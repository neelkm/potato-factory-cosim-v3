"""ovnewton adapter with explicit ownership and runtime collision isolation."""
import numpy as np
import warp as wp
import newton,ovnewton,ovstage
from state_protocol import RigidState
@wp.kernel
def record_contact_peak(count:wp.array[wp.int32],peak:wp.array[wp.int32]):
    wp.atomic_max(peak,0,count[0])

class NewtonEngine:
    def __init__(self,source,inactive=(),iterations=24,robot=False,robot_substeps=4,contact_capacity=32768):
        wp.set_device('cuda:0');newton.use_coord_layout_targets=True;ovnewton.register_usd_schemas()
        self.stage=ovstage.Stage('factory-newton');ovstage.population.open_usd(self.stage,source,ordinal=1,domains=ovstage.PopulationDomain.ALL);self.stage.advance_write_floor(1).wait()
        builder=newton.ModelBuilder();result=ovnewton.add_ovstage(builder,self.stage)
        self.model=builder.finalize(skip_validation_joints=result.has_orphan_joints)
        self.binding=ovnewton.attach_ovstage(self.stage,model=self.model)
        self.a,self.b=self.model.state(),self.model.state();self.control=self.model.control()
        newton.eval_fk(self.model,self.model.joint_q,self.model.joint_qd,self.a)
        self.b.body_q.assign(self.a.body_q);self.b.body_qd.assign(self.a.body_qd)
        self.paths=list(self.model.body_label);self.index={p:i for i,p in enumerate(self.paths)}
        self.flags=self.model.body_flags.numpy().copy();self.shape_flags=self.model.shape_flags.numpy().copy();self.joints=self.model.joint_enabled.numpy().copy()
        self.shape_body=self.model.shape_body.numpy();self.joint_parent=self.model.joint_parent.numpy();self.joint_child=self.model.joint_child.numpy()
        self.inactive=set();self.tick=0;self.ordinal=1
        self.solver=newton.solvers.SolverXPBD(self.model,iterations=iterations)
        self.robot=None;self.vacuum=None;self.graph=None;self.robot_substeps=robot_substeps
        self.contact_capacity=contact_capacity;self.contact_peak=wp.zeros(1,dtype=wp.int32)
        self.set_active(inactive,False)
        if robot:
            from franka_control import FrankaController
            from suction import VacuumGripper
            starts=self.model.joint_q_start.numpy();q=self.model.joint_q.numpy()
            target=[q[starts[self.model.joint_label.index(f'/World/Franka/fr3_link{i}/fr3_joint{i+1}')]] for i in range(7)]
            self.robot=FrankaController(self.model,target=target);self.vacuum=VacuumGripper(self.model)
    def describe(self):
        from importlib.metadata import version
        return dict(engine='newton',paths=self.paths,device=str(self.model.device),tick=self.tick,versions={p:version(p) for p in ['newton','ovnewton','ovstage','warp-lang']},internal_hz=240*self.robot_substeps,contact_capacity=self.contact_capacity)
    def set_active(self,paths,active):
        unknown=set(paths)-set(self.paths)
        if unknown:raise KeyError(unknown)
        if active:self.inactive.difference_update(paths)
        else:self.inactive.update(paths)
        disabled={self.index[p] for p in self.inactive};flags=self.flags.copy();sf=self.shape_flags.copy();jf=self.joints.copy()
        for i in disabled:flags[i]=int(newton.BodyFlags.KINEMATIC)
        for i,body in enumerate(self.shape_body):
            if body in disabled:sf[i]=0
        for i,(parent,child) in enumerate(zip(self.joint_parent,self.joint_child)):
            if parent in disabled or child in disabled:jf[i]=False
        self.model.body_flags.assign(flags);self.model.shape_flags.assign(sf);self.model.joint_enabled.assign(jf)
        inv_mass=1/self.model.body_mass.numpy();inv_inertia=np.linalg.inv(self.model.body_inertia.numpy())
        for i in disabled:inv_mass[i]=0;inv_inertia[i]=0
        self.model.body_inv_mass.assign(inv_mass.astype(np.float32));self.model.body_inv_inertia.assign(inv_inertia.astype(np.float32))
        self.solver.notify_model_changed(newton.ModelFlags.BODY_PROPERTIES | newton.ModelFlags.BODY_INERTIAL_PROPERTIES)
        # Broadphase caches collidable shape indices; rebuild it at the paused
        # ownership barrier instead of trusting a live flags edit alone.
        self.pipeline=newton.CollisionPipeline(self.model,rigid_contact_max=self.contact_capacity,include_static_kinematic_pairs=False);self.contacts=self.pipeline.contacts()
        self.graph=None
        return dict(inactive=sorted(self.inactive),active=len(self.paths)-len(self.inactive))
    def export_state(self,paths):
        q=self.a.body_q.numpy();v=self.a.body_qd.numpy();mass=self.model.body_mass.numpy();com=self.model.body_com.numpy();inertia=self.model.body_inertia.numpy()
        return [dict(path=p,pose=q[self.index[p]].tolist(),velocity=v[self.index[p]].tolist(),mass=float(mass[self.index[p]]),com=com[self.index[p]].tolist(),inertia=inertia[self.index[p]].tolist()) for p in paths]
    def import_state(self,states,joint_states=None):
        paths=[r['path'] for r in states]
        if not set(paths).issubset(self.inactive):raise RuntimeError('Receiver must be inactive before importing')
        q=self.a.body_q.numpy();v=self.a.body_qd.numpy();mass=self.model.body_mass.numpy();com=self.model.body_com.numpy();inertia=self.model.body_inertia.numpy();mi=self.model.body_inv_mass.numpy();ii=self.model.body_inv_inertia.numpy()
        for row in states:
            r=RigidState(**row).validate();i=self.index[r.path];q[i]=r.pose;v[i]=r.velocity;mass[i]=r.mass;com[i]=r.com;inertia[i]=r.inertia;mi[i]=1/r.mass;ii[i]=np.linalg.inv(r.inertia)
        self.model.body_mass.assign(mass);self.model.body_com.assign(com);self.model.body_inertia.assign(inertia);self.model.body_inv_mass.assign(mi);self.model.body_inv_inertia.assign(ii)
        for state in [self.a,self.b]:state.body_q.assign(q);state.body_qd.assign(v)
        self.graph=None
        if joint_states:
            parent_frames=self.model.joint_X_p.numpy();child_frames=self.model.joint_X_c.numpy()
            for path,description in joint_states.items():
                if 'parent_frame' not in description:continue
                if path not in self.model.joint_label:raise KeyError('Missing transfer joint '+path)
                j=self.model.joint_label.index(path);parent_frames[j]=description['parent_frame'];child_frames[j]=description['child_frame']
            self.model.joint_X_p.assign(parent_frames);self.model.joint_X_c.assign(child_frames)
        return self.export_state(paths)
    def advance(self,steps=1,dt=1/240):
        if self.robot:
            if steps%8 or abs(dt-1/240)>1e-10:raise ValueError('Franka uses 30 Hz control frames with 960 Hz internal substeps')
            if self.graph is None:self._capture_frame()
            for _ in range(steps//8):wp.capture_launch(self.graph)
            self._check_contacts()
            self.tick+=steps
            return dict(tick=self.tick)
        for _ in range(steps):
            self.a.clear_forces();self.pipeline.collide(self.a,self.contacts);self._record_contacts();self.solver.step(self.a,self.b,self.control,self.contacts,dt);self.a,self.b=self.b,self.a;self.tick+=1
        self._check_contacts()
        q=self.a.body_q.numpy()
        if not np.isfinite(q).all():raise RuntimeError('Newton produced non-finite state')
        return dict(tick=self.tick)
    def _substep(self):
        dt=1/(240*self.robot_substeps)
        self.a.clear_forces();self.robot.apply(self.a,self.control,dt);self.vacuum.apply(self.a)
        self.pipeline.collide(self.a,self.contacts);self._record_contacts();self.solver.step(self.a,self.b,self.control,self.contacts,dt);self.a,self.b=self.b,self.a
    def _record_contacts(self):wp.launch(record_contact_peak,dim=1,inputs=[self.contacts.rigid_contact_count],outputs=[self.contact_peak])
    def _check_contacts(self):
        if int(self.contact_peak.numpy()[0])>self.contact_capacity:raise RuntimeError('Newton contact capacity exceeded; run stopped before recording an invalid frame')
    def _capture_frame(self):
        q=self.a.body_q.numpy().copy();v=self.a.body_qd.numpy().copy()
        saved=[(array,array.numpy().copy()) for array in [self.robot.integral,self.robot.peak,self.vacuum.active,self.vacuum.peak,self.vacuum.deflection]]
        for _ in range(2):self._substep()
        for state in [self.a,self.b]:state.body_q.assign(q);state.body_qd.assign(v)
        for array,value in saved:array.assign(value)
        with wp.ScopedCapture(device=self.model.device) as capture:
            for _ in range(8*self.robot_substeps):self._substep()
        self.graph=capture.graph
    def set_robot_target(self,joints,payload=0.):
        self.robot.set_target(joints,payload);return None
    def seal_carton(self,box_path,flap_shapes):return self.vacuum.try_seal(self.a,box_path,flap_shapes)
    def release_carton(self):self.vacuum.release();self.robot.payload.zero_()
    def robot_status(self):
        newton.eval_ik(self.model,self.a,self.a.joint_q,self.a.joint_qd)
        starts=self.model.joint_q_start.numpy();q=self.a.joint_q.numpy()
        joints=[float(q[starts[j]]) for j in self.robot.joints.numpy()]
        return dict(joints=joints,tool_pose=self.a.body_q.numpy()[self.robot.tool].tolist(),peak_torque=self.robot.peak.numpy().tolist(),vacuum=self.vacuum.metrics(),contact_peak=int(self.contact_peak.numpy()[0]),contact_capacity=self.contact_capacity)
    def publish(self):
        self.ordinal+=1;self.binding.update_to_ovstage(self.a,ordinal=self.ordinal);self.stage.advance_write_floor(self.ordinal).wait()
        return dict(paths=self.paths,poses=self.a.body_q.numpy(),velocities=self.a.body_qd.numpy(),tick=self.tick)
    def close(self):
        # Worker lifetime owns the CUDA context. Dropping the binding first is
        # necessary before destroying its native stage.
        if hasattr(self.binding,'detach'):self.binding.detach()
        self.binding=None

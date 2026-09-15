"""ovphysx adapter: native state tensors, disabled actors, and real ovfmi control."""
import numpy as np
import ovstage
from ovphysx import PhysX
from ovphysx.api import set_log_level
from ovphysx.types import TensorType,LogLevel
from state_protocol import RigidState
class PhysXEngine:
    def __init__(self,source,inactive=(),fmi=False):
        set_log_level(LogLevel.ERROR);self.px=PhysX();set_log_level(LogLevel.ERROR)
        self.stage=ovstage.Stage('factory-physx');ovstage.population.open_usd(self.stage,source,ordinal=1,domains=ovstage.PopulationDomain.PHYSICS);self.stage.advance_write_floor(1).wait();self.px.attach_ovstage(self.stage,read_ordinal=1)
        self.bindings={};self.inactive=set();self.tick=0;self.fmi=None;self.pending_velocity={}
        if fmi:
            from fmi_control import Controller
            self.fmi=Controller(self.stage,source)
        self.set_active(inactive,False)
    def binding(self,paths,kind):
        key=(tuple(paths),kind)
        if key not in self.bindings:self.bindings[key]=self.px.create_tensor_binding(prim_paths=list(paths),tensor_type=kind,raise_if_empty=True)
        return self.bindings[key]
    def read(self,paths,kind):
        binding=self.binding(paths,kind);a=np.empty(binding.shape,dtype=np.uint8 if kind==TensorType.RIGID_BODY_DISABLE_SIMULATION else np.float32);binding.read(a)
        lookup={p:i for i,p in enumerate(binding.prim_paths)};return a[[lookup[p] for p in paths]]
    def write(self,paths,kind,data):
        binding=self.binding(paths,kind);lookup={p:i for i,p in enumerate(paths)};a=np.array([data[lookup[p]] for p in binding.prim_paths],dtype=np.uint8 if kind==TensorType.RIGID_BODY_DISABLE_SIMULATION else np.float32);binding.write(a)
    def describe(self):return dict(engine='physx',tick=self.tick)
    def set_active(self,paths,active):
        if paths:self.write(paths,TensorType.RIGID_BODY_DISABLE_SIMULATION,[0 if active else 1]*len(paths))
        if active:
            pending=[p for p in paths if p in self.pending_velocity]
            if pending:
                self.write(pending,TensorType.RIGID_BODY_VELOCITY,[self.pending_velocity[p] for p in pending])
                for p in pending:del self.pending_velocity[p]
        if active:self.inactive.difference_update(paths)
        else:self.inactive.update(paths)
        if paths:
            actual=self.read(paths,TensorType.RIGID_BODY_DISABLE_SIMULATION)
            if np.any(actual!=(0 if active else 1)):raise RuntimeError('PhysX activation readback failed')
        return dict(inactive=sorted(self.inactive))
    def export_state(self,paths):
        pose=self.read(paths,TensorType.RIGID_BODY_POSE);velocity=self.read(paths,TensorType.RIGID_BODY_VELOCITY);mass=self.read(paths,TensorType.RIGID_BODY_MASS);com=self.read(paths,TensorType.RIGID_BODY_COM_POSE);inertia=self.read(paths,TensorType.RIGID_BODY_INERTIA).reshape(-1,3,3)
        states=[]
        for i,p in enumerate(paths):
            # This binding returns the full tensor about COM in BODY axes.
            # Its COM-pose quaternion describes the internal principal frame;
            # applying that rotation again would rotate the tensor twice.
            states.append(dict(path=p,pose=pose[i].tolist(),velocity=velocity[i].tolist(),mass=float(mass[i]),com=com[i,:3].tolist(),inertia=inertia[i].tolist()))
        return states
    def import_state(self,states,joint_states=None):
        paths=[r['path'] for r in states]
        if not set(paths).issubset(self.inactive):raise RuntimeError('Receiver must be inactive before importing')
        arrays={k:[] for k in ['pose','velocity','mass','com','inertia']}
        for row in states:
            r=RigidState(**row).validate()
            arrays['pose'].append(r.pose);arrays['velocity'].append(r.velocity);arrays['mass'].append(r.mass);arrays['com'].append([*r.com,0,0,0,1]);arrays['inertia'].append(np.asarray(r.inertia).ravel())
        # The inertia setter diagonalizes the BODY-frame tensor and updates
        # its principal-axis COM rotation. Write COM position before inertia.
        for key,kind in [('mass',TensorType.RIGID_BODY_MASS),('com',TensorType.RIGID_BODY_COM_POSE),('inertia',TensorType.RIGID_BODY_INERTIA),('pose',TensorType.RIGID_BODY_POSE)]:self.write(paths,kind,arrays[key])
        # PhysX clears velocities on DISABLE_SIMULATION and refuses velocity
        # writes while disabled. Stage the measured twist until activation;
        # activation and readback occur while both engine clocks are paused.
        self.pending_velocity.update(zip(paths,arrays['velocity']))
        return self.export_state(paths)
    def control(self,dt=1/30,**inputs):
        if self.fmi is None:raise RuntimeError('No FMU loaded')
        return self.fmi.step(dt,**inputs)
    def advance(self,steps=1,dt=1/240):
        for _ in range(steps):self.px.step_sync(dt);self.tick+=1
        return dict(tick=self.tick)
    def close(self):
        if self.fmi:self.fmi.close()
        for b in self.bindings.values():b.destroy()
        self.px.detach_ovstage();self.px.release();self.stage.destroy()

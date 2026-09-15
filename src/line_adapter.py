"""Expose the full PhysX production line through the ownership protocol."""
import numpy as np
from scipy.spatial.transform import Rotation
from physx_engine import PhysXEngine
from line_simulation import FactoryLine
class PhysXLineAdapter(PhysXEngine):
    def __init__(self,source,inactive=('/World/Pallet',),water=True,external_control=False):
        self.line=FactoryLine(water=water,source=source,external_control=external_control)
        self.px=self.line.px;self.stage=self.line.stage;self.fmi=self.line.fmi
        self.bindings={};self.inactive=set();self.pending_velocity={};self.tick=0
        self.set_active(inactive,False)
    def describe(self):
        from importlib.metadata import version
        packages=['ovphysx','ovstage']+([] if self.line.external_control else ['ovfmi'])
        return dict(engine='physx',paths=self.line.paths,tick=self.tick,versions={p:version(p) for p in packages})
    def import_state(self,states,joint_states=None):
        result=super().import_state(states,joint_states)
        # Incoming native tensor writes must also refresh the line's capture
        # and sensor cache before the paused ownership barrier is published.
        self.line.read()
        return result
    def advance(self,steps=8,dt=1/240):
        if steps%8 or abs(dt-1/240)>1e-10:raise ValueError('Factory line advances in 30 Hz control intervals with 240 Hz physics')
        from ovphysx.types import TensorType
        standby=sorted(self.inactive)
        before=self.read(standby,TensorType.RIGID_BODY_POSE) if standby else None
        for _ in range(steps//8):self.line.step()
        if standby:
            disabled=self.read(standby,TensorType.RIGID_BODY_DISABLE_SIMULATION)
            after=self.read(standby,TensorType.RIGID_BODY_POSE)
            if np.any(disabled!=1) or np.max(abs(after-before))>1e-7:raise RuntimeError('A PhysX counterpart moved or reactivated while owned by Newton')
        self.tick=self.line.frame;return dict(tick=self.tick)
    def status(self):
        s=self.line
        return dict(tick=self.tick,time=s.t,box=s.box_index,pallet=s.pallet_count,box_count=len(s.box_members[min(s.box_index,5)]),target=s.box_target,reserved=len(s.reserved),washed=len(s.washed),inspected=len(s.inspected),handoff_ready=s.handoff_ready,forklift_complete=s.forkdone)
    def collect_inputs(self,dt=1/30):return self.line.collect_inputs(dt)
    def apply_controls(self,outputs):return bool(self.line.apply_controls(outputs))
    def capture(self):return dict(paths=self.line.paths,poses=np.asarray([self.line.pose_map[p] for p in self.line.paths]),water=self.line.water_points,status=self.status())
    def transfer_request(self):
        s=self.line
        if not s.handoff_ready:return None
        box=f'/World/Box_{s.box_index}';flaps=[f'/World/Flap_{s.box_index}_{j}' for j in range(4)];members=flaps+sorted(s.box_members[s.box_index]);paths=[box]+members
        if not 15<=len(s.box_members[s.box_index])<=20:raise RuntimeError('Carton count outside requested range')
        states={r['path']:r for r in self.export_state(paths)};b=np.array(states[box]['pose']);br=Rotation.from_quat(b[3:]);joints={}
        for f in flaps:
            pose=np.array(states[f]['pose']);local=br.inv().apply(pose[:3]-b[:3]);quat=(br.inv()*Rotation.from_quat(pose[3:])).as_quat()
            joints['/World/Joints/'+f.rsplit('/',1)[-1]]=dict(parent=box,child=f,sealed=True,parent_frame=[*local.tolist(),*quat.tolist()],child_frame=[0,0,0,0,0,0,1])
        return dict(box=s.box_index,paths=paths,membership={box:members},joint_states=joints,potatoes=len(s.box_members[s.box_index]),mass=sum(r['mass'] for r in states.values()))
    def carton_transferred(self):self.line.carton_transferred()
    def carton_placed(self):self.line.carton_placed()
    def pallet_returned(self):self.line.pallet_returned=True
    def report(self):
        s=self.line
        return dict(seconds=s.t,cache_fps=30,physics_hz=240,potatoes=len(s.potatoes),water=s.water,fluid_particles=s.inlet.n if s.inlet else 0,recycled_particles=s.inlet.recycled if s.inlet else 0,wash_times=s.wash_times,events=s.events,history=s.history,boxes=[sorted(v) for v in s.box_members],pallet_count=s.pallet_count,forklift_complete=s.forkdone,max_truck_potato_speed=s.max_truck_speed,manifest=s.meta)
    def close(self):
        for b in self.bindings.values():b.destroy()
        self.line.close()

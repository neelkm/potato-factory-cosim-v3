"""GPU PhysX production line, washing particles, FMI controls and forklift.

Driven machine bodies use native actuator targets. Loads move through contact.
The separate Newton worker owns the Franka and transferred cartons.
"""
import argparse,json,time,math,os
import numpy as np
import ovstage
from ovphysx import PhysX
from ovphysx.api import set_log_level
from ovphysx.types import LogLevel
from ovphysx.types import SimObjectType,ObjectScope,TensorType
from config import *
from mechanics import Mechanics
from fmi_control import Controller
from fluid_inlet import FluidInlet
from forklift_motion import ForkliftMotion
from conveyor_control import TerminalBeltDrive
def smooth(u):
    u=max(0,min(1,u));return u*u*u*(10+u*(-15+6*u))
def mix(a,b,u):return np.asarray(a)+(np.asarray(b)-a)*smooth(u)
def rotation(yaw,pitch=0):
    a,b=yaw/2,pitch/2;return (-math.sin(a)*math.sin(b),math.cos(a)*math.sin(b),math.sin(a)*math.cos(b),math.cos(a)*math.cos(b))
class FactoryLine:
    def __init__(self,water=True,source='factory_physx.usda',external_control=False):
        self.meta=json.loads((OUT/'manifest.json').read_text());self.water=water
        set_log_level(LogLevel.ERROR)
        self.stage=ovstage.Stage('field-flow-line');self.px=PhysX();set_log_level(LogLevel.ERROR)
        ovstage.population.open_usd(self.stage,str(OUT/source),ordinal=1,domains=ovstage.PopulationDomain.PHYSICS)
        self.stage.advance_write_floor(1).wait();self.px.attach_ovstage(self.stage,read_ordinal=1)
        self.d=ovstage.PathDictionary(self.stage);self.ordinal=1;self.m=Mechanics(self.px)
        self.external_control=external_control;self.control_context=None;self.control_applied_tick=None
        self.fmi=None if external_control else Controller(self.stage,OUT/source);self.inlet=FluidInlet(self.px) if water else None
        self.t=0.;self.frame=0;self.pose_map={};self.water_points=np.empty((0,3),np.float32)
        self.read();self.paths=sorted(self.pose_map)
        self.potatoes={'/World/'+p['name']:p for p in self.meta['potatoes']}
        for p in self.paths:
            if not p.startswith('/World/Roller'):self.m.tune(p)
        self.force=self.px.create_tensor_binding(prim_paths=list(self.potatoes),tensor_type=TensorType.RIGID_BODY_FORCE,raise_if_empty=True)
        self.velocity=self.px.create_tensor_binding(prim_paths=self.force.prim_paths,tensor_type=TensorType.RIGID_BODY_VELOCITY,raise_if_empty=True)
        self.force_index={p:i for i,p in enumerate(self.force.prim_paths)};self.vel=np.zeros(self.velocity.shape,np.float32);self.forces=np.zeros(self.force.shape,np.float32)
        from line_attribute_updates import ChangedAttributes
        self.changed_attributes=ChangedAttributes()
        self.queries={};self.events=[];self.washed=set();self.wash_dose={};self.wash_times={};self.inspected=set();self.rejects={}
        self.box_index=0;self.pallet_count=0;self.box_members=[set() for _ in range(6)];self.delivered=set();self.reserved=set();self.packing=None;self.gripped=False;self.forkstart=None;self.forkdone=False
        self.good_batch=sum(not p['damaged'] for p in self.potatoes.values());self.box_target=carton_target(self.good_batch,BOX_COUNT)
        self.tool=np.array((7.95,0,1.8));self.close_start=None;self.grip_peak=0.;self.grip_peak_deflection=0.;self.grip_offset=None;self.fill_gate_z=1.28;self.max_truck_speed=0.;self.history=[];self.fmi_out={}
        self.handoff_ready=False;self.pallet_returned=False
        self.fill_ready=False
        self.base_tilt=0.;self.motor_speed=BELT_SPEED;self.vibrators=[b for b in self.meta['bodies'] if b.get('vibrating')]
        self.terminal_drive=TerminalBeltDrive(speed=3*BELT_SPEED)
    def query(self,paths):
        key=tuple(paths)
        if key not in self.queries:
            pl=self.d.create_path_list_from_strings(paths);self.queries[key]=self.stage.query_from_path_list(pl);self.d.destroy_path_list(pl)
        return self.queries[key]
    def write(self,path,name,values):
        self.changed_attributes.write(self,[path],name,values)
    def read(self):
        with self.px.read(SimObjectType.RIGID_BODY,['position','orientation'],ObjectScope.ALL) as r:
            for g in r.groups:
                if g.is_array or not g.tensors:continue
                kind=self.d.token_to_string(g.attribute)
                for name,v in zip(self.d.get_path_strings(g.prim_list),g.tensors[0]):
                    if name not in self.pose_map:self.pose_map[name]=np.zeros(7,np.float32)
                    if kind=='position':self.pose_map[name][:3]=v
                    if kind=='orientation':self.pose_map[name][3:]=v
        if self.water:
            arrays=[]
            with self.px.read(SimObjectType.PARTICLE_SET,['points'],ObjectScope.ALL) as r:
                for g in r.groups:arrays.extend(g.tensors)
            a=np.concatenate(arrays).astype(np.float32) if arrays else np.empty((0,3),np.float32)
            self.water_points=a[(a[:,2]>.85)&(a[:,2]<2.6)&(abs(a[:,0])<2.2)&(abs(a[:,1])<1.65)]
    def event(self,kind,**kw):self.events.append(dict(time=round(self.t,4),kind=kind,**kw))
    def controls(self,dt):
        inputs=self.collect_inputs(dt)
        self.apply_controls(self.fmi.step(dt,**inputs))
    def collect_inputs(self,dt):
        if self.control_context is not None:raise RuntimeError('Sensor preparation called twice before controller response')
        self.ordinal+=1;self.changed_attributes.dirty=False;self.velocity.read(self.vel);self.forces[:]=0
        for path,p in self.potatoes.items():
            x,y,z=self.pose_map[path][:3]
            if x>4.46 and z>1.30 and path not in self.inspected:
                raise RuntimeError('Uninspected produce passed the quality station: '+path)
            if x<-4.75:self.max_truck_speed=max(self.max_truck_speed,float(np.linalg.norm(self.vel[self.force_index[path],:3])))
            if -1.7<x<1.7 and 1.45<z<2.1 and len(self.water_points):
                near=np.count_nonzero(np.sum((self.water_points-[x,y,z])**2,axis=1)<.13**2)
                if near:
                    self.wash_dose[path]=self.wash_dose.get(path,0)+dt
                    if self.wash_dose[path]>=.033 and path not in self.washed:self.washed.add(path);self.wash_times[path]=self.t
            if self.box_index<6 and path not in self.delivered and x>7.67 and abs(y)<.26 and z>1.22:self.reserved.add(path)
        count=0;ready=False
        if self.box_index<6:
            b=self.pose_map[f'/World/Box_{self.box_index}'][:3];ready=abs(b[0]-FILL[0])<.07 and abs(b[1])<.045 and abs(b[2]-FILL[2])<.045
            if ready and not self.gripped:
                for path in self.potatoes:
                    r=self.pose_map[path][:3]-b
                    if abs(r[0])<.153 and abs(r[1])<.113 and .015<r[2]<BOX_SIZE[2]+.01 and path not in self.delivered:self.box_members[self.box_index].add(path)
            count=len(self.box_members[self.box_index])
        # Cover the entire roller width, including produce displaced sideways
        # while the rejection guard is open for an earlier damaged potato.
        candidates=[p for p in self.potatoes if p not in self.inspected and 4.02<self.pose_map[p][0]<4.38 and abs(self.pose_map[p][1])<.80 and 1.46<self.pose_map[p][2]<1.95]
        candidate=max(candidates,key=lambda p:self.pose_map[p][0]) if candidates else None
        inputs=dict(presence=bool(candidate),objectId=int(candidate[-3:]) if candidate else -1,defectScore=self.potatoes[candidate]['defect_fraction'] if candidate else 0,washed=candidate in self.washed,boxCount=count,boxReady=ready,armBusy=self.packing is not None,palletCount=self.pallet_count,targetCount=self.box_target)
        self.control_context=dict(dt=dt,ready=ready,count=count,b=self.pose_map[f'/World/Box_{min(self.box_index,5)}'][:3].copy(),tick=self.frame)
        return inputs
    def apply_controls(self,outputs):
        context=self.control_context
        if context is None or context['tick']!=self.frame:raise RuntimeError('Controller response has no matching sensor sample')
        dt=context['dt'];ready=context['ready'];count=context['count'];b=context['b']
        self.fill_ready=bool(ready)
        self.fmi_out=outputs;o=self.fmi_out
        decision=int(round(o.get('decisionId',-1)));path=f'/World/Potato_{decision:03d}'
        if path in self.potatoes and path not in self.inspected and (o.get('acceptPulse',0)>.5 or o.get('rejectPulse',0)>.5):
            bad=o.get('rejectPulse',0)>.5;self.inspected.add(path);self.event('reject' if bad else 'accept',potato=path,washed=path in self.washed,position=list(map(float,self.pose_map[path][:3])))
            if bad:self.rejects[path]=self.t
        # Pneumatic force over 0.28 s; the FMU models the valve pressure rise.
        for path,start in list(self.rejects.items()):
            if self.t-start<.28:
                j=self.force_index[path];mass=self.potatoes[path]['mass'];pressure=max(.15,o.get('valvePressure',0))
                # Lift clear of adjacent produce, then divert laterally.
                wanted=np.array((.25,0,3.4) if self.t-start<.10 else (.25,-2.8,.6),np.float32)
                self.forces[j]=mass*pressure*(wanted-self.vel[j,:3])*22
        if count>BOX_MAX:raise RuntimeError(f'Carton {self.box_index} exceeds {BOX_MAX} potatoes')
        if o.get('packRequest',0)>.5 and self.packing is None and count>=self.box_target:
            self.packing=self.t;self.close_start=b.copy();self.event('box_full',box=self.box_index,count=count,target=self.box_target)
        elapsed=self.t-self.packing if self.packing is not None else -1
        if self.packing is not None and not self.gripped:
            for flap in self.meta['flaps']:
                if flap['box']==f'Box_{self.box_index}':
                    j=int(flap['name'][-1]);v=flap['target']*smooth((elapsed-(.9 if j>=2 else 1.8))/.8)
                    self.m.fold('/World/Joints/'+flap['name'],flap['axis'],math.radians(v))
            if elapsed>=3.2 and not self.gripped:self.handoff_ready=True
        if o.get('forkliftRequest',0)>.5 and self.pallet_returned and self.forkstart is None:
            self.fork_motion=ForkliftMotion(self.pose_map['/World/Pallet'])
            self.forkstart=self.t;self.event('forklift_start',alignment=self.fork_motion.describe())
        # Slow velocity ramps provide motor acceleration limits and hold a full box.
        run=o.get('conveyorRun',1)>.5 and len(self.reserved)<self.box_target
        desired=BELT_SPEED if run else 0.;self.motor_speed+=max(-.012,min(.012,desired-self.motor_speed))
        # An upstream stop must not strand a coasting potato at the belt lip,
        # where it can strike an upright carton flap. Clear the terminal belt
        # before the lids fold; the raised gate retains the upstream queue.
        terminal_speed=self.terminal_drive.update(dt,ready=ready,gripped=self.gripped,packing_elapsed=elapsed if self.packing is not None else None)
        for belt in self.meta['belts']:
            name=belt['name'];v=(0,-.22 if self.box_index<6 and not ready and self.packing is None else 0,0) if name=='CartonBelt' else (self.motor_speed*(3 if name.startswith('Output') else 1),0,0)
            if name=='OutputBelt':v=(terminal_speed,0,0)
            if name=='ReceivingBelt':
                on_wash=sum(-1.73<self.pose_map[p][0]<4.8 and self.pose_map[p][2]>1.3 for p in self.potatoes)
                v=(self.motor_speed*.25 if on_wash<16 else 0,0,0)
            self.write('/World/'+name,'physxSurfaceVelocity:surfaceVelocity',[v])
        # Rotation resistance represents the loaded wash bed; free produce
        # regains normal rotation on the belts and inside cartons.
        damping=np.array([100. if -1.80<self.pose_map[p][0]<4.85 and self.pose_map[p][2]>1.3 else .25 for p in self.potatoes],np.float32)
        self.changed_attributes.write(self,list(self.potatoes),'physxRigidBody:angularDamping',damping)
        roller_paths=['/World/Joints/'+r['name'] for r in self.meta['rollers']]
        self.changed_attributes.write(self,roller_paths,'drive:angular:physics:targetVelocity',np.full(len(roller_paths),math.degrees(self.motor_speed/ROLL_RADIUS),np.float32))
        self.stage.advance_write_floor(self.ordinal).wait()
        if self.changed_attributes.dirty:self.px.update_from_ovstage(self.ordinal,self.ordinal)
        self.control_context=None;self.control_applied_tick=self.frame
        return ready
    def actuators(self,t):
        for guide in self.vibrators:
            p=np.asarray(guide['pos'],float).copy();p[1]+=.006*math.sin(t*2*math.pi*3)
            self.m.target('/World/'+guide['name'],p,rotation(math.radians(guide.get('rotate_z',0))))
        angle=math.radians(31)*smooth((t-3)/24)
        self.m.target('/World/TruckBed',(-4.9,0,1.82),rotation(0,angle))
        # Retract the side guard laterally. A descending guard can press a
        # neighbouring good potato through a fine-pitch roller bed. Keep the
        # swept region clear before closing, and limit the return speed.
        opening=any(0<t-start<.65 for start in self.rejects.values())
        occupied=any(3.65<self.pose_map[p][0]<4.47 and -.55<self.pose_map[p][1]<-.018 and 1.43<self.pose_map[p][2]<1.79 for p in self.potatoes)
        goal=-.52 if opening or occupied else -.052
        previous=getattr(self,'reject_gate_y',-.052)
        self.reject_gate_y=previous+max(-4.8/PHYSICS_HZ,min(.40/PHYSICS_HZ,goal-previous))
        self.m.target('/World/RejectGate',(4.06,self.reject_gate_y,1.60))
        gate=not self.fill_ready or len(self.reserved)>=self.box_target or self.packing is not None or self.box_index>=6
        goal=1.60 if gate else 1.28
        self.fill_gate_z+=max(-.65/PHYSICS_HZ,min(.65/PHYSICS_HZ,goal-self.fill_gate_z))
        self.m.target('/World/FillGate',(7.61,0,self.fill_gate_z))
        p=np.array((8.17,-7.5,0.));carriage=p+np.array((0,0,-.03));yaw=0.
        if self.forkstart is not None:
            e=t-self.forkstart
            p,carriage,yaw=self.fork_motion.targets(e)
            if e>54 and not self.forkdone:self.forkdone=True;self.event('forklift_complete')
        self.m.target('/World/Forklift',p,rotation(yaw));self.m.target('/World/Forks',carriage,rotation(yaw))
    def carton_transferred(self):
        self.handoff_ready=False;self.gripped=True
    def carton_placed(self):
        i=self.box_index;members=self.box_members[i]
        self.delivered.update(members);self.reserved.difference_update(members);self.pallet_count+=1
        self.event('box_placed',box=i,count=len(members),pallet_count=self.pallet_count)
        self.box_index+=1;self.packing=None;self.gripped=False
        self.fill_ready=False
        if self.box_index<BOX_COUNT:self.box_target=carton_target(self.good_batch-len(self.delivered),BOX_COUNT-self.box_index)
    def step(self):
        dt=1/CACHE_FPS
        if self.external_control:
            if self.control_applied_tick!=self.frame:raise RuntimeError('Physics cannot advance before fresh control inputs')
        else:self.controls(dt)
        for _ in range(PHYSICS_HZ//CACHE_FPS):
            if self.inlet:self.inlet.update(1/PHYSICS_HZ)
            self.actuators(self.t+1/PHYSICS_HZ)
            for path in self.rejects:
                f=self.forces[self.force_index[path]]
                if np.any(f):self.m.push(path,f)
            self.px.step_sync(1/PHYSICS_HZ);self.frame+=1;self.t=self.frame/PHYSICS_HZ
        self.read()
        if self.frame%PHYSICS_HZ==0:self.history.append(dict(time=self.t,box=self.box_index,pallet=self.pallet_count,box_count=len(self.box_members[min(self.box_index,5)]),box_target=self.box_target,reserved=len(self.reserved),washed=len(self.washed),inspected=len(self.inspected)))
    def close(self):
        if self.fmi:self.fmi.close()
        self.force.destroy();self.velocity.destroy()
        for q in self.queries.values():self.stage.release_query(q).wait()
        self.d.destroy();self.px.detach_ovstage();self.px.release();self.stage.destroy()

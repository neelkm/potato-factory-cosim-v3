"""Measured, contact-gated FR3 carton pick and placement sequence."""
from pathlib import Path
import json,numpy as np
from franka_motion import FrankaKinematics
ROOT=Path(__file__).resolve().parents[1]
def smooth(u):u=np.clip(u,0,1);return u*u*u*(10+u*(-15+6*u))
class RobotCycle:
    def __init__(self,engine,manifest,request,time):
        self.engine=engine;self.request=request;self.box=request['box'];self.path=f'/World/Box_{self.box}'
        self.layout=json.loads((ROOT/'output/cell_layout.json').read_text());self.k=FrankaKinematics(self.layout['base'])
        self.mass=request['mass'];self.events=[];self.finished=False;self.attached=False;self.placed=False;self.seal_attempt_started=None
        self.flaps=[]
        for body in manifest['bodies']:
            if body['name'].startswith(f'Flap_{self.box}_'):
                for center,size in body['shapes']:self.flaps.append(('/World/'+body['name'],center,size))
        state=engine.call('export_state',paths=[self.path])[0];p=np.asarray(state['pose'][:3]);self.pick=p+np.array([0,0,.192])
        status=engine.call('robot_status');self.current=np.asarray(status['joints'])
        self.phases=[('above',3.,self.pick+np.array([0,0,.09])),('descend',3.,self.pick),('seal',2.,self.pick)]
        self.index=-1;self.phase_start=time;self.start_phase(time)
    def log(self,time,kind,**kw):self.events.append(dict(time=float(time),kind=kind,box=self.box,**kw))
    def start_phase(self,time):
        self.index+=1
        if self.index>=len(self.phases):self.finished=True;return
        name,duration,point=self.phases[self.index];self.phase_start=time
        self.q0=self.current.copy();self.q1=self.k.solve(np.asarray(point),self.current);self.target=np.asarray(point);self.log(time,'robot_phase',phase=name)
        self.start_point=self.k.tip(self.q0)[:3,3].copy()
    def before_step(self,time):
        if self.finished:return
        name,duration,point=self.phases[self.index];u=(time-self.phase_start)/duration
        if name in ('descend','lift','place','retreat'):
            # Joint interpolation bows the carton sideways even when both
            # endpoint tool poses share the same x/y. Keep the commanded tool
            # path straight around the neighboring cartons and filling guides.
            position=self.start_point+(self.target-self.start_point)*smooth(u)
            self.current=self.k.solve(position,self.current)
        else:self.current=self.q0+(self.q1-self.q0)*smooth(u)
        self.engine.call('set_robot_target',joints=self.current.tolist(),payload=self.mass if self.attached else 0.)
    def after_step(self,time):
        if self.finished:return
        status=self.engine.call('robot_status');name,duration,point=self.phases[self.index]
        if self.attached and not status['vacuum']['active']:raise RuntimeError('Vacuum seal broke during loaded FR3 motion')
        if time-self.phase_start<duration:return
        if name=='seal':
            result=self.engine.call('seal_carton',box_path=self.path,flap_shapes=self.flaps)
            if not result['sealed']:
                if self.seal_attempt_started is None:self.seal_attempt_started=time
                if time-self.seal_attempt_started>4.:raise RuntimeError(f'Could not seat all four suction cups: {result}')
                # Creep downward under torque control until the compliant lips
                # contact the measured lid surfaces. Never move the carton.
                self.target[2]-=.00010;self.q1=self.k.solve(self.target,self.q1);self.current=self.q1.copy()
                return
            self.attached=True;self.log(time,'vacuum_attached',mass_kg=self.mass,contacts=result['contacts'])
            target=np.asarray(self.layout['targets'][self.box]);lift=self.pick+np.array([0,0,.09])
            self.phases.extend([('lift',3.,lift),('carry_front',4.,(8.65,-.08,1.40)),('carry_side',3.,(8.72,-.58,1.30)),('above_pallet',4.,(target[0],target[1],1.24)),('place',4.,target),('settle',2.,target),('release',.1,target),('retreat',3.,(target[0],target[1],1.24)),('return_side',3.,(8.72,-.58,1.30)),('return_park',4.,self.layout['waypoints']['via_front']['position'])])
        elif name=='settle':
            state=self.engine.call('export_state',paths=[self.path])[0];velocity=np.asarray(state['velocity']);target=np.asarray(self.layout['targets'][self.box]);p=np.asarray(state['pose'][:3])
            if np.linalg.norm(p[:2]-target[:2])>.025:raise RuntimeError('Carton missed its pallet slot')
            pallet=self.engine.call('export_state',paths=['/World/Pallet'])[0]
            deck=pallet['pose'][2]+.15
            if p[2]>deck+.004:
                if time-self.phase_start>7.:raise RuntimeError('Carton did not contact the pallet before release')
                self.target[2]-=.0004;self.q1=self.k.solve(self.target,self.q1);self.current=self.q1.copy();return
            if np.linalg.norm(velocity[:3])>.035 and time-self.phase_start<8.:return
            if np.linalg.norm(velocity[:3])>.035:raise RuntimeError('Carton did not settle before release')
        elif name=='release':
            self.engine.call('release_carton');self.attached=False;self.placed=True;self.log(time,'vacuum_released',vacuum=status['vacuum'],peak_torque=status['peak_torque'])
        self.start_phase(time)

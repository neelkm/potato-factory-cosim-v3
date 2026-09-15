"""Reference implementation of the factory FMU for explicitly selected simple runs."""
import math
from fmi_control import INPUTS,OUTPUTS

class SimpleController:
    def __init__(self):
        self.values={name:0. for name in INPUTS+OUTPUTS}
        self.values.update(targetCount=18.,conveyorRun=1.,decisionId=-1.)
        self.done=set();self.current=-1;self.dwell=0.;self.jet=0.
    def step(self,dt,**inputs):
        if dt<=0:raise ValueError('Invalid control timestep')
        self.values.update(inputs);v=self.values;identity=int(v['objectId'])
        if v['presence']>.5 and 0<=identity<512 and identity not in self.done:
            if self.current!=identity:self.current=identity;self.dwell=0.;v['acceptPulse']=v['rejectPulse']=0.
            self.dwell+=dt
            if self.dwell>=.06:
                bad=v['defectScore']>.10 or v['washed']<.5;self.done.add(identity);v['decisionId']=float(identity)
                if bad:v['rejectPulse']=1.;v['rejectedTotal']+=1.;self.jet=.32
                else:v['acceptPulse']=1.;v['acceptedTotal']+=1.
        elif v['presence']<.5:self.current=-1;self.dwell=0.;v['acceptPulse']=v['rejectPulse']=0.
        self.jet=max(0.,self.jet-dt);command=1. if self.jet>0 else 0.
        v['valvePressure']+=(command-v['valvePressure'])*(1-math.exp(-dt/.035))
        target=v['targetCount'] if 15<=v['targetCount']<=20 else 18.
        v['packRequest']=float(v['boxCount']>=target and v['boxReady']>.5 and v['armBusy']<.5)
        v['forkliftRequest']=float(v['palletCount']>=6)
        v['conveyorRun']=float(v['boxReady']>.5 and v['boxCount']<target and v['armBusy']<.5 and v['palletCount']<6)
        return {name:float(v[name]) for name in OUTPUTS}
    def close(self):pass

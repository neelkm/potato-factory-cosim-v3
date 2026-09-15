"""Use NVIDIA's teleport zone decisions with qualified native transactions."""
import numpy as np
from .coupling import create_nvidia_zone_policy,FACTORY_CAPABILITIES

class NvidiaTeleportBridge:
    def __init__(self,coordinator,zones,bodies):
        if any(z.mode!='teleport' for z in zones):raise ValueError('This native bridge implements contact-free teleport zones only')
        self.coordinator=coordinator;self.cells=list(coordinator.engines);self.bodies=list(bodies)
        self.policy=create_nvidia_zone_policy(zones=zones,cells=self.cells,bodies=self.bodies,
                  start_owners=[self.cells.index(coordinator.owners[p]) for p in self.bodies],capabilities=FACTORY_CAPABILITIES)
        self.ports={}
        for name in self.cells:
            self.ports[self.policy.state_port(name)]=np.zeros((len(bodies),13),np.float32)
            self.ports[self.policy.ownership_port(name)]=np.zeros((len(bodies),14),np.float32)
    def update(self):
        c=self.coordinator
        with c._lock:
            c.assert_ready()
            try:
                previous=self.policy.owners.copy()
                for name in self.cells:
                    rows=c.engines[name].call('export_state',paths=self.bodies)
                    self.ports[self.policy.state_port(name)][:]=[r['pose']+r['velocity'] for r in rows]
                self.policy(c.tick/240,1/240,self.ports)
                for i,(old,new) in enumerate(zip(previous,self.policy.owners)):
                    if old!=new:
                        event=c.transfer([self.bodies[i]],self.cells[int(old)],self.cells[int(new)])
                        event['decision_policy']='NVIDIA HandoffPolicy teleport'
            except BaseException as exc:c.fail(exc);raise

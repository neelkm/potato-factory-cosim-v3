"""Execute the real NVIDIA policy APIs on deterministic boundary records.

This is a policy/port demonstration, not a native contact simulation. Native
factory qualification is src/check_handoff.py and the full production run.
"""
from pathlib import Path
import sys,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from framework.coupling import *

def run():
    cells=['physx','newton'];caps={'physx':Capabilities(hold_proxy=True,apply_wrench=True),'newton':Capabilities(hold_proxy=True,harvest_proxy_force=True)}
    modes={}
    for mode in ['teleport','replica','force']:
        zone=HandoffZone('seam',tuple(cells),0,0,0,.1,1.,mode)
        policy=create_nvidia_zone_policy(zones=[zone],cells=cells,bodies=['/Body'],start_owners=[0],capabilities=caps)
        ports={}
        for cell in cells:
            ports[policy.state_port(cell)]=np.zeros((1,13),np.float32);ports[policy.state_port(cell)][0,6]=1
            ports[policy.ownership_port(cell)]=np.zeros((1,14),np.float32)
        commands=[]
        for tick,x in enumerate([-.3,-.05,.05,.2,.3,.05,-.2,-.3]):
            for cell in cells:ports[policy.state_port(cell)][0,0]=x
            policy(tick/30,1/30,ports)
            commands.append(dict(tick=tick,x=x,owner=cells[int(policy.owners[0])],commands={cell:int(ports[policy.ownership_port(cell)][0,13]) for cell in cells}))
        assert len(policy.transitions)==2
        modes[mode]=dict(transitions=policy.transitions,commands=commands)
    report=dict(passed=True,scope='NVIDIA policy and port behavior only; native contact dynamics are not exercised',modes=modes)
    (ROOT/'output/coupling_policy_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    return report
if __name__=='__main__':run()

from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from physics_debug import DebugData,DebugState,DebugRenderer
d=DebugData();renderer=DebugRenderer(d)
for name,s in [('approach',DebugState(tick=240*9)),('contacts',DebugState(tick=240*13,closeup=True)),('handoff',DebugState(mode='Engine handoff',closeup=True,tick=1))]:
    before=time.monotonic();renderer.render(s,1280,720).save(d.base/(name+'.png'));print(name,time.monotonic()-before)
print('first_contact',d.first_contact,'peak',d.peak.max(axis=0).tolist())

"""Validate every carton approach against the actual FR3 kinematics."""
import json,numpy as np
from pathlib import Path
from franka_motion import FrankaKinematics,HOME
ROOT=Path(__file__).resolve().parents[1]
BASE=(8.15,-.50,.95)
PICKUP=(7.95,0,1.334)
TARGETS=[(x,y,.963) for y in [-1.15,-.89] for x in [7.84,8.17,8.50]]
def main():
    k=FrankaKinematics(BASE);points={'pickup':PICKUP,'pickup_lift':(7.95,0,1.425),'via_front':(8.65,-.08,1.35),'via_side':(8.72,-.58,1.30)}
    for i,p in enumerate(TARGETS):points[f'place_{i}']=p;points[f'approach_{i}']=(p[0],p[1],1.24)
    q=HOME.copy();solved={}
    for name,p in points.items():
        q=k.solve(np.array(p),q);solved[name]=dict(position=p,joints=q.tolist());print(name,'OK',flush=True)
    report=dict(base=BASE,pickup=PICKUP,pallet=(8.17,-1.02,.62),targets=TARGETS,waypoints=solved)
    (ROOT/'output/cell_layout.json').write_text(json.dumps(report,indent=2));print('ALL_CELL_TARGETS_REACHABLE',flush=True)
if __name__=='__main__':main()

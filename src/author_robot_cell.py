"""Place the actual FR3 and vacuum tool at the validated packing-cell pose."""
from pathlib import Path
import json,math,numpy as np
from pxr import Usd,UsdGeom,UsdPhysics,Gf
from scipy.spatial.transform import Rotation
from franka_motion import FrankaKinematics
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
def main():
    src=Usd.Stage.Open(str(OUT/'franka_test.usda'));src.GetRootLayer().Export(str(OUT/'franka_cell.usda'));s=Usd.Stage.Open(str(OUT/'franka_cell.usda'))
    layout=json.loads((OUT/'cell_layout.json').read_text());q=np.array(layout['waypoints']['via_front']['joints']);k=FrankaKinematics(layout['base']);links,_,_=k.chain(q)
    poses={f'/World/Franka/fr3_link{i}':m for i,m in enumerate(links)};tool=links[-1].copy();tool[:3,3]+=tool[:3,:3]@np.array([0,0,.107]);poses['/World/Tool']=tool
    for p,m in poses.items():
        op=UsdGeom.Xformable(s.GetPrimAtPath(p)).MakeMatrixXform();op.Set(Gf.Matrix4d(*m.T.ravel().tolist()))
    root=UsdPhysics.FixedJoint(s.GetPrimAtPath('/World/Franka/root_joint'));root.CreateLocalPos0Attr(Gf.Vec3f(*layout['base']))
    for i,v in enumerate(q):s.GetPrimAtPath(f'/World/Franka/fr3_link{i}/fr3_joint{i+1}').GetAttribute('state:angular:physics:position').Set(math.degrees(v))
    s.RemovePrim('/World/Floor');s.RemovePrim('/World/Physics');s.GetRootLayer().Save()
    print('FR3_CELL_ASSET_READY',flush=True)
if __name__=='__main__':main()

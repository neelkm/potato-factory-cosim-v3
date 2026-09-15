"""A physically loaded 18-potato carton shared by both native engines."""
import json
from usd_utils import *
from fmi_control import author
def main():
    s=Usd.Stage.CreateNew(str(OUT/'handoff_test.usda'));xform(s,'/World');s.SetDefaultPrim(s.GetPrimAtPath('/World'));UsdGeom.SetStageMetersPerUnit(s,1);UsdGeom.SetStageUpAxis(s,'Z');physics_scene(s)
    cube(s,'/World/Floor',(0,0,-.05),(3,3,.1),True)
    xform(s,'/World/Box_0',(0,0,.2));rigid(s.GetPrimAtPath('/World/Box_0'),.13)
    for i,(p,z) in enumerate([((0,0,.004),(.30,.22,.008)),((0,-.11,.09),(.30,.006,.18)),((0,.11,.09),(.30,.006,.18)),((-.15,0,.09),(.006,.22,.18)),((.15,0,.09),(.006,.22,.18))]):cube(s,f'/World/Box_0/Shape{i}',p,z,True)
    paths=['/World/Box_0'];members=[];joints={}
    for i in range(4):
        p=f'/World/Flap_0_{i}';position=((i%2-.5)*.15,(i//2-.5)*.11,.385)
        xform(s,p,position);rigid(s.GetPrimAtPath(p),.008);cube(s,p+'/Shape',(0,0,0),(.148,.108,.004),True)
        j=UsdPhysics.FixedJoint.Define(s,f'/World/Joints/Lid{i}');j.CreateBody0Rel().SetTargets(['/World/Box_0']);j.CreateBody1Rel().SetTargets([p]);j.CreateLocalPos0Attr(Gf.Vec3f(position[0],position[1],.185));j.CreateCollisionEnabledAttr(False)
        paths.append(p);members.append(p);joints[str(j.GetPath())]=dict(type='fixed',parent='/World/Box_0',child=p,sealed=True,parent_frame=[position[0],position[1],.185,0,0,0,1],child_frame=[0,0,0,0,0,0,1])
    for i in range(18):
        p=f'/World/Potato_{i:03d}';position=((i%3-1)*.077,((i//3)%3-1)*.061,.239+(i//9)*.052)
        xform(s,p,position);rigid(s.GetPrimAtPath(p),.076)
        shape=UsdGeom.Sphere.Define(s,p+'/Skin');shape.CreateRadiusAttr(1);shape.AddScaleOp().Set((.033,.023,.023));collision(shape.GetPrim());paths.append(p);members.append(p)
    author(s);s.GetRootLayer().Save();(OUT/'handoff_test.json').write_text(json.dumps(dict(paths=paths,membership={'/World/Box_0':members},joint_states=joints),indent=2))
    print('LOADED_CARTON_AUTHORED',len(paths),flush=True)
if __name__=='__main__':main()

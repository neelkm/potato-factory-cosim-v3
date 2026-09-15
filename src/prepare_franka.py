"""Author a metric FR3 Newton test scene and export joint frames for IK."""
from pathlib import Path
import json, math
from pxr import Usd,UsdGeom,UsdPhysics,Sdf,Gf
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
def main():
    src=Usd.Stage.Open(str(ROOT/'assets/franka_fr3/fr3.usd'))
    stage=Usd.Stage.CreateNew(str(OUT/'franka_test.usda'))
    UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,'Z')
    Sdf.CopySpec(src.Flatten(),'/fr3',stage.GetRootLayer(),'/World/Franka')
    for name in ['fr3_link8','fr3_hand','fr3_leftfinger','fr3_rightfinger','fr3_hand_tcp']:
        stage.RemovePrim('/World/Franka/'+name)
    stage.RemovePrim('/World/Franka/fr3_link7/fr3_joint8')
    tool=UsdGeom.Xform.Define(stage,'/World/Tool');UsdPhysics.RigidBodyAPI.Apply(tool.GetPrim())
    mass=UsdPhysics.MassAPI.Apply(tool.GetPrim());mass.CreateMassAttr(.35);mass.CreateCenterOfMassAttr(Gf.Vec3f(0,0,.06));mass.CreateDiagonalInertiaAttr(Gf.Vec3f(.0008,.0011,.0013))
    block=UsdGeom.Cube.Define(stage,'/World/Tool/Plate');block.CreateSizeAttr(1);block.AddTranslateOp().Set((0,0,.06));block.AddScaleOp().Set((.19,.14,.025));UsdPhysics.CollisionAPI.Apply(block.GetPrim())
    for i,(x,y) in enumerate([(-.06,-.04),(-.06,.04),(.06,-.04),(.06,.04)]):
        c=UsdGeom.Cylinder.Define(stage,f'/World/Tool/Cup{i}');c.CreateRadiusAttr(.025);c.CreateHeightAttr(.04);c.CreateAxisAttr('Z');c.AddTranslateOp().Set((x,y,.10));UsdPhysics.CollisionAPI.Apply(c.GetPrim())
        stem=UsdGeom.Cylinder.Define(stage,f'/World/Tool/Stem{i}');stem.CreateRadiusAttr(.012);stem.CreateHeightAttr(.014);stem.CreateAxisAttr('Z');stem.AddTranslateOp().Set((x,y,.076))
    j=UsdPhysics.FixedJoint.Define(stage,'/World/Franka/fr3_link7/VacuumMount');j.CreateBody0Rel().SetTargets(['/World/Franka/fr3_link7']);j.CreateBody1Rel().SetTargets(['/World/Tool']);j.CreateLocalPos0Attr(Gf.Vec3f(0,0,.107))
    # Resolve the manufacturer's zero-mass marker links explicitly. The fixed
    # base stays anchored by its authored world joint; marker links carry 1 g.
    joints=[];bodies=[]
    for p in list(stage.Traverse()):
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            mass=UsdPhysics.MassAPI(p);value=mass.GetMassAttr().Get()
            if value is None or value<=0:
                mass.CreateMassAttr(.001 if p.GetName()!='fr3_link0' else 1.)
                mass.CreateCenterOfMassAttr(Gf.Vec3f(0))
                mass.CreateDiagonalInertiaAttr(Gf.Vec3f(1e-6 if p.GetName()!='fr3_link0' else .01))
            bodies.append(str(p.GetPath()))
        if p.IsA(UsdPhysics.RevoluteJoint):
            j=UsdPhysics.RevoluteJoint(p)
            index=int(p.GetName()[-1])-1;home=[0,-.45,0,-1.95,0,1.55,.785][index]
            p.AddAppliedSchema('PhysicsJointStateAPI:angular')
            p.CreateAttribute('state:angular:physics:position',Sdf.ValueTypeNames.Float).Set(math.degrees(home))
            p.CreateAttribute('state:angular:physics:velocity',Sdf.ValueTypeNames.Float).Set(0.)
            d=UsdPhysics.DriveAPI.Apply(p,'angular');d.CreateStiffnessAttr(0);d.CreateDampingAttr(0);d.CreateTargetPositionAttr(math.degrees(home))
            frames=[]
            for pos,rot in [(j.GetLocalPos0Attr().Get(),j.GetLocalRot0Attr().Get()),(j.GetLocalPos1Attr().Get(),j.GetLocalRot1Attr().Get())]:
                frames.append([*map(float,pos),*map(float,rot.GetImaginary()),float(rot.GetReal())])
            joints.append(dict(path=str(p.GetPath()),axis=j.GetAxisAttr().Get(),frames=frames,limits=[math.radians(j.GetLowerLimitAttr().Get()),math.radians(j.GetUpperLimitAttr().Get())],parent=str(j.GetBody0Rel().GetTargets()[0]),child=str(j.GetBody1Rel().GetTargets()[0])))
    scene=UsdPhysics.Scene.Define(stage,'/World/Physics');scene.CreateGravityDirectionAttr(Gf.Vec3f(0,0,-1));scene.CreateGravityMagnitudeAttr(9.81)
    floor=UsdGeom.Cube.Define(stage,'/World/Floor');floor.CreateSizeAttr(1);floor.AddTranslateOp().Set((0,0,-.05));floor.AddScaleOp().Set((3,3,.1));UsdPhysics.CollisionAPI.Apply(floor.GetPrim())
    stage.GetRootLayer().Save();(OUT/'franka_kinematics.json').write_text(json.dumps(dict(joints=joints,bodies=bodies),indent=2))
    print('FRANKA_AUTHORED',len(bodies),len(joints),flush=True)
if __name__=='__main__':main()

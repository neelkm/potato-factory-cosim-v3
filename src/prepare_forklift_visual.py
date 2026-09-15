"""Preserve SimReady geometry/materials while separating the driven carriage.

This asset is used as a detailed visual shell. Factory actuation and cargo
contacts are supplied by the explicit PhysX bodies in the assembled stage.
"""
from pathlib import Path
from pxr import Usd,UsdGeom,UsdPhysics,Sdf,Gf
ROOT=Path(__file__).resolve().parents[1]
def main():
    src=Usd.Stage.Open(str(ROOT/'assets/forklift_blue_c01/sm_vehicle_forklift_blue_c01_01.usd'))
    while True:
        instances=[p for p in src.Traverse() if p.IsInstance()]
        if not instances:break
        for p in instances:p.SetInstanceable(False)
    out=ROOT/'assets/forklift_blue_c01/presentation.usdc';stage=Usd.Stage.CreateNew(str(out));UsdGeom.Xform.Define(stage,'/Assets');stage.SetDefaultPrim(stage.GetPrimAtPath('/Assets'));UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,'Z')
    flat=src.Flatten();Sdf.CopySpec(flat,'/RootNode',stage.GetRootLayer(),'/Assets/Forklift')
    stage.RemovePrim('/Assets/Forklift/Joints')
    moving=['sm_fork1_c01_obj_00','sm_fork2_c01_obj_00','sm_mast_stage2_c01_obj_00','sm_mast_stage3_c01_obj_00','sm_mast_stage4_c01_obj_00']
    UsdGeom.Xform.Define(stage,'/Assets/Forks');UsdGeom.Xform.Define(stage,'/Assets/Forks/Geometry')
    for name in moving:
        path='/Assets/Forklift/Geometry/'+name
        if stage.GetPrimAtPath(path):Sdf.CopySpec(stage.GetRootLayer(),path,stage.GetRootLayer(),'/Assets/Forks/Geometry/'+name);stage.RemovePrim(path)
    # Flatten makes texture identifiers absolute. Built-in MDL module names
    # remain renderer-resolved; all texture tiles live beside this file.
    for p in list(stage.Traverse()):
        if p.IsA(UsdPhysics.Joint):stage.RemovePrim(p.GetPath());continue
        for api in list(p.GetAppliedSchemas()):
            if any(x in api.lower() for x in ['physics','physx','articulation','rigidbody']):p.RemoveAppliedSchema(api)
        for a in list(p.GetAttributes()):
            if a.GetName().startswith(('physics:','physx','newton:')):p.RemoveProperty(a.GetName())
        for rel in p.GetRelationships():
            rel.SetTargets([Sdf.Path(str(t).replace('/RootNode','/Assets/Forklift')) for t in rel.GetTargets()])
    stage.GetRootLayer().Save();print('SIMREADY_PRESENTATION_READY',flush=True)
if __name__=='__main__':main()

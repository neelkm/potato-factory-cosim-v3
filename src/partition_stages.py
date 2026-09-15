"""One presentation stage with separate native-physics views for each engine."""
import math,json
from usd_utils import *
def assemble_partitions(s,manifest):
    from conveyor_collision_groups import author_conveyor_filters
    author_conveyor_filters(s,manifest)
    robot=Usd.Stage.Open(str(OUT/'franka_cell.usda'))
    for name in ['Franka','Tool']:Sdf.CopySpec(robot.GetRootLayer(),'/World/'+name,s.GetRootLayer(),'/World/'+name)
    # The editable Blender export also contains these visual meshes. Retain
    # one authoritative copy per USD link to avoid coincident surfaces.
    for name in ['Franka','Tool']:
        for p in reversed(list(Usd.PrimRange(s.GetPrimAtPath('/World/'+name)))):
            if not robot.GetPrimAtPath(p.GetPath()):p.SetActive(False)
    for p in s.Traverse():
        if str(p.GetPath()).startswith('/World/Franka/') and p.GetName()=='collisions':UsdGeom.Imageable(p).CreateVisibilityAttr('invisible')
        if p.HasAPI(UsdPhysics.CollisionAPI):
            attr(p,'newton:contactMargin','Float',.0005);attr(p,'newton:contactGap','Float',.002)
        if p.HasAPI(UsdPhysics.RigidBodyAPI):
            owned='newton' if str(p.GetPath()).startswith(('/World/Franka/','/World/Tool','/World/Pallet')) else 'physx'
            attr(p,'factory:initialOwner','String',owned)
    attr(s.GetPrimAtPath('/World'),'factory:physicsClockHz','Int',240)
    attr(s.GetPrimAtPath('/World'),'factory:controlClockHz','Int',30)
    cup_material=material(s,'/World/VacuumRubber',(.018,.024,.028),0,.6)
    plate_material=material(s,'/World/VacuumMetal',(.31,.35,.37),.7,.28)
    for p in s.GetPrimAtPath('/World/Tool').GetChildren():
        if p.GetName().startswith('Cup'):bind(p,cup_material)
        elif p.GetName()=='Plate' or p.GetName().startswith('Stem'):bind(p,plate_material)
    s.GetRootLayer().Save()
    physx=Usd.Stage.CreateNew(str(OUT/'factory_physx.usda'));physx.GetRootLayer().subLayerPaths=['factory.usda'];physx.SetDefaultPrim(physx.GetPrimAtPath('/World'))
    for name in ['Franka','Tool']:physx.OverridePrim('/World/'+name).SetActive(False)
    physx.GetRootLayer().Save()
    newton=Usd.Stage.CreateNew(str(OUT/'factory_newton.usda'));newton.GetRootLayer().subLayerPaths=['factory.usda'];newton.SetDefaultPrim(newton.GetPrimAtPath('/World'))
    keep={'Physics','Franka','Tool','Pallet','CartonBelt','CollisionProxies','Joints','_materials','Contact','CardContact','BeltContact','PolishedGuides','TruckContact'}
    for p in s.GetPrimAtPath('/World').GetChildren():
        name=p.GetName()
        if name not in keep and not name.startswith(('Potato_','Box_','Flap_')):newton.OverridePrim(p.GetPath()).SetActive(False)
    flap_map={f['name']:f for f in manifest['flaps']}
    for p in s.GetPrimAtPath('/World/Joints').GetChildren():
        if p.GetName() not in flap_map:newton.OverridePrim(p.GetPath()).SetActive(False)
        else:
            f=flap_map[p.GetName()];j=UsdPhysics.FixedJoint.Define(newton,p.GetPath());j.CreateLocalRot0Attr(Gf.Quatf(Gf.Rotation(Gf.Vec3d(1,0,0) if f['axis']=='X' else Gf.Vec3d(0,1,0),f['target']).GetQuat()))
    newton.GetRootLayer().Save()
    weights=sorted(p['mass'] for p in manifest['potatoes'] if not p['damaged'])
    worst=sum(weights[-20:])+.13+4*.008+.35
    if worst>3.:raise RuntimeError('Carton/tool exceed FR3 payload')
    report=dict(franka_payload_limit_kg=3.,vacuum_tool_mass_kg=.35,carton_and_lids_mass_kg=.162,worst_20_potato_payload_with_tool_kg=worst,potato_mass_range_kg=[min(p['mass'] for p in manifest['potatoes']),max(p['mass'] for p in manifest['potatoes'])],geometry_scale_from_v2=.4,box_dimensions_m=list(BOX_SIZE) if 'BOX_SIZE' in globals() else [.30,.22,.18])
    (OUT/'payload_validation.json').write_text(json.dumps(report,indent=2))

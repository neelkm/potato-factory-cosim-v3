"""Keep mounted conveyor components from acting as meshed friction gears.

Produce, water and cargo retain contact with every conveyor surface. Roller
bearings/joints carry hardware loads; neighbouring sleeves must not gear-lock
through their numerical contact margins or touch fixed guide/belt housings.
"""
from pxr import Usd,UsdPhysics

def author_conveyor_filters(stage,manifest):
    rollers=UsdPhysics.CollisionGroup.Define(stage,'/World/ConveyorFilters/Rollers')
    hardware=UsdPhysics.CollisionGroup.Define(stage,'/World/ConveyorFilters/MountedHardware')
    roller_shapes=['/World/'+r['name']+'/Collider' for r in manifest['rollers']]
    mounted=[]
    roots=['/World/CollisionProxies']+['/World/'+r['name'] for r in manifest['bodies'] if r.get('kinematic')]
    for root in roots:
        for prim in Usd.PrimRange(stage.GetPrimAtPath(root)):
            if prim.HasAPI(UsdPhysics.CollisionAPI):mounted.append(prim.GetPath())
    rollers.GetCollidersCollectionAPI().CreateIncludesRel().SetTargets(roller_shapes)
    hardware.GetCollidersCollectionAPI().CreateIncludesRel().SetTargets(mounted)
    rollers.CreateFilteredGroupsRel().SetTargets([rollers.GetPath(),hardware.GetPath()])
    hardware.CreateFilteredGroupsRel().SetTargets([rollers.GetPath()])

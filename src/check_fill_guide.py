"""Native queue-release fixture for lateral containment at the belt lip."""
import argparse,hashlib,json,math
import numpy as np
from scipy.spatial.transform import Rotation
from pxr import Usd,UsdPhysics
import ovstage
from config import OUT
from conveyor_control import TerminalBeltDrive
from physx_engine import PhysXEngine
from mechanics import Mechanics
from ovphysx.types import TensorType

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--legacy',action='store_true');args=parser.parse_args()
    fixture_path=OUT/'qualification/fill_guide/fixture.json'
    if not fixture_path.exists():
        cache=OUT/'diagnostic_fill_guide';names=json.loads((cache/'paths.json').read_text());record=np.load(cache/'poses.npy',mmap_mode='r')
        frame=round(366.7*30);snapshot=record[frame].copy();previous=record[frame-1].copy()
        potatoes=[p for i,p in enumerate(names) if 'Potato_' in p and 6.4<snapshot[i,0]<8.3 and abs(snapshot[i,1])<.3 and snapshot[i,2]>1.12]
        bodies=['/World/Box_4']+[f'/World/Flap_4_{j}' for j in range(4)]+potatoes;initial={}
        for path in bodies:
            i=names.index(path);velocity=(snapshot[i,:3]-previous[i,:3])*30
            omega=(Rotation.from_quat(snapshot[i,3:])*Rotation.from_quat(previous[i,3:]).inv()).as_rotvec()*30
            initial[path]=dict(pose=snapshot[i].tolist(),velocity=[*velocity.tolist(),*omega.tolist()])
        fixture=dict(bodies=bodies,potatoes=potatoes,initial=initial,source_frame=frame,source_cache='diagnostic_fill_guide',source_simulation_sha256=hashlib.sha256((cache/'simulation.json').read_bytes()).hexdigest())
        fixture_path.parent.mkdir(parents=True,exist_ok=True);fixture_path.write_text(json.dumps(fixture,indent=2))
    fixture=json.loads(fixture_path.read_text());bodies=fixture['bodies'];potatoes=fixture['potatoes'];start=fixture['source_frame']/30
    stage=Usd.Stage.CreateNew(str(OUT/'fill_guide_probe.usda'));stage.GetRootLayer().subLayerPaths=['factory_physx.usda']
    retained=bodies+['/World/FillGate','/World/OutputBelt','/World/CartonBelt','/World/Vibrating_Packing_lane']
    for prim in list(stage.GetPrimAtPath('/World').GetChildren()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and str(prim.GetPath()) not in retained:stage.OverridePrim(prim.GetPath()).SetActive(False)
        if prim.GetTypeName() in ('PhysxParticleSystem','PhysxParticleSet','FmuInstance'):stage.OverridePrim(prim.GetPath()).SetActive(False)
    for prim in list(stage.GetPrimAtPath('/World/Joints').GetChildren()):
        if not str(prim.GetPath()).startswith('/World/Joints/Flap_4_'):stage.OverridePrim(prim.GetPath()).SetActive(False)
    stage.OverridePrim('/World/Water').SetActive(False)
    length=1.0 if args.legacy else 1.18;center=6.6+length/2
    manifest=json.loads((OUT/'manifest.json').read_text())
    guide_index=next(i for i,r in enumerate(manifest['static']) if r['name']=='Packing_lane' and r['pos'][1]<0)
    negative=stage.GetPrimAtPath(f'/World/CollisionProxies/C{guide_index:03}');negative.GetAttribute('xformOp:translate').Set((center,-.052,1.6));negative.GetAttribute('xformOp:scale').Set((length,.022,.20))
    positive=stage.GetPrimAtPath('/World/Vibrating_Packing_lane');positive.GetAttribute('xformOp:translate').Set((center,.052+.006*math.sin(start*2*math.pi*3),1.6))
    stage.GetPrimAtPath('/World/Vibrating_Packing_lane/Collider0').GetAttribute('xformOp:scale').Set((length,.022,.20))
    for p in potatoes:stage.GetPrimAtPath(p).GetAttribute('physxRigidBody:angularDamping').Set(.25)
    stage.GetRootLayer().Save();stage=None
    engine=PhysXEngine(str(OUT/'fill_guide_probe.usda'),inactive=bodies);dictionary=None;query=None
    try:
        states=engine.export_state(bodies)
        for row in states:row.update(fixture['initial'][row['path']])
        engine.import_state(states);engine.set_active(bodies,True);mechanics=Mechanics(engine.px)
        for path in bodies:mechanics.tune(path)
        dictionary=ovstage.PathDictionary(engine.stage);pl=dictionary.create_path_list_from_strings(['/World/OutputBelt']);query=engine.stage.query_from_path_list(pl);dictionary.destroy_path_list(pl)
        trajectory=[];ordinal=1;drive=TerminalBeltDrive();drive.speed=.036
        for frame in range(180):
            speed=drive.update(1/30,ready=True,gripped=False);ordinal+=1;values=np.array([[speed,0,0]],np.float32)
            tensor=ovstage.make_dltensor(values,dtype=ovstage.DLDataType(ovstage.DLDataTypeCode.kDLFloat,32,3),shape=[1],ndim=1)
            engine.stage.write_attribute(query,'physxSurfaceVelocity:surfaceVelocity',ordinal,tensor,is_array=False).wait();engine.stage.advance_write_floor(ordinal).wait();engine.px.update_from_ovstage(ordinal,ordinal)
            for substep in range(8):
                now=start+(frame*8+substep+1)/240
                mechanics.target('/World/FillGate',[7.61,0,1.28])
                mechanics.target('/World/Vibrating_Packing_lane',[center,.052+.006*math.sin(now*2*math.pi*3),1.6])
                engine.advance()
            poses=engine.read(bodies,TensorType.RIGID_BODY_POSE);trajectory.append(poses.copy())
        box=poses[0];relative=Rotation.from_quat(box[3:]).inv().apply(poses[5:,:3]-box[:3])
        inside=(abs(relative[:,0])<.154)&(abs(relative[:,1])<.114)&(relative[:,2]>.009)&(relative[:,2]<.195)
        escaped=[p for p,ok in zip(potatoes,inside) if not ok];success=not escaped
        report=dict(passed=not success if args.legacy else success,physical_success=success,expected_failure=args.legacy,potatoes=len(potatoes),retained=int(sum(inside)),escaped=escaped,
                    final_positions={p:row[:3].tolist() for p,row in zip(potatoes,poses[5:])},guide_end_m=center+length/2,fixture_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
                    scope='Isolated native queue release, initialized from recorded poses and estimated velocities. Fixed input fixture, not a restored solver state or full production batch.')
        suffix='legacy' if args.legacy else 'extended';(OUT/f'fill_guide_{suffix}_validation.json').write_text(json.dumps(report,indent=2));np.save(OUT/f'fill_guide_{suffix}_poses.npy',trajectory);print(json.dumps(report,indent=2),flush=True)
        if not report['passed']:raise RuntimeError('Filling guide qualification failed')
    finally:
        if query is not None:engine.stage.release_query(query).wait()
        if dictionary is not None:dictionary.destroy()
        engine.close()

if __name__=='__main__':main()

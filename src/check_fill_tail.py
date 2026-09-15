"""Native terminal-belt fixture reconstructed from a failed fill recording.

Poses and estimated velocities initialize this isolated test. Hidden solver/FMU
state is not restored; this is a controlled fixture, not a resumed batch.
"""
import argparse,json,math,hashlib
import numpy as np
from scipy.spatial.transform import Rotation
from pxr import Usd,UsdPhysics
import ovstage
from config import OUT
from physx_engine import PhysXEngine
from mechanics import Mechanics
from line_simulation import smooth
from conveyor_control import TerminalBeltDrive
from ovphysx.types import TensorType

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stop',action='store_true');args=parser.parse_args()
    fixture_path=OUT/'qualification/fill_tail/fixture.json'
    if not fixture_path.exists():
        cache=OUT/'diagnostic_fill_tail';names=json.loads((cache/'paths.json').read_text());record=np.load(cache/'poses.npy',mmap_mode='r')
        frame=round(254.*30);snapshot=record[frame].copy();previous=record[frame-1].copy()
        potatoes=[p for i,p in enumerate(names) if 'Potato_' in p and 7.1<snapshot[i,0]<8.15 and abs(snapshot[i,1])<.3 and snapshot[i,2]>1.1]
        bodies=['/World/Box_2']+[f'/World/Flap_2_{j}' for j in range(4)]+potatoes
        initial={}
        for path in bodies:
            i=names.index(path);velocity=(snapshot[i,:3]-previous[i,:3])*30
            omega=(Rotation.from_quat(snapshot[i,3:])*Rotation.from_quat(previous[i,3:]).inv()).as_rotvec()*30
            initial[path]=dict(pose=snapshot[i].tolist(),velocity=[*velocity.tolist(),*omega.tolist()])
        fixture=dict(bodies=bodies,potatoes=potatoes,initial=initial,source_frame=frame,source_cache='diagnostic_fill_tail',source_simulation_sha256=hashlib.sha256((cache/'simulation.json').read_bytes()).hexdigest())
        fixture_path.parent.mkdir(parents=True,exist_ok=True);fixture_path.write_text(json.dumps(fixture,indent=2))
    fixture=json.loads(fixture_path.read_text());bodies=fixture['bodies'];potatoes=fixture['potatoes'];frame=fixture['source_frame']
    stage=Usd.Stage.CreateNew(str(OUT/'fill_tail_probe.usda'));stage.GetRootLayer().subLayerPaths=['factory_physx.usda']
    for prim in list(stage.GetPrimAtPath('/World').GetChildren()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and str(prim.GetPath()) not in bodies+['/World/FillGate','/World/OutputBelt','/World/CartonBelt']:stage.OverridePrim(prim.GetPath()).SetActive(False)
        if prim.GetTypeName() in ('PhysxParticleSystem','PhysxParticleSet','FmuInstance'):stage.OverridePrim(prim.GetPath()).SetActive(False)
    for prim in list(stage.GetPrimAtPath('/World/Joints').GetChildren()):
        if not str(prim.GetPath()).startswith('/World/Joints/Flap_2_'):stage.OverridePrim(prim.GetPath()).SetActive(False)
    # Hold the original short guide fixed to isolate the terminal-drive fix
    # from the later, separately qualified lateral-containment extension.
    manifest=json.loads((OUT/'manifest.json').read_text())
    guide_index=next(i for i,r in enumerate(manifest['static']) if r['name']=='Packing_lane' and r['pos'][1]<0)
    guide=stage.GetPrimAtPath(f'/World/CollisionProxies/C{guide_index:03}')
    guide.GetAttribute('xformOp:translate').Set((7.1,-.052,1.6));guide.GetAttribute('xformOp:scale').Set((1.0,.022,.20))
    stage.OverridePrim('/World/Water').SetActive(False);stage.GetRootLayer().Save();stage=None
    engine=PhysXEngine(str(OUT/'fill_tail_probe.usda'),inactive=bodies);dictionary=None;query=None
    try:
        states=engine.export_state(bodies)
        for row in states:
            row.update(fixture['initial'][row['path']])
        engine.import_state(states);engine.set_active(bodies,True);mechanics=Mechanics(engine.px)
        for path in bodies:mechanics.tune(path)
        dictionary=ovstage.PathDictionary(engine.stage);pl=dictionary.create_path_list_from_strings(['/World/OutputBelt']);query=engine.stage.query_from_path_list(pl);dictionary.destroy_path_list(pl)
        trajectory=[];gate_start=253.3666666667-frame/30;full=253.6666666667-frame/30;ordinal=1;drive=TerminalBeltDrive()
        for f in range(150):
            t=f/30
            speed=max(0.,.9-1.08*max(0.,t-gate_start)) if args.stop else drive.update(1/30,ready=True,gripped=False,packing_elapsed=t-full)
            ordinal+=1;values=np.array([[speed,0,0]],np.float32)
            tensor=ovstage.make_dltensor(values,dtype=ovstage.DLDataType(ovstage.DLDataTypeCode.kDLFloat,32,3),shape=[1],ndim=1)
            engine.stage.write_attribute(query,'physxSurfaceVelocity:surfaceVelocity',ordinal,tensor,is_array=False).wait();engine.stage.advance_write_floor(ordinal).wait();engine.px.update_from_ovstage(ordinal,ordinal)
            for s in range(8):
                now=(f*8+s+1)/240
                mechanics.target('/World/FillGate',[7.61,0,min(1.6,1.28+.65*max(0,now-gate_start))])
                for j,target in enumerate([-90,90,90,-90]):mechanics.fold(f'/World/Joints/Flap_2_{j}','X' if j<2 else 'Y',math.radians(target)*smooth((now-full-(.9 if j>=2 else 1.8))/.8))
                engine.advance()
            poses=engine.read(bodies,TensorType.RIGID_BODY_POSE);trajectory.append(poses.copy())
        box=poses[0];relative=Rotation.from_quat(box[3:]).inv().apply(poses[5:,:3]-box[:3])
        inside=(abs(relative[:,0])<.154)&(abs(relative[:,1])<.114)&(relative[:,2]>.009)&(relative[:,2]<.195)
        escaped=[p for p,ok in zip(potatoes,inside) if not ok];physical_success=not escaped
        report=dict(passed=not physical_success if args.stop else physical_success,physical_success=physical_success,expected_failure=args.stop,
                    potatoes=len(potatoes),retained=int(sum(inside)),escaped=escaped,final_positions={p:row[:3].tolist() for p,row in zip(potatoes,poses[5:])},
                    source_cache=fixture['source_cache'],source_frame=frame,source_seconds=frame/30,fixture_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
                    controlled_guide_end_m=7.6,
                    scope='Isolated native filling fixture initialized from recorded poses and finite-difference velocity estimates; not a restored solver state or full factory run.')
        suffix='stop' if args.stop else 'clear';(OUT/f'fill_tail_{suffix}_validation.json').write_text(json.dumps(report,indent=2));np.save(OUT/f'fill_tail_{suffix}_poses.npy',trajectory)
        print(json.dumps(report,indent=2),flush=True)
        if not report['passed']:raise RuntimeError('Terminal belt fixture failed')
    finally:
        if query is not None:engine.stage.release_query(query).wait()
        if dictionary is not None:dictionary.destroy()
        engine.close()

if __name__=='__main__':main()

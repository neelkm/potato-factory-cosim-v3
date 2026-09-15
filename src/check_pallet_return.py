"""Replay a measured loaded-pallet return in an isolated native PhysX scene."""
import argparse,json,math
import numpy as np
from scipy.spatial.transform import Rotation
from pxr import Usd,UsdPhysics
from config import OUT
from physx_engine import PhysXEngine
from mechanics import Mechanics
from forklift_motion import ForkliftMotion
from state_protocol import continuity
from ovphysx.types import TensorType

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--cache',default='cache');parser.add_argument('--nominal',action='store_true');args=parser.parse_args()
    run=json.loads((OUT/args.cache/'simulation.json').read_text());event=next(e for e in reversed(run['ownership_events']) if e['destination']=='physx')
    states=event['states'];paths=[r['path'] for r in states];index={p:i for i,p in enumerate(paths)}
    stage=Usd.Stage.CreateNew(str(OUT/'pallet_return_probe.usda'));stage.GetRootLayer().subLayerPaths=['factory_physx.usda']
    for prim in list(stage.GetPrimAtPath('/World').GetChildren()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and str(prim.GetPath()) not in paths+['/World/Forklift','/World/Forks']:stage.OverridePrim(prim.GetPath()).SetActive(False)
        if prim.GetTypeName() in ('PhysxParticleSystem','PhysxParticleSet','FmuInstance'):stage.OverridePrim(prim.GetPath()).SetActive(False)
    for prim in list(stage.GetPrimAtPath('/World/Joints').GetChildren()):
        if str(prim.GetPath()) not in event['joint_states']:stage.OverridePrim(prim.GetPath()).SetActive(False)
    stage.OverridePrim('/World/Water').SetActive(False)
    stage.GetRootLayer().Save();stage=None
    engine=PhysXEngine(str(OUT/'pallet_return_probe.usda'),inactive=paths);frames=[];checks=[]
    try:
        engine.import_state(states);engine.set_active(paths,True);residual=continuity(states,engine.export_state(paths));native=Mechanics(engine.px)
        for path in paths:native.tune(path)
        for k in range(6):
            for j,target in enumerate([-90,90,90,-90]):native.fold(f'/World/Joints/Flap_{k}_{j}','X' if j<2 else 'Y',math.radians(target))
        pallet=next(r['pose'] for r in states if r['path']=='/World/Pallet')
        motion=ForkliftMotion([8.17,-1.02,.62,0,0,0,1] if args.nominal else pallet)
        for frame in range(1624):
            for substep in range(8):
                t=(frame*8+substep+1)/240;p,fork,yaw=motion.targets(t);q=[0,0,math.sin(yaw/2),math.cos(yaw/2)]
                native.target('/World/Forklift',p,q);native.target('/World/Forks',fork,q);engine.advance()
            pose=engine.read(paths,TensorType.RIGID_BODY_POSE)
            if frame%3==0:frames.append(pose.copy())
            counts=[]
            for k in range(6):
                box=pose[index[f'/World/Box_{k}']];points=pose[[index[p] for p in run['boxes'][k]],:3]
                relative=Rotation.from_quat(box[3:]).inv().apply(points-box[:3])
                counts.append(int(np.sum((abs(relative[:,0])<.154)&(abs(relative[:,1])<.114)&(relative[:,2]>.009)&(relative[:,2]<.195))))
            good=counts==[len(b) for b in run['boxes']]
            checks.append(good)
            if frame%150==0 or not good:print('PALLET_PROBE',round((frame+1)/30,2),counts,pose[index['/World/Pallet'],:3].tolist(),flush=True)
            if not good:break
        final=pose[index['/World/Pallet'],:3];arrived=np.linalg.norm(final[:2]-[13,-6.49])<.20 and abs(final[2])<.05
        physical_success=bool(all(checks) and arrived)
        report=dict(passed=not physical_success if args.nominal else physical_success,physical_success=physical_success,expected_failure=args.nominal,
                    seconds=(frame+1)/30,carton_counts=counts,expected_counts=[len(b) for b in run['boxes']],
                    alignment=motion.describe(),native_transfer_continuity=residual,pallet_final=final.tolist(),source_cache=args.cache,
                    source_return_digest=event['digest'],scope='Isolated native forklift qualification initialized from the saved complete return packet; this is not a resumed full factory run.')
        suffix='nominal' if args.nominal else 'aligned';(OUT/f'pallet_return_{suffix}_validation.json').write_text(json.dumps(report,indent=2))
        np.save(OUT/f'pallet_return_{suffix}_poses.npy',frames);print(json.dumps(report,indent=2),flush=True)
        if not report['passed']:raise RuntimeError('Loaded-pallet forklift qualification failed')
    finally:engine.close()
if __name__=='__main__':main()

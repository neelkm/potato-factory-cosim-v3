"""Capture an isolated native replay of the real loaded-pallet return packet.

The production run is never overwritten. This is a qualified reproduction,
not a claim to have recorded contacts during the historical factory run.
"""
import argparse, hashlib, json, math, msvcrt, time
from pathlib import Path
import numpy as np
from pxr import Usd, UsdPhysics, Sdf
from config import OUT
from physx_engine import PhysXEngine
from mechanics import Mechanics
from forklift_motion import ForkliftMotion
from state_protocol import continuity
from ovphysx.types import TensorType

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=16);parser.add_argument('--ovd',action='store_true')
    args=parser.parse_args();base=OUT/'physics_debug';base.mkdir(exist_ok=True)
    recording=base/('capture_'+time.strftime('%Y%m%d_%H%M%S'));recording.mkdir()
    lock=(OUT/'simulation.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    source=OUT/'cache/simulation.json';run=json.loads(source.read_text())
    event=next(e for e in reversed(run['ownership_events']) if e['destination']=='physx')
    states=event['states'];paths=[r['path'] for r in states];actors=paths+['/World/Forklift','/World/Forks']
    stage=Usd.Stage.CreateNew(str(recording/'scene.usda'));stage.GetRootLayer().subLayerPaths=['../../factory_physx.usda']
    for prim in list(stage.GetPrimAtPath('/World').GetChildren()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and str(prim.GetPath()) not in actors:stage.OverridePrim(prim.GetPath()).SetActive(False)
        if prim.GetTypeName() in ('PhysxParticleSystem','PhysxParticleSet','FmuInstance'):stage.OverridePrim(prim.GetPath()).SetActive(False)
    for prim in list(stage.GetPrimAtPath('/World/Joints').GetChildren()):
        if str(prim.GetPath()) not in event['joint_states']:stage.OverridePrim(prim.GetPath()).SetActive(False)
    stage.OverridePrim('/World/Water').SetActive(False)
    for path in ['/World/Pallet','/World/Forks']:
        prim=stage.OverridePrim(path);prim.AddAppliedSchema('PhysxContactReportAPI')
        prim.CreateAttribute('physxContactReport:threshold',Sdf.ValueTypeNames.Float).Set(0.)
    stage.GetRootLayer().Save();stage=None
    engine=None;contact=None
    try:
        engine=PhysXEngine(str(recording/'scene.usda'),inactive=paths,recording_directory=recording if args.ovd else None)
        before=engine.read(paths,TensorType.RIGID_BODY_DISABLE_SIMULATION).tolist()
        engine.import_state(states);engine.set_active(paths,True)
        after=engine.read(paths,TensorType.RIGID_BODY_DISABLE_SIMULATION).tolist()
        imported=engine.export_state(paths);residual=continuity(states,imported)
        native=Mechanics(engine.px)
        for path in paths:native.tune(path)
        for k in range(6):
            for j,target in enumerate([-90,90,90,-90]):native.fold(f'/World/Joints/Flap_{k}_{j}','X' if j<2 else 'Y',math.radians(target))
        motion=ForkliftMotion(next(r['pose'] for r in states if r['path']=='/World/Pallet'))
        contact=engine.px.create_contact_binding(sensor_patterns=['/World/Pallet','/World/Forks'],max_contact_data_count=16384)
        sensor_paths=contact.sensor_paths;capacity=contact.max_contact_data_count
        force=np.zeros((capacity,1),np.float32);positions=np.zeros((capacity,3),np.float32);normals=np.zeros_like(positions)
        separations=np.zeros_like(force);counts=np.zeros(contact.sensor_count,np.uint32);starts=np.zeros_like(counts);other=np.zeros(capacity,np.uint64)
        poses=[];velocities=[];contact_rows=[];contact_offsets=[0];other_paths={};contacts_paths=[]
        for tick in range(round(args.seconds*240)+1):
            if tick:
                p,fork,yaw=motion.targets(tick/240);q=[0,0,math.sin(yaw/2),math.cos(yaw/2)]
                native.target('/World/Forklift',p,q);native.target('/World/Forks',fork,q);engine.advance()
            poses.append(engine.read(actors,TensorType.RIGID_BODY_POSE));velocities.append(engine.read(actors,TensorType.RIGID_BODY_VELOCITY))
            if tick:
                contact.read_raw_contact_data(force,positions,normals,separations,counts,starts,other)
                for sensor,(count,start) in enumerate(zip(counts,starts)):
                    for row in range(int(start),int(start+count)):
                        oid=int(other[row])
                        if oid not in other_paths:
                            name=contact.get_other_actor_paths_from_ids(np.asarray([oid],np.uint64))[0]
                            if not name:raise RuntimeError('Unresolved contact actor')
                            if name not in contacts_paths:contacts_paths.append(name)
                            other_paths[oid]=contacts_paths.index(name)
                        # Tensor API returns normal force averaged over dt. Store
                        # the equivalent normal impulse, not instantaneous force.
                        contact_rows.append([*positions[row],*normals[row],float(separations[row,0]),float(force[row,0])/240,sensor,other_paths[oid]])
            contact_offsets.append(len(contact_rows))
            if tick%480==0:print('DEBUG_CAPTURE',tick,round(tick/240,3),flush=True)
        np.savez_compressed(recording/'motion.npz',poses=poses,velocities=velocities,contacts=np.asarray(contact_rows,np.float32).reshape(-1,10),contact_offsets=contact_offsets)
        report=dict(schema=1,scope='Isolated native PhysX reproduction from the production Newton return packet; not the historical full factory run.',
                    hz=240,steps=len(poses)-1,source_time=event['tick']/240,paths=actors,
                    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),event=event,imported=imported,
                    alignment=motion.describe(),continuity=residual,disabled_before=before,disabled_after=after,
                    contact_source='ovphysx ContactBinding.read_raw_contact_data',sensor_paths=sensor_paths,contact_actor_paths=contacts_paths,
                    contact_columns=['x','y','z','nx','ny','nz','separation_m','normal_impulse_Ns','sensor_index','other_actor_index'])
        (recording/'capture.json').write_text(json.dumps(report,indent=2))
    finally:
        if contact:contact.destroy()
        if engine:engine.close()
        lock.close()
    files=list(recording.glob('*.ovd'))
    if args.ovd:assert files,'OVD capture was not finalized'
    (base/'latest_capture.json').write_text(json.dumps({'directory':str(recording),'ovd':str(files[0]) if files else None},indent=2))
    print('DEBUG_CAPTURE_COMPLETE',recording,'contacts',len(contact_rows),flush=True)

if __name__=='__main__':main()

"""Actual GPU PhysX → Newton → PhysX loaded-carton roundtrip, gated by ovfmi."""
from pathlib import Path
import json,time,numpy as np
from engine_process import EngineProcess
from coordinator import Coordinator
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
def main():
    start=time.perf_counter();m=json.loads((OUT/'handoff_test.json').read_text());paths=m['paths'];engines={};report={}
    try:
        for name in ['physx','newton']:
            engines[name]=EngineProcess(name);print('WORKER_CONNECTED',name,flush=True)
            args=dict(source=(OUT/'handoff_test.usda').as_posix(),inactive=paths if name=='newton' else [])
            if name=='physx':args['fmi']=True
            print('LOADED',engines[name].call('load',**args),flush=True)
        c=Coordinator(engines,{p:'physx' for p in paths})
        standby=engines['newton'].call('export_state',paths=paths)
        for _ in range(30):
            engines['physx'].call('control',presence=0,boxCount=0,boxReady=1,armBusy=0,palletCount=0,targetCount=18)
            c.advance(steps=8)
        standby_after=engines['newton'].call('export_state',paths=paths)
        frozen_error=max(float(np.max(np.abs(np.array(a['pose'])-b['pose']))) for a,b in zip(standby,standby_after))
        print('INACTIVE_ERROR',frozen_error,flush=True)
        print('INACTIVE_MOVERS',[(a['path'],float(np.max(np.abs(np.array(a['pose'])-b['pose'])))) for a,b in zip(standby,standby_after) if np.max(np.abs(np.array(a['pose'])-b['pose']))>1e-7],flush=True)
        fmi=engines['physx'].call('control',presence=0,boxCount=18,boxReady=1,armBusy=0,palletCount=0,targetCount=18)
        print('FMU_OUTPUT',fmi,flush=True)
        if fmi['packRequest']<.5:raise RuntimeError('FMU did not request a full carton')
        first=c.transfer(paths,'physx','newton',m['membership'],m['joint_states']);print('TRANSFER_TO_NEWTON',first,flush=True)
        before=engines['newton'].call('export_state',paths=paths);c.advance(steps=240);after=engines['newton'].call('export_state',paths=paths)
        second=c.transfer(paths,'newton','physx',m['membership'],m['joint_states']);print('TRANSFER_TO_PHYSX',second,flush=True)
        c.advance(steps=240);final=engines['physx'].call('export_state',paths=paths)
        box=np.array(final[0]['pose'][:3]);potatoes=[r for r in final if 'Potato' in r['path']]
        contained=int(sum(abs(r['pose'][0]-box[0])<.15 and abs(r['pose'][1]-box[1])<.11 and .008<r['pose'][2]-box[2]<.18 for r in potatoes))
        motion=max(float(np.linalg.norm(np.array(a['pose'][:3])-b['pose'][:3])) for a,b in zip(before,after))
        checks=dict(inactive_newton_frozen=frozen_error<1e-7,fmi_pack_interlock=fmi['packRequest']>.5,all_bodies_roundtripped=len(final)==23,all_potatoes_retained=contained==18,quiet_newton_settle=motion<.025,two_atomic_transfers=len(c.events)==2,returned_owner=all(v=='physx' for v in c.owners.values()))
        report=dict(checks=checks,passed=all(checks.values()),events=c.events,fmi=fmi,inactive_pose_error=frozen_error,newton_settle_displacement=motion,contained=contained,final=final,seconds=time.perf_counter()-start)
        print('HANDOFF_CHECKS',checks,flush=True)
    finally:
        for e in engines.values():e.close()
        if report:(OUT/'handoff_validation.json').write_text(json.dumps(report,indent=2))
    if not report.get('passed'):raise RuntimeError('Loaded-carton handoff validation failed')
if __name__=='__main__':main()

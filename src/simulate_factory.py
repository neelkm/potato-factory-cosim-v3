"""Run the native PhysX/FMI line and Newton/FR3 cell on one ownership clock."""
import argparse,json,time,os,traceback
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from engine_process import EngineProcess
from coordinator import Coordinator
from robot_cycle import RobotCycle
from config import OUT,BOX_SIZE
from framework.graph import FactoryGraph
from framework.profiles import get_profile
from framework.files import atomic_json

def classify(manifest,paths,pose,washed):
    rows=[];index={p:i for i,p in enumerate(paths)}
    for potato in manifest['potatoes']:
        path='/World/'+potato['name'];xyz=pose[index[path],:3];x,y,z=xyz;location='line'
        if 3.515<x<4.565 and -2.525<y<-1.275 and z<.75:location='discard'
        elif z<.3:location='floor'
        for k in range(6):
            box=pose[index[f'/World/Box_{k}']];rel=Rotation.from_quat(box[3:]).inv().apply(xyz-box[:3])
            if abs(rel[0])<BOX_SIZE[0]/2+.004 and abs(rel[1])<BOX_SIZE[1]/2+.004 and .009<rel[2]<BOX_SIZE[2]+.015:
                location=f'box_{k}';break
        rows.append(dict(potato=path,damaged=potato['damaged'],washed=path in washed,position=xyz.tolist(),location=location))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=1800);ap.add_argument('--cache',default='cache');ap.add_argument('--stop-after-cartons',type=int);ap.add_argument('--newton-iterations',type=int,default=32)
    ap.add_argument('--profile',choices=['production','simple_controls','diagnostic_rpc'],default='production')
    ap.add_argument('--qualification',action='store_true',help='Allow an intentionally incomplete short native run')
    args=ap.parse_args();profile=get_profile(args.profile)
    dest=OUT/args.cache;dest.mkdir(exist_ok=False)
    # The GPU PhysX library is process-global; prevent two app reruns competing.
    import msvcrt
    lock=(OUT/'simulation.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    try:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:raise RuntimeError('Another co-simulation run is already active')
    manifest=json.loads((OUT/'manifest.json').read_text());engines={};control=None;graph=None;failure=None;poses=water=None;used=0;report={};cycle=None;robot_events=[];requests=[];peak={};start=time.perf_counter();returned=False
    try:
        for name in ['physx','newton']:engines[name]=EngineProcess(name)
        pd=engines['physx'].call('load',source='factory_physx.usda',factory=True,external_control=True)
        standby=['/World/'+p['name'] for p in manifest['potatoes']]+['/World/'+p['name'] for p in manifest['bodies'] if p['name'].startswith(('Box_','Flap_'))]
        nd=engines['newton'].call('load',source=str(OUT/'factory_newton.usda'),inactive=standby,iterations=args.newton_iterations,robot=True)
        robot_paths=[p for p in nd['paths'] if p.startswith('/World/Franka/') or p=='/World/Tool']
        owners={p:'physx' for p in pd['paths']};owners.update({p:'newton' for p in robot_paths+['/World/Pallet']});c=Coordinator(engines,owners)
        control=EngineProcess('fmi');fd=control.call('load',backend=profile.controller)
        if profile.transport=='shared_memory':
            engines['physx'].configure_snapshot(pd['paths'],2592)
            engines['newton'].configure_snapshot(nd['paths'])
        graph=FactoryGraph(c,control,profile)
        paths=sorted(owners);index={p:i for i,p in enumerate(paths)};(dest/'paths.json').write_text(json.dumps(paths));(dest/'initial_owners.json').write_text(json.dumps(owners,indent=2))
        n=int(args.seconds*30)+1
        poses=np.lib.format.open_memmap(dest/'poses.npy',mode='w+',dtype=np.float32,shape=(n,len(paths),7));water=np.lib.format.open_memmap(dest/'water.npy',mode='w+',dtype=np.float32,shape=(n,2592,3));counts=np.zeros(n,np.int32)
        def capture():
            nonlocal used
            pc=engines['physx'].capture('capture');nc=engines['newton'].capture('publish');frame=np.full((len(paths),7),np.nan,np.float32)
            for name,cache in [('physx',pc),('newton',nc)]:
                for p,q in zip(cache['paths'],cache['poses']):
                    if c.owners.get(p)==name:frame[index[p]]=q
            if not np.isfinite(frame).all():raise RuntimeError('Non-finite owner transforms')
            for event in c.events:
                if event['tick']!=c.tick:continue
                for state in event['states']:
                    got=frame[index[state['path']]];expected=np.asarray(state['pose'])
                    if np.linalg.norm(got[:3]-expected[:3])>2e-5 or min(np.linalg.norm(got[3:]-expected[3:]),np.linalg.norm(got[3:]+expected[3:]))>2e-5:
                        raise RuntimeError('Captured owner pose differs from committed transfer: '+state['path'])
            poses[used]=frame;count=len(pc['water']);water[used,:count]=pc['water'];counts[used]=count;used+=1
            return pc['status']
        status=capture();print('COSIM_STARTED',dict(bodies=len(paths),newton_bodies=len(nd['paths'])),flush=True)
        for frame in range(1,n):
            if frame%30==0 and (dest/'stop.request').exists():raise RuntimeError('Simulation stopped by the user')
            t=c.tick/240
            if cycle:cycle.before_step(t)
            graph.step();t=c.tick/240
            if cycle:
                cycle.after_step(t)
                if cycle.finished:
                    robot_events.extend(cycle.events);engines['physx'].call('carton_placed');print('CARTON_PLACED',cycle.box,'time',t,flush=True);cycle=None
            status=engines['physx'].call('status')
            if status['handoff_ready'] and cycle is None:
                request=engines['physx'].call('transfer_request')
                if request['mass']+.35>3.:raise RuntimeError('Measured FR3 payload exceeds 3 kg including tool')
                snapshot=dict(tick=c.tick,request=request,states=engines['physx'].call('export_state',paths=request['paths']))
                (dest/f'carton_{request["box"]}_handoff.json').write_text(json.dumps(snapshot,indent=2))
                event=c.transfer(request['paths'],'physx','newton',request['membership'],request['joint_states']);requests.append(request);engines['physx'].call('carton_transferred')
                cycle=RobotCycle(engines['newton'],manifest,request,t);print('CARTON_HANDOFF',request['box'],request['potatoes'],request['mass'],event['continuity'],flush=True)
            if status['pallet']==6 and cycle is None and not returned:
                group=['/World/Pallet']+[p for request in requests for p in request['paths']]
                states=engines['newton'].call('export_state',paths=group)
                if max(np.linalg.norm(r['velocity'][:3]) for r in states)<.06:
                    membership={k:v for r in requests for k,v in r['membership'].items()};membership['/World/Pallet']=[f'/World/Box_{i}' for i in range(6)]
                    joints={k:v for r in requests for k,v in r['joint_states'].items()};c.transfer(group,'newton','physx',membership,joints);returned=True;engines['physx'].call('pallet_returned');print('PALLET_RETURNED_TO_PHYSX',t,flush=True)
            status=capture()
            if frame%30==0:
                low=classify(manifest,paths,poses[used-1],set())
                invalid=[r for r in low if r['location']=='floor' or
                         (r['damaged'] and r['location'].startswith('box_')) or
                         (not r['damaged'] and r['location']=='discard')]
                if invalid:raise RuntimeError('Invalid produce outcome: '+json.dumps([{k:v for k,v in row.items() if k!='washed'} for row in invalid]))
                peak=engines['newton'].call('robot_status');progress=dict(**status,used_frames=used,wall_seconds=round(time.perf_counter()-start,1),robot_phase=cycle.phases[cycle.index][0] if cycle else 'park',transfers=len(c.events),state='running')
                atomic_json(dest/'progress.json',progress,timeout=2.,required=False)
            if frame%150==0:print('COSIM',progress,flush=True);poses.flush();water.flush()
            if args.stop_after_cartons and status['pallet']>=args.stop_after_cartons:break
            if status['forklift_complete']:break
        if not args.stop_after_cartons and not args.qualification and not status['forklift_complete']:raise RuntimeError('Full factory batch did not complete within the simulation limit')
    except Exception as e:
        failure=traceback.format_exc();print(failure,flush=True)
    finally:
        if poses is not None and used:
            # Include the precise stop state, not the previous one-second
            # telemetry sample, when a contact or seal check halts the run.
            if not engines['newton'].failed:
                try:peak=engines['newton'].call('robot_status')
                except Exception:pass
            if not engines['physx'].failed:
                try:report=engines['physx'].call('report')
                except Exception:pass
            report.setdefault('events',[]);report.setdefault('wash_times',{});report.setdefault('pallet_count',0);report['manifest']=None
            if cycle:robot_events.extend(cycle.events)
            report.update(error=failure,used_frames=used,seconds=(used-1)/30,rigid_bodies=len(paths),events=sorted(report['events']+robot_events,key=lambda e:e['time']),ownership_events=c.events,final_owners=c.owners,carton_requests=requests,robot=peak,wall_seconds=time.perf_counter()-start,sdk_versions={'physx_worker':pd.get('versions',{}),'newton_worker':nd.get('versions',{})},newton_internal_hz=nd['internal_hz'],newton_iterations=args.newton_iterations)
            report['failed_transfer']=c.pending_transfer
            report['framework']=graph.report() if graph else None
            report['sdk_versions']['control_worker']=fd.get('versions',{})
            report['qualification_only']=args.qualification
            report['outcomes']=classify(manifest,paths,poses[used-1],report['wash_times'])
            atomic_json(dest/'simulation.json',report);np.save(dest/'water_counts.npy',counts[:used])
            for name,arr in [('poses',poses),('water',water)]:
                arr.flush()
                if used<len(arr):
                    temp=dest/(name+'_trim.npy');trim=np.lib.format.open_memmap(temp,mode='w+',dtype=np.float32,shape=(used,*arr.shape[1:]));trim[:]=arr[:used];trim.flush();trim._mmap.close();arr._mmap.close()
                    for attempt in range(300):
                        try:os.replace(temp,dest/(name+'.npy'));break
                        except PermissionError:
                            if attempt==299:raise
                            time.sleep(.1)
                else:arr._mmap.close()
            atomic_json(dest/'progress.json',dict(state='failed' if failure else 'complete',seconds=report['seconds'],pallet=report['pallet_count'],error=failure))
        if not used and failure:atomic_json(dest/'progress.json',dict(state='failed',error=failure))
        if graph:graph.close()
        if 'c' in locals():c.close()
        if control:control.close()
        for e in engines.values():
            try:e.close()
            except Exception:traceback.print_exc()
        lock.close()
    if failure:raise RuntimeError('Co-simulation stopped; see the cache report and engine logs')
    print('COSIM_COMPLETE',report['seconds'],report['pallet_count'],flush=True)
if __name__=='__main__':main()

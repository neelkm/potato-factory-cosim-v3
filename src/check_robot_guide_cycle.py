"""Qualify a native Newton carton cycle beside the extended filling guides."""
import hashlib,json,time
import numpy as np
from scipy.spatial.transform import Rotation
from config import OUT
from engine_process import EngineProcess
from robot_cycle import RobotCycle

def main():
    fixture=OUT/'qualification/robot_guide_cycle/carton.json'
    if not fixture.exists():
        source=OUT/'diagnostic_fill_guide/carton_0_handoff.json'
        fixture.parent.mkdir(parents=True,exist_ok=True);fixture.write_bytes(source.read_bytes())
    packet=json.loads(fixture.read_text());request=packet['request'];manifest=json.loads((OUT/'manifest.json').read_text())
    standby=['/World/'+p['name'] for p in manifest['potatoes']]+['/World/'+p['name'] for p in manifest['bodies'] if p['name'].startswith(('Box_','Flap_'))]
    engine=EngineProcess('newton');started=time.perf_counter();frames=[];escaped=[]
    try:
        description=engine.call('load',source=str(OUT/'factory_newton.usda'),inactive=standby,iterations=32,robot=True)
        for _ in range(60):engine.call('advance',steps=8)
        engine.call('import_state',states=packet['states'],joint_states=request['joint_states']);engine.call('set_active',paths=request['paths'],active=True)
        t=2.;cycle=RobotCycle(engine,manifest,request,t)
        recorded_paths=sorted(set(request['paths']+['/World/Pallet']+[p for p in description['paths'] if p.startswith('/World/Franka/') or p=='/World/Tool']))
        for frame in range(1800):
            cycle.before_step(t);engine.call('advance',steps=8);t=(frame+61)/30;cycle.after_step(t)
            if frame%3==0 or cycle.finished:
                rows=engine.call('export_state',paths=recorded_paths);poses={r['path']:np.asarray(r['pose']) for r in rows};box=poses['/World/Box_0'];q=Rotation.from_quat(box[3:])
                for p in request['paths']:
                    if 'Potato_' not in p:continue
                    relative=q.inv().apply(poses[p][:3]-box[:3])
                    if not (abs(relative[0])<.154 and abs(relative[1])<.114 and .009<relative[2]<.195):escaped.append(p)
                frames.append([poses[p] for p in recorded_paths])
                if escaped:raise RuntimeError('Contents escaped during the isolated robot cycle')
            if frame%150==0:print('ROBOT_GUIDE_CYCLE',round(t,2),cycle.phases[cycle.index][0] if not cycle.finished else 'complete',flush=True)
            if cycle.finished:break
        status=engine.call('robot_status');limits=np.asarray([87]*4+[12]*3)
        report=dict(passed=cycle.finished and not escaped and np.all(np.asarray(status['peak_torque'])<=limits+.001).item(),
                    finished=cycle.finished,retained_potatoes=request['potatoes']-len(set(escaped)),escaped=sorted(set(escaped)),events=cycle.events,
                    robot=status,seconds=t,wall_seconds=time.perf_counter()-started,fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                    source_stage_sha256=hashlib.sha256((OUT/'factory.usda').read_bytes()).hexdigest(),
                    scope='One isolated native Newton pickup, carry and placement using the production RobotCycle and a saved loaded-carton packet. This checks operation beside the extended static guide; it is not the full factory batch.')
        (OUT/'robot_guide_cycle_validation.json').write_text(json.dumps(report,indent=2));np.save(OUT/'robot_guide_cycle_poses.npy',frames);(OUT/'robot_guide_cycle_paths.json').write_text(json.dumps(recorded_paths))
        print('ROBOT_GUIDE_CYCLE_COMPLETE',report['passed'],report['retained_potatoes'],flush=True)
        if not report['passed']:raise RuntimeError('Robot guide cycle did not complete')
    finally:engine.close()

if __name__=='__main__':main()

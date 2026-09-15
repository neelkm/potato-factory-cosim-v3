"""Check the actual merged physics cache, contents, handoffs and robot limits."""
import argparse,json,collections,math
import numpy as np
from scipy.spatial.transform import Rotation
from config import OUT,BOX_COUNT,BOX_MIN,BOX_MAX,FILL

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',default='cache');args=ap.parse_args();p=OUT/args.cache
    m=json.loads((p/'simulation.json').read_text());paths=json.loads((p/'paths.json').read_text());a=np.load(p/'poses.npy',mmap_mode='r');events=m['events'];checks={}
    def check(name,value):checks[name]=bool(value)
    check('no_runtime_error',m['error'] is None);check('finite_recorded_transforms',np.isfinite(a).all());check('unit_orientation_quaternions',np.max(abs(np.linalg.norm(a[:,:,3:],axis=2)-1))<.002)
    check('six_cartons_placed',m['pallet_count']==BOX_COUNT);check('forklift_delivery_completed',m['forklift_complete'])
    cartons=[len(b) for b in m['boxes']];locations=collections.Counter(o['location'] for o in m['outcomes'])
    check('each_carton_contains_15_to_20',len(cartons)==6 and all(BOX_MIN<=n<=BOX_MAX for n in cartons))
    check('each_carton_retains_counted_contents',[locations[f'box_{i}'] for i in range(6)]==cartons)
    check('all_boxed_potatoes_washed_and_undamaged',all(o['washed'] and not o['damaged'] for o in m['outcomes'] if o['location'].startswith('box_')))
    check('all_damaged_potatoes_in_discard_bin',all(o['location']=='discard' for o in m['outcomes'] if o['damaged']))
    check('discard_contains_only_damaged_potatoes',all(o['damaged'] for o in m['outcomes'] if o['location']=='discard'))
    decisions=[e for e in events if e['kind'] in ('accept','reject')]
    expected={o['potato']:o['damaged'] for o in m['outcomes']}
    check('every_potato_inspected_exactly_once',len(decisions)==len(expected) and {e['potato'] for e in decisions}==set(expected))
    check('every_potato_washed_before_inspection',set(m['wash_times'])==set(expected) and all(m['wash_times'][e['potato']]<=e['time']+1e-4 for e in decisions))
    check('inspection_decisions_match_visible_quality',all(e['potato'] in expected and (e['kind']=='reject')==expected[e['potato']] for e in decisions))
    check('no_floor_spillage',locations['floor']==0);check('all_potatoes_accounted_for',sum(locations[f'box_{i}'] for i in range(6))+locations['discard']==126)
    attach=[e for e in events if e['kind']=='vacuum_attached'];release=[e for e in events if e['kind']=='vacuum_released']
    check('six_four_cup_contact_verified_pickups',len(attach)==6 and all(len(e['contacts'])==4 and all(abs(h['distance']-.008)<=.00401 for h in e['contacts']) for e in attach))
    check('six_controlled_releases',len(release)==6)
    robot=m.get('robot',{});vacuum=robot.get('vacuum',{});force=vacuum.get('peak_cup_force',[float('inf')]);deflection=vacuum.get('peak_cup_deflection',[float('inf')])
    check('suction_within_22N_per_cup',0<max(force)<=22.001);check('seal_travel_within_30mm',max(deflection)<.0301)
    check('franka_motor_torque_limits',len(robot.get('peak_torque',[]))==7 and np.all(np.asarray(robot['peak_torque'])<=np.array([87]*4+[12]*3)+.001))
    check('newton_contact_buffer_has_headroom',0<robot.get('contact_peak',0)<robot.get('contact_capacity',0))
    check('payload_under_3kg_with_tool',len(m['carton_requests'])==6 and all(r['mass']+.35<=3. for r in m['carton_requests']))
    # Observe native gate poses while each replacement carton approaches.
    # The first ready sample ends the waiting window, avoiding assumptions
    # about a fixed carton-conveyor travel time.
    gate_waits=[];gate_poses=a[:,paths.index('/World/FillGate'),2]
    for e in (e for e in events if e['kind']=='box_placed' and e['box']<5):
        first=round(e['time']*30);box=a[first:,paths.index(f'/World/Box_{e["box"]+1}'),:3]
        ready=(abs(box[:,0]-FILL[0])<.07)&(abs(box[:,1])<.045)&(abs(box[:,2]-FILL[2])<.045)
        candidates=np.flatnonzero(ready)
        gate_waits.append(bool(len(candidates)) and (candidates[0]==0 or float(np.min(gate_poses[first:first+candidates[0]]))>=1.59))
    check('fill_gate_waits_for_replacement_carton',len(gate_waits)==5 and all(gate_waits))
    transfers=m['ownership_events'];check('six_carton_handoffs_and_one_pallet_return',len(transfers)==7 and all(e['committed'] for e in transfers) and sum(e['source']=='physx' for e in transfers)==6)
    from state_protocol import Transfer,continuity
    evidence=[]
    for event in transfers:
        packet=Transfer(event['tick'],event['source'],event['destination'],event['states'],event['membership'],event['joint_states'],event['protocol_version']).validate()
        evidence.append(packet.digest==event['digest'] and continuity(event['states'],event['echoed'])==event['continuity'])
    check('independent_transfer_packet_validation',len(evidence)==7 and all(evidence))
    framework=m.get('framework',{})
    check('nvidia_wavefront_graph_executed',framework.get('scheduler')=='NVIDIA WavefrontScheduler' and framework.get('batches')==[['sensors'],['controller'],['line','packing']])
    check('all_live_control_samples_exchanged',framework.get('controller_samples')==m['used_frames']-1==framework.get('ticks'))
    check('coordinator_never_failed',framework.get('failed') is False and not m.get('failed_transfer'))
    check('production_not_short_qualification',not m.get('qualification_only',True))
    # Coordinator commits only after state_protocol.continuity passes; preserve
    # every measured residual in the validation artifact for independent review.
    check('handoffs_at_shared_control_barrier',all(e['tick']%8==0 for e in transfers))
    recorded_handoff_error=0.
    for event in transfers:
        if not event.get('states'):recorded_handoff_error=float('inf');continue
        for state in event['states']:
            recorded=a[event['tick']//8,paths.index(state['path'])];expected=np.asarray(state['pose'])
            recorded_handoff_error=max(recorded_handoff_error,float(np.linalg.norm(recorded[:3]-expected[:3])),float(min(np.linalg.norm(recorded[3:]-expected[3:]),np.linalg.norm(recorded[3:]+expected[3:]))))
    check('replay_captures_committed_handoff_poses',recorded_handoff_error<2e-5)
    check('all_cargo_returned_to_physx',all(owner=='physx' for path,owner in m['final_owners'].items() if path.startswith(('/World/Box_','/World/Flap_','/World/Potato_')) or path=='/World/Pallet'))
    lid_errors=[]
    for i in range(6):
        b=Rotation.from_quat(a[-1,paths.index(f'/World/Box_{i}'),3:])
        for j in range(4):
            q=b.inv()*Rotation.from_quat(a[-1,paths.index(f'/World/Flap_{i}_{j}'),3:]);target=Rotation.from_euler('x' if j<2 else 'y',[-90,90,90,-90][j],degrees=True);lid_errors.append(math.degrees((target.inv()*q).magnitude()))
    check('all_lids_closed',max(lid_errors)<7)
    pallet=a[-1,paths.index('/World/Pallet'),:3];check('pallet_at_dispatch',np.linalg.norm(pallet[:2]-[13,-6.49])<.20 and abs(pallet[2])<.05)
    vehicle=a[:,paths.index('/World/Forklift')];heading=Rotation.from_quat(vehicle[:,3:]).apply([0,1,0])[:,:2];heading=heading[1:]+heading[:-1];heading/=np.linalg.norm(heading,axis=1)[:,None];velocity=np.diff(vehicle[:,:2],axis=0)*30;lateral=float(np.max(abs(velocity[:,0]*heading[:,1]-velocity[:,1]*heading[:,0])))
    check('forklift_follows_its_heading',lateral<.005)
    fork_event=next(e for e in events if e['kind']=='forklift_start');alignment=fork_event.get('alignment',{})
    shift=alignment.get('side_shift_m',float('inf'));measured=alignment.get('measured_pallet_pose',[])
    check('forklift_uses_measured_pallet_alignment',len(measured)==7 and abs(shift-(measured[0]-8.17))<1e-6 and abs(shift)<=.15)
    frame=min(len(a)-1,round((fork_event['time']+11)*30));body=a[frame,paths.index('/World/Forklift')];forks=a[frame,paths.index('/World/Forks')]
    offset=Rotation.from_quat(body[3:]).inv().apply(forks[:3]-body[:3])
    check('native_fork_carriage_reaches_alignment',abs(offset[0]-shift)<2e-4)
    flow=m['recycled_particles']/m['seconds'];ratio=flow/(80772/90);check('double_particle_volume',m['fluid_particles']==2592);check('double_measured_inlet_flow',1.95<ratio<2.05)
    result=dict(passed=all(checks.values()),checks=checks,seconds=m['seconds'],locations=dict(locations),carton_counts=cartons,peak_cup_force_N=force,peak_cup_deflection_m=deflection,peak_motor_torque_Nm=robot.get('peak_torque'),maximum_lid_error_degrees=max(lid_errors),pallet_final_position_m=pallet.tolist(),inlet_particles_per_second=flow,inlet_relative_to_v1=ratio,handoff_continuity=[e['continuity'] for e in transfers])
    (p/'validation.json').write_text(json.dumps(result,indent=2))
    if args.cache=='cache':(OUT/'validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()

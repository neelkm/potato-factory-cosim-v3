"""Independent numeric checks on the captured native fixture and its viewer."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from physics_debug import DebugData,rotation

def main():
    d=DebugData();a=d.arrays;checks={}
    checks['complete_240hz_samples']=a['poses'].shape==(d.steps+1,len(d.paths),7)
    checks['finite_payloads']=all(np.isfinite(v).all() for v in a.values())
    checks['contact_offsets']=len(a['contact_offsets'])==d.steps+2 and np.all(np.diff(a['contact_offsets'])>=0) and a['contact_offsets'][-1]==len(a['contacts'])
    checks['native_normals_unit']=bool(np.allclose(np.linalg.norm(a['contacts'][:,3:6],axis=1),1,atol=1e-4))
    checks['contact_ids_valid']=bool(np.all((a['contacts'][:,8]>=0)&(a['contacts'][:,8]<len(d.sensors))) and np.all((a['contacts'][:,9]>=0)&(a['contacts'][:,9]<len(d.others))))
    checks['boundary_disabled_readback']=all(d.meta['disabled_before']) and not any(d.meta['disabled_after'])
    checks['complete_139_body_return']=len(d.meta['imported'])==139
    checks['handoff_position_continuity']=d.meta['continuity']['position']<2e-5
    checks['handoff_velocity_continuity']=d.meta['continuity']['velocity']<2e-4
    checks['simulation_time_from_tick']=d.meta['source_time']==522.2
    checks['fork_contacts_observed']=d.first_contact is not None and d.peak[:,0].max()>0
    production=Path(__file__).resolve().parents[1]/'output/cache/simulation.json'
    checks['source_provenance']=hashlib.sha256(production.read_bytes()).hexdigest()==d.meta['source_sha256']
    run=json.loads(production.read_text());counts=[]
    for tick in range(0,d.steps+1,8):
        current=[]
        for k,paths in enumerate(run['boxes']):
            box=a['poses'][tick,d.index[f'/World/Box_{k}']];points=a['poses'][tick,[d.index[p] for p in paths],:3]
            relative=(points-box[:3])@rotation(box[3:])
            current.append(int(np.sum((abs(relative[:,0])<.154)&(abs(relative[:,1])<.114)&(relative[:,2]>.009)&(relative[:,2]<.195))))
        counts.append(current)
    expected=[len(b) for b in run['boxes']]
    checks['all_carton_contents_retained']=all(c==expected for c in counts)
    checks['lift_completed']=a['poses'][-1,d.index['/World/Pallet'],2]>.79
    report=dict(passed=all(checks.values()),checks={k:bool(v) for k,v in checks.items()},native_steps=d.steps,
                native_contact_rows=len(a['contacts']),first_fork_contact_s=d.first_contact/d.hz,
                peak_abs_normal_impulse_Ns=d.peak.max(axis=0).tolist(),carton_counts=counts[-1],scope=d.meta['scope'])
    (d.base/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
    if not report['passed']:raise RuntimeError('Debug capture qualification failed')
if __name__=='__main__':main()

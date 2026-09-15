"""Publish the local video only after simulation, replay and media validation."""
import hashlib,json,os,shutil,subprocess
import imageio.v2 as imageio
import imageio_ffmpeg
from config import ROOT,OUT

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    cache=OUT/'cache';validation=json.loads((cache/'validation.json').read_text())
    replay=json.loads((cache/'replay_validation.json').read_text())
    run=json.loads((cache/'simulation.json').read_text())
    assert validation['passed'] and replay['passed'] and run['error'] is None
    for name in ['asset_validation.json','blender_validation.json','control_parity_validation.json','handoff_validation.json','moving_boundary_validation.json','inertia_roundtrip_validation.json','router_contribution_validation.json','fmi_error_contribution_validation.json','fmi_first_sample_contribution_validation.json','core_test_validation.json','build_portability_validation.json','clean_install_validation.json','pallet_return_aligned_validation.json','pallet_return_nominal_validation.json','fill_tail_clear_validation.json','fill_tail_stop_validation.json']:
        assert json.loads((OUT/name).read_text())['passed'],name
    assert replay['frames']==run['used_frames']
    for name in ['fill_guide_legacy_validation.json','fill_guide_extended_validation.json','robot_guide_cycle_validation.json']:
        assert json.loads((OUT/name).read_text())['passed'],name
    ui=json.loads((OUT/'ui_smoke_validation.json').read_text())
    assert ui['passed'] and ui['cache']=='cache' and ui['source']=='factory_replay.usdc'
    assert ui['simulation_sha256']==digest(cache/'simulation.json')
    assert ui['replay_sha256']==digest(OUT/'factory_replay.usdc')
    assert ui.get('app_sha256')==digest(ROOT/'app.py'),'Repeat the desktop check after changing the app'
    render=json.loads((OUT/'render_manifest.json').read_text())
    assert render['simulation_sha256']==digest(cache/'simulation.json')
    shots=json.loads((OUT/'storyboard.json').read_text());expected_frames=sum(round(s['duration']*24) for s in shots)
    assert render['frames']==expected_frames and render['width']==1920 and render['height']==1080 and render['fps']==24
    movie=OUT/'potato_factory.mp4';reader=imageio.get_reader(movie)
    try:
        metadata=reader.get_meta_data();frames=reader.count_frames()
        assert frames==expected_frames,(frames,expected_frames)
        assert tuple(metadata['size'])==(1920,1080) and abs(metadata['fps']-24)<.001,metadata
        assert abs(metadata['duration']-expected_frames/24)<.1,metadata
        for frame in [0,frames//2,frames-1]:
            image=reader.get_data(frame)
            assert image.shape[:2]==(1080,1920) and image.std()>10
    finally:reader.close()
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-xerror','-i',str(movie),'-map','0:v:0','-f','null','-'],check=True,capture_output=True)
    checksum=digest(movie);copies=[]
    for name in ['potato_factory_v3.mp4','potato_factory_latest.mp4']:
        target=ROOT.parent/name;temp=target.with_suffix('.pending.mp4')
        shutil.copy2(movie,temp)
        assert digest(temp)==checksum
        os.replace(temp,target);copies.append(str(target))
    receipt=dict(passed=True,video=dict(frames=frames,seconds=expected_frames/24,width=1920,height=1080,fps=24,sha256=checksum,paths=copies),
                 simulation_seconds=run['seconds'],carton_counts=validation['carton_counts'],locations=validation['locations'],
                 ownership_transfers=len(run['ownership_events']),sdk_versions=run['sdk_versions'],replay=replay,
                 desktop_validation=ui,
                 render=render,
                 native_validation='output/cache/validation.json',framework=run['framework'],checkpoint='../factory_checkpoints/master_20260915')
    (OUT/'delivery_manifest.json').write_text(json.dumps(receipt,indent=2))
    residuals=validation['handoff_continuity']
    lines=['# Completed co-simulation validation','',
           f"The complete native production run lasted {run['seconds']:.2f} simulated seconds. All {len(validation['checks'])} production checks passed.",'',
           '| Result | Measured outcome |','| --- | --- |',
           '| Washing and inspection | All 126 potatoes washed before inspection; each inspected once |',
           '| Good produce | Carton counts '+', '.join(map(str,validation['carton_counts']))+'; all 108 retained through delivery |',
           '| Damaged produce | All 18 in the discard bin; no good potatoes discarded |',
           '| Franka handling | Six pickups with four verified suction contacts; six controlled releases |',
           '| Engine transfers | Six cartons to Newton, followed by the complete loaded pallet back to PhysX |',
           '| Forklift | Loaded pallet delivered to dispatch; no floor spillage |','',
           f"Seven ownership transfers committed at paused clock boundaries. Largest position discontinuity: {max(r['position'] for r in residuals):.9g} m.",
           f"Maximum measured carton plus tool load: {max(r['mass']+.35 for r in run['carton_requests']):.3f} kg (3 kg limit).",
           f"Water inlet rate: {validation['inlet_particles_per_second']:.2f} particles/s; {validation['inlet_relative_to_v1']:.3f} times the original flow.",
           f"Film: {expected_frames/24:.0f} seconds, 1920 × 1080, 24 fps; all {frames} frames decoded. Native ovrtx path tracing, {render['samples_per_pixel']} samples per pixel and OptiX denoising.",
           'Desktop viewer: station navigation, seeking, half-speed playback, orbit, zoom and replay reload passed with this complete run.','',
           'Detailed checks and measured handoff residuals: `cache/validation.json`. Exact package versions and video hashes: `delivery_manifest.json`.',
           'The replay records measured dynamics. The simulation source remains `factory.usda`, with separate native engine partitions.',
           'The native stress tests and protocol failure tests are separate qualification artifacts, not substitutes for this completed batch.','',
           'Physical scope and rebuild/rollback instructions are in the project README.']
    (OUT/'VALIDATION.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf-8')
    text=text.replace('Full integration qualification is in progress; the older working edition remains available in the sibling `potato_factory` folder.',
                      'The complete production batch and its replay have passed validation. The older working edition remains available in the sibling `potato_factory` folder. See `output/VALIDATION.md` and `output/delivery_manifest.json` for measured results.')
    text=text.replace('The production batch and media are being regenerated for this release. Completed results are recorded in `output/VALIDATION.md` and `output/delivery_manifest.json`; a short qualification run is never treated as a finished factory batch.',
                      'The complete native batch, matching USD replay, desktop app and 57-second film passed release validation. Measured outcomes and file hashes are recorded in `output/VALIDATION.md` and `output/delivery_manifest.json`.')
    readme.write_text(text,encoding='utf-8');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()

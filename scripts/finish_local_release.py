"""Finish the current measured run, qualify it, then render and publish locally."""
from pathlib import Path
import subprocess,json,time
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
NATIVE=ROOT/'.venv_physx/Scripts/python.exe';COORDINATOR=ROOT/'.venv_coordinator/Scripts/python.exe'

def execute(exe,script,*args):
    print('RELEASE_STEP',script,flush=True)
    subprocess.run([str(exe),str(ROOT/script),*args],cwd=ROOT,check=True)

def main():
    deadline=time.monotonic()+18000
    while not (OUT/'cache/simulation.json').exists():
        progress=OUT/'cache/progress.json'
        if progress.exists() and json.loads(progress.read_text()).get('state')=='failed':raise RuntimeError('Factory startup failed; inspect the native worker log')
        if time.monotonic()>deadline:raise TimeoutError('Production run did not finish')
        time.sleep(3)
    run=json.loads((OUT/'cache/simulation.json').read_text())
    if run.get('error'):raise RuntimeError('Native factory run failed; rendering has not started')
    # The simulation writes its report just before cleanup. Its process-global
    # native resources must be released before the next PhysX qualification.
    import msvcrt
    while True:
        stream=(OUT/'simulation.lock').open('r+b');stream.seek(0)
        try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1);stream.close();break
        except OSError:stream.close();time.sleep(1)
        if time.monotonic()>deadline:raise TimeoutError('Native worker cleanup did not finish')
    execute(NATIVE,'src/validate_run.py')
    execute(COORDINATOR,'src/check_moving_boundary.py')
    execute(NATIVE,'src/check_inertia_roundtrip.py')
    while not (OUT/'cache/replay_validation.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Replay export did not finish')
        time.sleep(3)
    execute(COORDINATOR,'scripts/audit_scene_assets.py')
    execute(NATIVE,'src/render_video.py','--preview','--width','1280','--spp','16')
    execute(NATIVE,'app.py','--smoke-ui')
    execute(NATIVE,'src/render_video.py','--spp','16','--workers','3')
    execute(NATIVE,'src/finalize_delivery.py')
    print('LOCAL_V3_RELEASE_COMPLETE',flush=True)
if __name__=='__main__':main()

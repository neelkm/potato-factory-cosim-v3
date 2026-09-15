"""Check isolated RTX workers against an explicitly identified replay fixture."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import argparse,sys,json,time,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def worker(job):
    index,fixture=job;fixture=Path(fixture)
    import numpy as np
    from PIL import Image
    from rtx_replay import Replay,VIEWS
    renderer=Replay(960,540,16,source=(fixture/'factory_replay.usdc').as_posix(),cache=str(fixture/'cache'),tag='concurrency_fixture_'+str(os.getpid()))
    destination=ROOT/'output/render_concurrency_probe';destination.mkdir(exist_ok=True);images=[]
    try:
        for frame in range(3):
            pixels=renderer.render(52.733333+frame/24,*VIEWS['Water wash'])
            if pixels.shape[:2]!=(540,960) or pixels.std()<10:raise RuntimeError('Invalid concurrent RTX frame')
            path=destination/f'worker_{index}_{frame}.png';Image.fromarray(pixels).save(path);images.append(str(path))
    finally:renderer.close()
    return images

def main():
    import numpy as np
    from PIL import Image
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',type=Path,default=ROOT/'output');args=parser.parse_args()
    fixture=args.fixture.resolve()
    if not (fixture/'cache/replay_validation.json').exists():raise RuntimeError('Use a completed, validated replay fixture')
    start=time.perf_counter()
    with ProcessPoolExecutor(max_workers=3) as pool:results=list(pool.map(worker,[(i,str(fixture)) for i in range(3)]))
    differences=[]
    for frame in range(3):
        reference=np.asarray(Image.open(results[0][frame]),float)
        for index in [1,2]:differences.append(float(np.sqrt(np.mean((np.asarray(Image.open(results[index][frame]),float)-reference)**2))))
    report=dict(passed=max(differences)<8,workers=3,frames_per_worker=3,max_pixel_rmse=max(differences),wall_seconds=time.perf_counter()-start,
                fixture=str(fixture),scope='RTX process-isolation qualification on the specified read-only fixture; this short probe is separate from the production film')
    (ROOT/'output/render_concurrency_validation.json').write_text(json.dumps(report,indent=2));print(report)
    if not report['passed']:raise RuntimeError('Concurrent render results diverged')
if __name__=='__main__':main()

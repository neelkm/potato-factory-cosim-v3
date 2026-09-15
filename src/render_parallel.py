"""Isolated RTX render workers; encode shots once and concatenate losslessly."""
from concurrent.futures import ProcessPoolExecutor,wait,FIRST_COMPLETED
from pathlib import Path
import atexit,hashlib,json,os,subprocess,time
import numpy as np
from PIL import Image
import imageio.v2 as imageio
import imageio_ffmpeg
from rtx_replay import Replay,VIEWS,OUT
from storyboard import storyboard
from framework.files import atomic_json

_renderer=None

def initialize(options):
    global _renderer,_options,_poses,_paths
    _options=options
    _poses=None;_paths=None
    atexit.register(close)

def ensure_renderer():
    global _renderer,_poses,_paths
    if _renderer is not None:return
    options=_options
    _renderer=Replay(options['width'],options['width']*9//16,options['spp'],source=options['source'],cache=options['cache'],tag='film_worker_'+str(os.getpid()))
    _poses=np.load(OUT/options['cache']/'poses.npy',mmap_mode='r')
    _paths=json.loads((OUT/options['cache']/'paths.json').read_text())

def close():
    global _renderer
    if _renderer is not None:
        _renderer.close();_renderer=None

def shot_job(job):
    from render_video import overlay
    si,shot,offset,total,directory,signature=job;directory=Path(directory);n=round(shot['duration']*24)
    eye,target=VIEWS[shot['view']];eye=shot.get('eye',eye);target=shot.get('target',target)
    destination=directory/f'shot_{si:02}.mp4';temporary=directory/f'shot_{si:02}.partial.mp4';start=time.perf_counter()
    receipt=directory/f'shot_{si:02}.json'
    if receipt.exists() and destination.exists():
        old=json.loads(receipt.read_text())
        if old.get('signature')==signature and old.get('state')=='complete' and old.get('sha256')==hashlib.sha256(destination.read_bytes()).hexdigest():
            print('SHOT_REUSED',si+1,flush=True);return old
    ensure_renderer()
    for _ in range(2):_renderer.render(shot['t0'],eye,target)
    writer=imageio.get_writer(temporary,fps=24,codec='libx264',quality=None,ffmpeg_params=['-crf','17','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart'],macro_block_size=1)
    try:
        for k in range(n):
            u=k/max(1,n-1);cam=np.asarray(eye)+np.asarray(shot['move'])*(u*u*(3-2*u));t=min(_options['seconds'],shot['t0']+k/24*shot['rate'])
            pixels=_renderer.render(t,cam,target)
            tracking=(_poses[round(t*30),_paths.index(shot['tracked']),:3],cam,np.asarray(target,float)) if 'tracked' in shot else None
            final=overlay(pixels,shot,t,offset+k,total,tracking);writer.append_data(final)
            if k==n//2:
                Image.fromarray(final).save(OUT/f'station_{si:02}.jpg',quality=95)
                if si==0:Image.fromarray(final).save(OUT/'poster.jpg',quality=95)
            if k%12==0 or k==n-1:atomic_json(directory/f'shot_{si:02}.json',dict(station=si+1,frames=k+1,total=n,state='rendering'),timeout=1,required=False)
    finally:writer.close()
    reader=imageio.get_reader(temporary)
    try:
        count=reader.count_frames();meta=reader.get_meta_data()
        if count!=n or tuple(meta['size'])!=(_options['width'],_options['width']*9//16) or abs(meta['fps']-24)>.001:raise RuntimeError('Shot encoding mismatch')
    finally:reader.close()
    os.replace(temporary,destination)
    result=dict(station=si+1,frames=n,total=n,state='complete',seconds=time.perf_counter()-start,path=destination.name,
                signature=signature,sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    atomic_json(directory/f'shot_{si:02}.json',result);print('SHOT_COMPLETE',shot['title'],round(result['seconds'],1),flush=True)
    return result

def render(args):
    start=time.perf_counter();validation=json.loads((OUT/args.cache/'validation.json').read_text())
    if not validation['passed']:raise RuntimeError('Full factory validation is required')
    path=OUT/args.cache/'simulation.json';meta=json.loads(path.read_text());checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    shots=storyboard(meta);total=sum(round(s['duration']*24) for s in shots);directory=OUT/'render_shots';directory.mkdir(exist_ok=True)
    options=dict(width=args.width,spp=args.spp,source=args.source,cache=args.cache,seconds=meta['seconds'])
    jobs=[];offset=0
    source_hashes={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['rtx_replay.py','render_video.py','render_parallel.py','storyboard.py']}
    source_hashes.update({name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ['factory.usda','factory_geometry.usdc',args.source]})
    source_hashes.update({p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'textures').rglob('*') if p.is_file()})
    from importlib.metadata import version
    source_hashes.update({name:version(name) for name in ['ovrtx','ovstage']})
    for index,shot in enumerate(shots):
        signature=hashlib.sha256(json.dumps(dict(shot=shot,options=options,simulation=checksum,sources=source_hashes),sort_keys=True).encode()).hexdigest()
        jobs.append((index,shot,offset,total,str(directory),signature));offset+=round(shot['duration']*24)
        receipt=directory/f'shot_{index:02}.json';old={}
        if receipt.exists():
            try:old=json.loads(receipt.read_text())
            except ValueError:pass
        if old.get('signature')!=signature or old.get('state')!='complete':
            atomic_json(receipt,dict(station=index+1,frames=0,total=round(shot['duration']*24),state='queued'))
    results=[]
    try:
        with ProcessPoolExecutor(max_workers=args.workers,initializer=initialize,initargs=(options,)) as pool:
            pending={pool.submit(shot_job,job) for job in jobs}
            while pending:
                done,pending=wait(pending,timeout=1,return_when=FIRST_COMPLETED)
                for future in done:results.append(future.result())
                rows=[]
                for index in range(len(shots)):
                    try:rows.append(json.loads((directory/f'shot_{index:02}.json').read_text()))
                    except (OSError,ValueError):pass
                atomic_json(OUT/'render_progress.json',dict(state='rendering',frames=sum(r['frames'] for r in rows),total=total,
                    completed_stations=len(results),stations=len(shots),workers=args.workers,wall_seconds=round(time.perf_counter()-start,1)),timeout=1,required=False)
        if sum(row['frames'] for row in results)!=total or len(results)!=len(shots):raise RuntimeError('Incomplete shot set')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=checksum:raise RuntimeError('Simulation changed during render')
        listing=directory/'concat.txt';listing.write_text(''.join(f"file 'shot_{index:02}.mp4'\n" for index in range(len(shots))))
        target=OUT/'potato_factory.mp4';temporary=OUT/'potato_factory.pending.mp4'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart',str(temporary)],check=True)
        reader=imageio.get_reader(temporary)
        try:
            if reader.count_frames()!=total:raise RuntimeError('Concatenated frame count mismatch')
        finally:reader.close()
        os.replace(temporary,target)
        manifest=dict(width=args.width,height=args.width*9//16,fps=24,frames=total,samples_per_pixel=args.spp,
                      renderer='ovrtx PathTracing with OptiX denoising',seconds=total/24,source=args.source,cache=args.cache,
                      wall_seconds=time.perf_counter()-start,simulation_sha256=checksum,workers=args.workers,
                      encoding='Each shot encoded once with libx264 CRF 17; final concatenation uses stream copy',shots=sorted(results,key=lambda r:r['station']))
        atomic_json(OUT/'render_manifest.json',manifest)
        atomic_json(OUT/'render_progress.json',dict(state='complete',frames=total,total=total,workers=args.workers,wall_seconds=time.perf_counter()-start))
        print('PARALLEL_FILM_COMPLETE',total,round(time.perf_counter()-start,1),flush=True)
    except BaseException:
        atomic_json(OUT/'render_progress.json',dict(state='failed',completed_stations=len(results),total=total,workers=args.workers));raise

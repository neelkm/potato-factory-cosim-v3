"""Compare film sampling and camera framing against the completed native run."""
import argparse,json,time
from PIL import Image
import numpy as np
from rtx_replay import Replay,VIEWS,OUT
from render_video import overlay
from storyboard import storyboard

ap=argparse.ArgumentParser();ap.add_argument('--only',nargs='+',type=int);args=ap.parse_args()
shots=storyboard(json.loads((OUT/'cache/simulation.json').read_text()));total=sum(round(s['duration']*24) for s in shots)
renderer=Replay(1920,1080,16,tag='quality_16');results=[]
try:
    for index in args.only or [0,2,4,5,6,9,10,11,12]:
        shot=shots[index];n=round(shot['duration']*24);k=n//2;u=k/(n-1)
        eye,target=VIEWS[shot['view']];eye=shot.get('eye',eye);target=shot.get('target',target)
        eye=np.asarray(eye)+np.asarray(shot['move'])*(u*u*(3-2*u));t=shot['t0']+k/24*shot['rate']
        print('QUALITY_BEGIN',index,t,flush=True);pixels=renderer.render(t,eye,target)
        ordinal=sum(round(s['duration']*24) for s in shots[:index])+k
        Image.fromarray(overlay(pixels,shot,t,ordinal,total)).save(OUT/f'quality16_{index:02}.jpg',quality=95)
        results.append(dict(station=index,seconds=t,**renderer.last_timing));print('QUALITY16',results[-1],flush=True)
    (OUT/'render_quality_timing.json').write_text(json.dumps(results,indent=2))
finally:renderer.close()

"""Check immediate and repeated sampling across large replay-time changes."""
import argparse,json
import numpy as np
from PIL import Image
from rtx_replay import Replay,VIEWS,OUT
from storyboard import storyboard

ap=argparse.ArgumentParser();ap.add_argument('--zero-dt',action='store_true');args=ap.parse_args()
shots=storyboard(json.loads((OUT/'cache/simulation.json').read_text()))
r=Replay(960,540,16,tag='temporal_probe')
if args.zero_dt:
    step=r.r.step
    r.r.step=lambda **kw:step(**dict(kw,delta_time=0.0))
try:
    for index in [0,6,11,0]:
        s=shots[index];eye,target=VIEWS[s['view']];eye=s.get('eye',eye);target=s.get('target',target)
        t=s['t0']+s['duration']*.5*s['rate']
        for repeat in range(3):
            pixels=r.render(t,eye,target)
            Image.fromarray(pixels).convert('RGB').save(OUT/f'temporal_{int(args.zero_dt)}_{index}_{repeat}.jpg',quality=95)
            print(index,repeat,r.last_timing,r.last_render_progress,flush=True)
finally:r.close()

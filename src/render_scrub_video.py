"""Captioned tour of the validated post-wash scrubbing variant."""
import argparse,json,os
# Large native thread pools in concurrent RTX workers can oversubscribe the
# workstation during USD population. Preserve an explicit caller override.
os.environ.setdefault('PXR_WORK_THREAD_LIMIT','8')
from config import OUT

def scrub_storyboard(meta):
    if not meta.get('scrub_times') or not meta.get('forklift_complete') or meta.get('error'):
        raise RuntimeError('A complete scrubber production run is required')
    events=meta['events']
    first=lambda kind:next(e['time'] for e in events if e['kind']==kind)
    scrub=min(meta['scrub_times'].values());wash=min(meta['wash_times'].values())
    def shot(view,duration,t0,title,caption,rate=1,**kwargs):
        return dict(view=view,duration=duration,t0=max(0,t0),rate=rate,title=title,caption=caption,move=(0,0,0),**kwargs)
    return [
        shot('Overall',3,wash+3,'FIELD / FLOW  |  POST-WASH SCRUBBING','Wash → soft-brush scrub → inspect → pack'),
        shot('Water wash',4,wash+1,'01  WATER WASH','PhysX spray and roller transport · Actual simulation replay'),
        shot('Dirt scrubbing',6,scrub-1,'02  GENTLE BRUSH SCRUB','Six driven brushes · Compliant PhysX contact surfaces',cleaning_times=sorted(meta['scrub_times'].values())),
        shot('Dirt scrubbing',5,scrub+1,'CONTACT-BASED CLEANING CHECK','Contact time + surface slip · Soil removal is an empirical proxy',rate=.5,
             eye=(2.4,-1.3,2.45),target=(2.30,0,1.53),cleaning_times=sorted(meta['scrub_times'].values())),
        shot('Quality & rejection',4,first('reject')-.6,'03  INSPECT & DIVERT','FMI accepts good potatoes only after washing and scrubbing',rate=.6),
        shot('Robot palletizing',4,first('vacuum_attached')+2,'04  PACK & PALLETIZE','Loaded cartons transfer from PhysX to Newton for the Franka arm',rate=2),
        shot('Forklift dispatch',4,first('forklift_start')+16,'05  DISPATCH','Six packed cartons return to PhysX for forklift transport',rate=4,
             eye=(16,-.5,5.5),target=(10.6,-4.5,.8)),
    ]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',default='scrub_20261005');ap.add_argument('--source',default='factory_scrub_replay.usdc')
    ap.add_argument('--width',type=int,default=1920);ap.add_argument('--spp',type=int,default=32);ap.add_argument('--workers',type=int,default=1,choices=[1,2,3,4]);ap.add_argument('--preview',action='store_true')
    args=ap.parse_args();meta=json.loads((OUT/args.cache/'simulation.json').read_text())
    if not json.loads((OUT/args.cache/'validation.json').read_text())['passed']:raise RuntimeError('Validation failed')
    shots=scrub_storyboard(meta);media=OUT/'scrub_media';media.mkdir(exist_ok=True)
    (media/'storyboard.json').write_text(json.dumps(shots,indent=2))
    if args.preview:
        from rtx_replay import Replay,VIEWS
        from render_video import overlay
        from PIL import Image
        r=Replay(args.width,args.width*9//16,args.spp,source=args.source,cache=args.cache,tag='scrub_preview')
        try:
            for i,s in enumerate(shots):
                eye,target=VIEWS[s['view']];eye=s.get('eye',eye);target=s.get('target',target);t=s['t0']+s['duration']*.5*s['rate']
                pixels=r.render(t,eye,target)
                Image.fromarray(overlay(pixels,s,t,i,len(shots))).save(media/f'preview_{i:02}.jpg',quality=95)
                print('PREVIEW',i,flush=True)
        finally:r.close()
    else:
        from render_parallel import render
        render(args,shots=shots,output='potato_factory_scrub.mp4',artifact_dir=media)

if __name__=='__main__':main()

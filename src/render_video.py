"""A station tour cut from the actual complete factory simulation."""
import argparse,json,time,math,hashlib,os
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import imageio.v2 as imageio
from rtx_replay import Replay,VIEWS,metrics,OUT
from storyboard import storyboard
from framework.files import atomic_json

def font(n,bold=False):return ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',n)
def overlay(pixels,shot,t,k,total,tracking=None):
    im=Image.fromarray(pixels).convert('RGBA');w,h=im.size;s=w/1920;layer=Image.new('RGBA',im.size);d=ImageDraw.Draw(layer)
    def rect(x,y,x2,y2,fill,r=8):d.rounded_rectangle(tuple(int(v*s) for v in (x,y,x2,y2)),radius=int(r*s),fill=fill)
    def txt(x,y,label,size=27,bold=False,color=(242,240,229,255)):d.text((int(x*s),int(y*s)),label,font=font(int(size*s),bold),fill=color)
    rect(38,30,305,85,(10,29,27,215));txt(59,40,'FIELD / FLOW',29,True)
    rect(1580,30,1880,85,(10,29,27,215));txt(1602,43,f'SIMULATION  {t:06.2f}s',24)
    panel_width=870 if 'tracked' in shot else (1050 if shot['view']=='Overall' else 1240)
    rect(38,895,panel_width,1030,(10,29,27,225));d.rectangle((int(38*s),int(895*s),int(46*s),int(1030*s)),fill=(217,174,86,255))
    txt(68,914,shot['title'],36,True);txt(68,973,shot['caption'],25,color=(196,217,207,255))
    d.rectangle((0,h-int(5*s),int(w*(k+1)/total),h),fill=(217,174,86,255))
    if tracking is not None and shot['event_time']-.15<t<shot['event_time']+1.2:
        p,eye,target=tracking;v=np.asarray(target)-eye;v/=np.linalg.norm(v);right=np.cross(v,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,v);r=p-eye;dep=r@v
        if dep>.2:
            focal=w*35/36;x=w/2+(r@right)*focal/dep;y=h/2-(r@up)*focal/dep;rad=max(16*s,.15*focal/dep)
            if 0<x<w and 0<y<h:d.ellipse((x-rad,y-rad,x+rad,y+rad),outline=(250,101,72,255),width=max(2,int(3*s)))
    return np.asarray(Image.alpha_composite(im,layer).convert('RGB'))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',default='cache');ap.add_argument('--source',default='factory_replay.usdc');ap.add_argument('--width',type=int,default=1920);ap.add_argument('--spp',type=int,default=64);ap.add_argument('--preview',action='store_true');ap.add_argument('--only',nargs='+',type=int)
    ap.add_argument('--workers',type=int,choices=[1,2,3,4],default=3);args=ap.parse_args()
    if args.only and not args.preview:ap.error('--only is available for preview images only')
    if args.workers>1 and not args.preview:
        from render_parallel import render
        return render(args)
    validation=json.loads((OUT/args.cache/'validation.json').read_text());assert validation['passed'], 'Full-run validation has not passed'
    meta=json.loads((OUT/args.cache/'simulation.json').read_text());shots=storyboard(meta);fps=24;total=sum(round(s['duration']*fps) for s in shots);index=0;start=time.perf_counter()
    poses=np.load(OUT/args.cache/'poses.npy',mmap_mode='r');paths=json.loads((OUT/args.cache/'paths.json').read_text());r=Replay(args.width,args.width*9//16,args.spp,source=args.source,cache=args.cache,tag='film_v3')
    writer=None if args.preview else imageio.get_writer(OUT/'potato_factory.mp4',fps=fps,codec='libx264',quality=None,ffmpeg_params=['-crf','17','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart'],macro_block_size=1)
    try:
        for si,shot in enumerate(shots):
            if args.only and si not in args.only:continue
            eye,target=VIEWS[shot['view']];eye=shot.get('eye',eye);target=shot.get('target',target);n=round(shot['duration']*fps)
            for _ in range(2):r.render(shot['t0'],eye,target)
            for k in ([n//2] if args.preview else range(n)):
                u=k/max(1,n-1);cam=np.asarray(eye)+np.asarray(shot['move'])*(u*u*(3-2*u));t=min(meta['seconds'],shot['t0']+k/fps*shot['rate'])
                pixels=r.render(t,cam,target);track=(poses[round(t*30),paths.index(shot['tracked']),:3],cam,np.asarray(target,float)) if 'tracked' in shot else None
                final=overlay(pixels,shot,t,index,total,track)
                if writer:writer.append_data(final)
                if k==n//2:
                    Image.fromarray(final).save(OUT/f'station_{si:02}.jpg',quality=95)
                    if si==0:Image.fromarray(final).save(OUT/'poster.jpg',quality=95)
                index+=1
                if writer:
                    progress=dict(state='rendering',frames=index,total=total,station=si+1,stations=len(shots),wall_seconds=round(time.perf_counter()-start,1))
                    atomic_json(OUT/'render_progress.json',progress,timeout=1.,required=False)
                if k%24==0:print(f'RENDER station={si+1}/{len(shots)} frame={k}/{n} wall={time.perf_counter()-start:.1f}s',flush=True)
            print('SHOT_COMPLETE',shot['title'],r.last_timing,flush=True)
        print('PREVIEW_COMPLETE' if args.preview else 'FILM_COMPLETE',flush=True)
        if not args.preview:
            manifest=dict(width=args.width,height=args.width*9//16,fps=fps,frames=index,samples_per_pixel=args.spp,
                          renderer='ovrtx PathTracing with OptiX denoising',seconds=sum(s['duration'] for s in shots),
                          source=args.source,cache=args.cache,wall_seconds=time.perf_counter()-start,
                          simulation_sha256=hashlib.sha256((OUT/args.cache/'simulation.json').read_bytes()).hexdigest())
            (OUT/'render_manifest.json').write_text(json.dumps(manifest,indent=2))
    finally:
        if writer:
            writer.close()
            progress=dict(state='complete' if index==total else 'failed',frames=index,total=total,wall_seconds=round(time.perf_counter()-start,1))
            atomic_json(OUT/'render_progress.json',progress)
        r.close()
if __name__=='__main__':main()

"""Prepare measured water meshes without holding the live cache files open."""
import argparse,json,time,os,zipfile
import numpy as np
from config import OUT
from water_mesh import reconstruct
ap=argparse.ArgumentParser();ap.add_argument('--cache',default='cache');ap.add_argument('--start',type=int,default=0);ap.add_argument('--stride',type=int,default=1);args=ap.parse_args()
p=OUT/args.cache;dest=p/'liquid_mesh';dest.mkdir(exist_ok=True);f=args.start
while True:
    info=p/'simulation.json';finished=False
    if info.exists():
        try:meta=json.loads(info.read_text());finished=True
        except json.JSONDecodeError:time.sleep(.1);continue
        if f>round(meta['seconds']*30):break
    try:poses=np.load(p/'poses.npy',mmap_mode='r')
    except (PermissionError,FileNotFoundError):time.sleep(.1);continue
    ready=f<len(poses) and (finished or (f+2<len(poses) and poses[f+2,0,6]!=0));poses._mmap.close()
    if not ready:time.sleep(.25);continue
    target=dest/f'{f:06}.npz';valid=target.exists()
    if valid:
        try:
            with zipfile.ZipFile(target) as z:valid=z.testzip() is None
        except zipfile.BadZipFile:valid=False
    if not valid:
        try:water=np.load(p/'water.npy',mmap_mode='r')
        except (PermissionError,FileNotFoundError):time.sleep(.1);continue
        points=np.asarray(water[f]).copy();water._mmap.close();points=points[points[:,2]>.8];v,faces,n=reconstruct(points)
        temp=dest/f'{f:06}.tmp.npz';np.savez_compressed(temp,vertices=v,faces=faces,normals=n);os.replace(temp,target)
    if (f-args.start)%900==0:print('LIQUID_READY',f/30,flush=True)
    f+=args.stride
print('LIQUID_CACHE_COMPLETE',flush=True)

"""Exercise repeated native RTX frames and record GPU allocation growth."""
import argparse,gc,json,subprocess,time
from collections import Counter
from rtx_replay import Replay,VIEWS,OUT

def memory():
    text=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True)
    return int(text.strip().splitlines()[0])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--no-reset',action='store_true');ap.add_argument('--collect',action='store_true');ap.add_argument('--frames',type=int,default=100);ap.add_argument('--width',type=int,default=480);ap.add_argument('--spp',type=int,default=1);args=ap.parse_args()
    r=Replay(args.width,args.width*9//16,args.spp,tag='memory_probe',reset_history=not args.no_reset)
    rows=[];start=time.perf_counter()
    try:
        for i in range(args.frames):
            image=r.render(52.733333+i/24,*VIEWS['Overall']);del image
            if args.collect:gc.collect()
            if i%5==0 or i==args.frames-1:
                counts=Counter(type(o).__name__ for o in gc.get_objects())
                row=dict(frame=i,gpu_mib=memory(),live_mappings=len(r.r._live_mappings),products=counts['RenderProductSetOutputs'],mapped=counts['MappedRenderVar'],timing=r.last_timing,wall=round(time.perf_counter()-start,2));rows.append(row);print(json.dumps(row),flush=True)
        (OUT/f"render_memory_{'noreset' if args.no_reset else 'reset'}_{'gc' if args.collect else 'normal'}.json").write_text(json.dumps(rows,indent=2))
    finally:r.close()
if __name__=='__main__':main()

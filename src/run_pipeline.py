"""Create and validate a fresh replay without overwriting the delivered run."""
from pathlib import Path
import argparse,subprocess,sys,time
from config import ROOT,OUT
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',default='rerun_'+time.strftime('%Y%m%d_%H%M%S'));ap.add_argument('--seconds',type=float,default=1800);args=ap.parse_args()
    if (OUT/args.cache).exists():raise RuntimeError('Choose a new cache name; that run folder already exists')
    for command in [
        ['simulate_factory.py','--cache',args.cache,'--seconds',str(args.seconds)],
        ['validate_run.py','--cache',args.cache],
        ['bake_replay.py','--cache',args.cache,'--name',args.cache+'.usdc']]:
        runtime=ROOT/('.venv_coordinator' if command[0]=='simulate_factory.py' else '.venv_physx')/'Scripts/python.exe'
        subprocess.run([str(runtime),str(ROOT/'src'/command[0]),*command[1:]],cwd=ROOT,check=True)
    print('Validated replay:',OUT/(args.cache+'.usdc'))
if __name__=='__main__':main()

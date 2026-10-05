"""Build a fresh validated replay; preserve every previously completed run."""
import argparse,json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['production','simple_controls','diagnostic_rpc'],default='production')
    parser.add_argument('--seconds',type=int,default=1200);parser.add_argument('--physx-source');args=parser.parse_args()
    active_path=ROOT/'output/active_run.json'
    active=json.loads(active_path.read_text()) if active_path.exists() else {}
    physics=args.physx_source or active.get('physics_source','factory_physx.usda')
    cache='run_'+time.strftime('%Y%m%d_%H%M%S');source=cache+'.usdc'
    coordinator=ROOT/'.venv_coordinator/Scripts/python.exe';native=ROOT/'.venv_physx/Scripts/python.exe'
    subprocess.run([coordinator,ROOT/'src/simulate_factory.py','--seconds',str(args.seconds),'--cache',cache,'--profile',args.profile,'--physx-source',physics],cwd=ROOT,check=True)
    subprocess.run([native,ROOT/'src/validate_run.py','--cache',cache],cwd=ROOT,check=True)
    subprocess.run([native,ROOT/'src/bake_replay.py','--cache',cache,'--name',source],cwd=ROOT,check=True)
    print('Validated replay:',ROOT/'output'/source)
    subprocess.run([native,ROOT/'app.py','--cache',cache,'--source',source],cwd=ROOT,check=True)
if __name__=='__main__':main()

"""Retrieve pinned source dependencies and create isolated Windows runtimes."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1]
SOURCES={
 'cosim':('NVIDIA-dev/cosim','8b45d424641ebc74cbc5660a16aa7bc7eb4efeb3','vendor/nvidia_cosim',''),
 'ovnewton':('NVIDIA-Omniverse/ovnewton-internal','fe5dcfe9e017e2e462ede0ab7dea73120dd0b46d','reference/ovnewton',''),
 'ovfmi':('NVIDIA-Omniverse/omniverse-labs','da9ce230ccaf464aca6a5246ac3ace1c925c4eeb','reference/ovfmi','projects/ovfmi/'),
}

def fetch_source(name):
    repo,commit,relative,subdir=SOURCES[name];target=ROOT/relative
    if target.exists():
        marker=target/'.factory-source.json'
        if marker.exists() and json.loads(marker.read_text()).get('commit')==commit:return
        raise RuntimeError(f'{target} already exists; verify it manually rather than overwriting a local checkout')
    download=ROOT/'downloads';download.mkdir(exist_ok=True);archive=download/(name+'-'+commit[:12]+'.zip')
    with archive.open('wb') as stream:subprocess.run(['gh','api',f'repos/{repo}/zipball/{commit}'],stdout=stream,check=True)
    with zipfile.ZipFile(archive) as zipped:
        prefix=zipped.namelist()[0].split('/')[0]+'/'+subdir
        for info in zipped.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):continue
            path=Path(info.filename[len(prefix):])
            # Package only source needed by ovfmi, not its third-party tree.
            if name=='ovfmi' and path.parts[0] in ('third-party','.git','build'):continue
            dest=(target/path).resolve()
            if not dest.is_relative_to(target.resolve()):raise ValueError('Unsafe archive path')
            dest.parent.mkdir(parents=True,exist_ok=True)
            with zipped.open(info) as source,dest.open('wb') as output:shutil.copyfileobj(source,output)
    (target/'.factory-source.json').write_text(json.dumps(dict(repository=repo,commit=commit),indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fetch-sources',action='store_true');parser.add_argument('--install',action='store_true')
    parser.add_argument('--sources',nargs='+',choices=list(SOURCES),default=list(SOURCES))
    parser.add_argument('--plan',action='store_true');args=parser.parse_args()
    plan=dict(python='CPython 3.12, Windows x64',sources=SOURCES,environments=['coordinator','physx','newton'],
              note='Requires existing GitHub access to private source repositories and access to the pinned internal ovstage wheel. No credentials are stored here.')
    if args.plan or not (args.fetch_sources or args.install):print(json.dumps(plan,indent=2));return
    if args.fetch_sources:
        for name in args.sources:fetch_source(name)
    if args.install:
        if sys.version_info[:2]!=(3,12) or sys.platform!='win32':raise RuntimeError('This native release requires Windows CPython 3.12')
        for name in ['coordinator','physx','newton']:
            environment=ROOT/('.venv_'+name)
            if environment.exists():raise RuntimeError(f'{environment} already exists; preserving its installed packages')
            subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
            executable=environment/'Scripts/python.exe'
            subprocess.run([str(executable),'-m','pip','install','--extra-index-url','https://pypi.nvidia.com','-r',str(ROOT/f'requirements-{name}.lock.txt')],cwd=ROOT,check=True)
    print('BOOTSTRAP_COMPLETE')
if __name__=='__main__':main()

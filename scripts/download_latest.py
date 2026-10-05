"""Download the pinned base and 3.1 update, then verify and safely extract both."""
from pathlib import Path
import subprocess
from unpack_release import unpack

ROOT=Path(__file__).resolve().parents[1]
REPO='neelkm/potato-factory-cosim-v3'

def main():
    for tag,manifest in [('v3.0.0','release_manifest.json'),('v3.1.0','scrub-manifest.json')]:
        directory=ROOT/'downloads'/tag
        directory.mkdir(parents=True,exist_ok=True)
        subprocess.run(['gh','release','download',tag,'--repo',REPO,'--dir',str(directory),'--skip-existing',
                        '--pattern','*manifest.json','--pattern','*.part*','--pattern','factory-*.zip'],check=True)
        unpack(directory/manifest,ROOT)

if __name__=='__main__':main()

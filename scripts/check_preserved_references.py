"""Recheck the preserved master source/media and retired v1 references."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];WORKSPACE=ROOT.parent

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):value.update(chunk)
    return value.hexdigest()

def main():
    checkpoint=WORKSPACE/'factory_checkpoints/master_20260915'
    manifest=json.loads((checkpoint/'manifest.json').read_text());selected=[]
    for row in manifest['files']:
        path=Path(row['path'])
        if path.parts[0]=='src' and path.suffix in ('.py','.cpp','.h') or row['path'] in (
            'app.py','README.md','Launch Factory.cmd','output/factory.usda','output/factory_geometry.usdc',
            'output/potato_factory.blend','output/potato_factory.mp4','output/cache/simulation.json'):
            for base in [WORKSPACE/'potato_factory_cosim',checkpoint/'potato_factory_cosim']:
                if digest(base/path)!=row['sha256']:raise RuntimeError('Preserved master changed: '+str(path))
            selected.append(row['path'])
    reference=WORKSPACE/'factory_reference/v1';retired=json.loads((reference/'retirement_manifest.json').read_text())
    for row in retired['files']:
        if digest(reference/row['path'])!=row['sha256'].lower():raise RuntimeError('Retained v1 reference changed')
    report=dict(passed=True,master_total_files=len(manifest['files']),master_total_bytes=sum(r['bytes'] for r in manifest['files']),
                rechecked_master_files=selected,v1_reference_files=len(retired['files']),
                scope='Full master copy was individually verified at creation. This follow-up checks master source and principal scene/media in both original and checkpoint, plus every retained v1 reference.')
    (ROOT/'output/preservation_validation.json').write_text(json.dumps(report,indent=2));print('PRESERVATION_VERIFIED',len(selected),len(retired['files']))
if __name__=='__main__':main()

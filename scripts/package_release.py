"""Package source-independent assets and measured replay into verified parts."""
from pathlib import Path
import argparse,hashlib,json,zipfile,time
ROOT=Path(__file__).resolve().parents[1];DIST=ROOT/'dist';OUT=ROOT/'output'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def selected(group):
    if group=='assets':
        names=['factory.usda','factory_geometry.usdc','factory_physx.usda','factory_newton.usda','factory_fmi.usda','FactoryController.fmu',
               'potato_factory.blend','potato_albedo.png','hangar_interior_4k.hdr','franka_cell.usda','franka_test.usda','franka_kinematics.json','cell_layout.json','manifest.json']
        files=[OUT/name for name in names]
        files += [p for base in [ROOT/'assets',OUT/'textures'] for p in base.rglob('*') if p.is_file()]
        files += [ROOT/'tools/mechanics_bridge.dll',ROOT/'tools/fluid_bridge.dll']
    elif group=='replay':
        assert json.loads((OUT/'cache/validation.json').read_text())['passed']
        assert json.loads((OUT/'cache/replay_validation.json').read_text())['passed']
        files=[p for p in (OUT/'cache').rglob('*') if p.is_file() and ('liquid_mesh' not in p.parts) and p.suffix in ('.npy','.json','.usdc')]
        files += [p for p in OUT.glob('factory_replay*') if p.is_file()]
        # Preserve the exact packet behind the positive/negative docking
        # qualification without distributing an entire failed diagnostic run.
        files += [OUT/'qualification/pallet_return/simulation.json']
        files += [OUT/'qualification/fill_tail/fixture.json']
        files += [OUT/'qualification/fill_guide/fixture.json']
        files += [OUT/'qualification/robot_guide_cycle/carton.json']
    elif group=='media':
        assert json.loads((OUT/'delivery_manifest.json').read_text())['passed']
        files=[OUT/'potato_factory.mp4',OUT/'poster.jpg',OUT/'app_screenshot.png',OUT/'VALIDATION.md']
        files += list(OUT.glob('station_*.jpg'))
        files += [p for p in OUT.glob('*.json') if p.name.endswith('validation.json') or p.name in ('delivery_manifest.json','render_manifest.json','runtime_manifest.json','storyboard.json','render_progress.json')]
    else:raise ValueError(group)
    files=sorted(set(files))
    if any(not p.is_file() for p in files):raise RuntimeError('Missing release asset')
    return files

def pack(group):
    DIST.mkdir(exist_ok=True);archive=DIST/f'factory-{group}-v3.zip';files=selected(group);entries=[];start=time.perf_counter()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4,allowZip64=True) as zipped:
        for i,path in enumerate(files):
            relative=path.relative_to(ROOT).as_posix();checksum=digest(path)
            zipped.write(path,relative);entries.append(dict(path=relative,bytes=path.stat().st_size,sha256=checksum))
            if i%50==0:print('PACKING',group,i,len(files),flush=True)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:raise RuntimeError('Archive CRC validation failed')
    parts=[];limit=1024**3
    if archive.stat().st_size<=limit:
        parts=[dict(name=archive.name,bytes=archive.stat().st_size,sha256=digest(archive))]
    else:
        with archive.open('rb') as stream:
            index=1
            while True:
                first=stream.read(8*1024*1024)
                if not first:break
                part=DIST/(archive.name+f'.part{index:03}');written=0
                with part.open('wb') as output:
                    output.write(first);written+=len(first)
                    while written<limit:
                        chunk=stream.read(min(8*1024*1024,limit-written))
                        if not chunk:break
                        output.write(chunk);written+=len(chunk)
                parts.append(dict(name=part.name,bytes=part.stat().st_size,sha256=digest(part)));index+=1
    report=dict(group=group,archive=archive.name,archive_sha256=digest(archive),parts=parts,files=entries,verified=True,wall_seconds=time.perf_counter()-start)
    (DIST/f'{group}-manifest.json').write_text(json.dumps(report,indent=2));print('PACK_COMPLETE',group,len(files),archive.stat().st_size,flush=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('group',choices=['assets','replay','media','manifest']);args=parser.parse_args()
    if args.group!='manifest':pack(args.group);return
    groups=[json.loads((DIST/f'{g}-manifest.json').read_text()) for g in ['assets','replay','media']]
    for group in groups:
        for part in group['parts']:
            path=DIST/part['name']
            if digest(path)!=part['sha256']:raise RuntimeError('Release part mismatch: '+path.name)
    report=dict(version='3.0.0',repository='neelkm/potato-factory-cosim-v3',groups=groups,verified=True)
    (DIST/'release_manifest.json').write_text(json.dumps(report,indent=2));print('RELEASE_PARTS_VERIFIED',sum(len(g['parts']) for g in groups))
if __name__=='__main__':main()

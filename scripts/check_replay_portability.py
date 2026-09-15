"""Check a release replay after verified extraction into a separate folder."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from pxr import Usd,UsdGeom,Sdf,Ar

ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);args=parser.parse_args()
    relocated=args.root.resolve();out=relocated/'output'
    if relocated==ROOT:raise RuntimeError('Use a separately extracted release folder')
    if not json.loads((out/'asset_validation.json').read_text())['passed']:raise RuntimeError('Relocated scene assets have not passed')
    stage=Usd.Stage.Open(str(out/'factory_replay.usdc'))
    if not stage:raise RuntimeError('Relocated replay could not be opened')
    world=stage.GetPrimAtPath('/World');sets=world.GetMetadata('clips') or {};dependencies=[]
    for spec in world.GetPrimStack():
        if not spec.HasInfo('clips'):continue
        for clip in spec.GetInfo('clips').values():
            if 'templateAssetPath' in clip:raise RuntimeError('Factory release requires explicit clip paths')
            assets=list(clip.get('assetPaths',[]))
            if clip.get('manifestAssetPath'):assets.append(clip['manifestAssetPath'])
            for asset in assets:
                if Path(asset.path).is_absolute():raise RuntimeError('Replay contains an absolute clip path')
                resolved=Ar.GetResolver().Resolve(Sdf.ComputeAssetPathRelativeToLayer(spec.layer,asset.path))
                if not resolved:raise RuntimeError('Missing relocated clip: '+asset.path)
                path=Path(str(resolved)).resolve()
                if not path.is_relative_to(relocated):raise RuntimeError('Clip resolves outside the extracted release')
                dependencies.append(path.relative_to(relocated).as_posix())
    if not sets or not dependencies:raise RuntimeError('No recorded value clips found')
    run=json.loads((out/'cache/simulation.json').read_text());paths=json.loads((out/'cache/paths.json').read_text())
    if run.get('error'):raise RuntimeError('Production run failed')
    poses=np.load(out/'cache/poses.npy',mmap_mode='r');peak=0.;water_samples=[]
    try:
        for frame in [0,run['used_frames']-1]:
            for i,path in enumerate(paths):
                transform=np.asarray(UsdGeom.Xformable(stage.GetPrimAtPath(path)).GetLocalTransformation(frame))
                peak=max(peak,float(np.max(np.abs(transform[3,:3]-poses[frame,i,:3]))))
            water_samples.append(len(stage.GetPrimAtPath('/World/WaterReplay').GetAttribute('points').Get(frame)))
    finally:poses._mmap.close()
    layers=[Path(layer.realPath).resolve() for layer in stage.GetUsedLayers() if layer.realPath]
    if any(not p.is_relative_to(relocated) for p in layers):raise RuntimeError('Composed replay layer escapes the extracted release')
    if peak>2e-5 or not all(water_samples):raise RuntimeError('Relocated replay differs from recorded samples')
    report=dict(passed=True,folder=str(relocated),clip_dependencies=sorted(set(dependencies)),max_position_error_m=peak,
                frames=run['used_frames'],water_points_first_last=water_samples,
                assets_manifest_sha256=digest(ROOT/'dist/assets-manifest.json'),replay_manifest_sha256=digest(ROOT/'dist/replay-manifest.json'),
                scope='Verified release archives extracted into a separate folder. All explicit USD clip paths resolve locally; first and last body/water samples match the measured cache. Original replay validation checks every clip boundary.')
    (ROOT/'output/replay_portability_validation.json').write_text(json.dumps(report,indent=2));print('REPLAY_PORTABILITY_PASSED',len(set(dependencies)),peak)

if __name__=='__main__':main()

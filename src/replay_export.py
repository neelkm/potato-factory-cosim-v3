"""Bounded-memory value-clip export of measured simulation samples.

See https://openusd.org/dev/api/stitch_clips_8h.html. The source physics is
unchanged; each small replay segment contains exact 30 Hz owner/water samples.
"""
import argparse, gc, hashlib, json, time
from pxr import UsdUtils
from usd_utils import *

def copied_slice(path,selection):
    for attempt in range(300):
        try:
            mapped=np.load(path,mmap_mode='r')
            result=np.asarray(mapped[selection]).copy();mapped._mmap.close()
            return result
        except (PermissionError,FileNotFoundError):
            if attempt==299:raise
            time.sleep(.1)


def export_clip(cache, paths, first, last, directory):
    target = directory / f'frames_{first:06}_{last:06}.usdc'
    marker = target.with_suffix('.json')
    signature = dict(first=first, last=last, paths=hashlib.sha256(json.dumps(paths).encode()).hexdigest(),
                     cache_created_ns=(cache/'paths.json').stat().st_mtime_ns)
    if target.exists() and marker.exists() and json.loads(marker.read_text()) == signature:
        return target
    poses = copied_slice(cache/'poses.npy',slice(first,last+1))
    stage = Usd.Stage.CreateNew(str(target))
    stage.SetTimeCodesPerSecond(30); stage.SetFramesPerSecond(30)
    stage.SetStartTimeCode(first); stage.SetEndTimeCode(last)
    UsdGeom.Xform.Define(stage, '/World')
    for i, path in enumerate(paths):
        xf = UsdGeom.Xformable(stage.OverridePrim(path))
        op = xf.MakeMatrixXform(); xf.SetResetXformStack(True)
        for offset, row in enumerate(poses[:, i]):
            q = Gf.Quatd(float(row[6]), Gf.Vec3d(*map(float, row[3:6])))
            m = Gf.Matrix4d().SetRotate(q); m.SetTranslateOnly(Gf.Vec3d(*map(float, row[:3])))
            op.Set(m, first+offset)
    mesh = UsdGeom.Mesh.Define(stage, '/World/WaterReplay')
    mesh.CreateSubdivisionSchemeAttr('none'); mesh.SetNormalsInterpolation('vertex')
    for frame in range(first, last+1):
        saved = cache/'liquid_mesh'/f'{frame:06}.npz'
        if saved.exists():
            with np.load(saved) as data:
                verts, faces, normals = data['vertices'], data['faces'], data['normals']
        else:
            from water_mesh import reconstruct
            points = copied_slice(cache/'water.npy',frame)
            verts, faces, normals = reconstruct(points[points[:, 2] > .8])
        mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(verts), frame)
        mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray.FromNumpy(np.full(len(faces), 3, np.int32)), frame)
        mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray.FromNumpy(faces.reshape(-1)), frame)
        mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(normals), frame)
    stage.GetRootLayer().Save()
    del mesh, op, xf, stage
    gc.collect()
    marker.write_text(json.dumps(signature))
    print('REPLAY_SEGMENT_READY', first, last, target.stat().st_size, flush=True)
    return target


def assemble_replay(cache, clips, count, name):
    layer = Sdf.Layer.CreateNew(str(OUT/name))
    if not UsdUtils.StitchClips(layer, [str(p) for p in clips], Sdf.Path('/World'), 0, count-1):
        raise RuntimeError('USD value clip stitching failed')
    layer.subLayerPaths.append('factory.usda'); layer.Save()
    stage = Usd.Stage.Open(layer)
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'))
    stage.SetTimeCodesPerSecond(30); stage.SetFramesPerSecond(30)
    stage.SetStartTimeCode(0); stage.SetEndTimeCode(count-1)
    mat = material(stage, '/World/WaterVisual', (.62, .85, .96), 0, .04)
    shader = UsdShade.Shader.Define(stage, '/World/WaterVisual/Glass')
    shader.CreateImplementationSourceAttr('sourceAsset')
    shader.SetSourceAsset(Sdf.AssetPath('OmniGlass.mdl'), 'mdl'); shader.SetSourceAssetSubIdentifier('OmniGlass', 'mdl')
    shader.CreateInput('glass_color', Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.95, .98, 1))
    shader.CreateInput('glass_ior', Sdf.ValueTypeNames.Float).Set(1.333)
    shader.CreateInput('frosting_roughness', Sdf.ValueTypeNames.Float).Set(.045)
    shader.CreateInput('thin_walled', Sdf.ValueTypeNames.Bool).Set(False); shader.CreateOutput('out', Sdf.ValueTypeNames.Token)
    mat.CreateSurfaceOutput('mdl').ConnectToSource(shader.ConnectableAPI(), 'out')
    bind(stage.GetPrimAtPath('/World/WaterReplay'), mat)
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.RigidBodyAPI): UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
        if prim.HasAPI(UsdPhysics.CollisionAPI): UsdPhysics.CollisionAPI(prim).CreateCollisionEnabledAttr(False)
        if prim.IsA(UsdPhysics.Joint): UsdPhysics.Joint(prim).CreateJointEnabledAttr(False)
        if prim.GetTypeName() == 'PhysxParticleSystem': prim.CreateAttribute('particleSystemEnabled', Sdf.ValueTypeNames.Bool).Set(False)
        if prim.GetTypeName() == 'FmuInstance': prim.CreateAttribute('fmi:enabled', Sdf.ValueTypeNames.Bool).Set(False)
    skin = stage.GetPrimAtPath('/World/_materials/Potato_skin')
    if skin:
        for prim in Usd.PrimRange(skin):
            if prim.GetTypeName() == 'Shader' and prim.GetAttribute('info:id').Get() == 'UsdPreviewSurface':
                prim.GetAttribute('inputs:roughness').Set(.54)
    stage.GetRootLayer().Save()
    # Validate both sides of every segment boundary against measured owner poses.
    paths = json.loads((cache/'paths.json').read_text()); poses = np.load(cache/'poses.npy', mmap_mode='r')
    samples = sorted(set([0, count-1] + [int(p.stem.split('_')[1])+d for p in clips[1:] for d in [-1, 0, 1]]))
    peak = 0.
    for frame in samples:
        if not 0 <= frame < count: continue
        for i, path in enumerate(paths):
            got = np.array(UsdGeom.Xformable(stage.GetPrimAtPath(path)).GetLocalTransformation(frame))
            peak = max(peak, float(np.max(np.abs(got[3, :3]-poses[frame, i, :3]))))
        if len(stage.GetPrimAtPath('/World/WaterReplay').GetAttribute('points').Get(frame)) == 0:
            raise RuntimeError(f'Missing water replay sample at {frame}')
    poses._mmap.close()
    if peak > 2e-5: raise RuntimeError(f'Value-clip boundary position error: {peak}')
    result = dict(passed=True, clips=len(clips), frames=count, boundary_frames=samples, max_position_error_m=peak)
    (cache/'replay_validation.json').write_text(json.dumps(result, indent=2))
    print('REPLAY_BAKED', name, result, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', default='cache'); ap.add_argument('--name', default='factory_replay.usdc')
    ap.add_argument('--chunk-frames', type=int, default=450)
    ap.add_argument('--follow', action='store_true', help='Prepare finished segments during a live simulation')
    ap.add_argument('--max-frames', type=int, help='Bounded export for explicitly labelled replay qualification')
    args = ap.parse_args(); cache = OUT/args.cache
    paths = json.loads((cache/'paths.json').read_text()); directory = cache/'usd_clips'; directory.mkdir(exist_ok=True)
    first = 0; clips = []
    while True:
        report = cache/'simulation.json'; finished = report.exists()
        if finished:
            try:meta = json.loads(report.read_text())
            except json.JSONDecodeError:time.sleep(.1);continue
            if meta.get('error') and not args.max_frames: raise RuntimeError('Cannot publish a replay from a failed production run')
            count = int(meta.get('used_frames', round(meta['seconds']*30)+1))
        else:
            if not args.follow and not args.max_frames: raise RuntimeError('Simulation incomplete; use --follow for live preparation')
            progress = json.loads((cache/'progress.json').read_text()); count = progress.get('used_frames', 0)-2
        if args.max_frames:
            count = min(count, args.max_frames); finished = count == args.max_frames
        if first >= count:
            if finished: break
            time.sleep(.5); continue
        last = min(first+args.chunk_frames-1, count-1)
        if not finished and last-first+1 < args.chunk_frames: time.sleep(.5); continue
        clips.append(export_clip(cache, paths, first, last, directory)); first = last+1
    assemble_replay(cache, clips, count, args.name)


if __name__ == '__main__': main()

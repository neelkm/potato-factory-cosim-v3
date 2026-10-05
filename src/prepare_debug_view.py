"""Extract authored USD collision proxies for the portable debug workspace."""
import json, hashlib
import numpy as np
from scipy.spatial import ConvexHull
from pxr import Usd,UsdGeom,UsdPhysics,Gf
from config import OUT

def main():
    base=OUT/'physics_debug';latest=json.loads((base/'latest_capture.json').read_text());directory=__import__('pathlib').Path(latest['directory'])
    meta=json.loads((directory/'capture.json').read_text());stage=Usd.Stage.Open(str(directory/'scene.usda'));cache=UsdGeom.XformCache()
    shapes=[];unsupported=[]
    for prim in stage.Traverse():
        if not prim.HasAPI(UsdPhysics.CollisionAPI):continue
        if UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() is False:continue
        body=prim
        while body and not body.IsPseudoRoot() and not body.HasAPI(UsdPhysics.RigidBodyAPI):body=body.GetParent()
        path=str(body.GetPath()) if body and not body.IsPseudoRoot() else None
        if path and path not in meta['paths']:continue
        matrix=cache.GetLocalToWorldTransform(prim)
        kind=prim.GetTypeName()
        if kind=='Cube':
            size=UsdGeom.Cube(prim).GetSizeAttr().Get()/2
            points=np.array([[x,y,z] for x in [-size,size] for y in [-size,size] for z in [-size,size]])
        elif kind=='Mesh':points=np.asarray(UsdGeom.Mesh(prim).GetPointsAttr().Get(),float)
        elif kind=='Sphere':
            radius=UsdGeom.Sphere(prim).GetRadiusAttr().Get()
            points=np.array([[radius*np.cos(a)*np.cos(b),radius*np.sin(a)*np.cos(b),radius*np.sin(b)] for a in np.linspace(0,2*np.pi,12,endpoint=False) for b in np.linspace(-np.pi/2,np.pi/2,7)])
        else:unsupported.append(str(prim.GetPath())+':'+kind);continue
        if len(points)<4:continue
        world=np.array([matrix.Transform(Gf.Vec3d(*p)) for p in points])
        center=world.mean(0)
        if not path and not (6.8<center[0]<9.6 and -9<center[1]<.5 and -.1<center[2]<1.2):continue
        if not path and np.ptp(world,axis=0).max()>10:continue
        approximation=UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get() if kind=='Mesh' else None
        if kind=='Mesh' and approximation not in ('convexHull','convexDecomposition'):
            mesh=UsdGeom.Mesh(prim);indices=list(mesh.GetFaceVertexIndicesAttr().Get());counts=list(mesh.GetFaceVertexCountsAttr().Get());faces=[];offset=0
            for n in counts:
                face=indices[offset:offset+n];offset+=n
                faces.extend([[face[0],face[j],face[j+1]] for j in range(1,n-1)])
        else:
            if approximation=='convexDecomposition':unsupported.append(str(prim.GetPath())+':convexDecomposition');continue
            hull=ConvexHull(points);faces=hull.simplices.tolist()
        if path:
            inv=cache.GetLocalToWorldTransform(body).GetInverse();world=np.array([inv.Transform(Gf.Vec3d(*p)) for p in world])
        shapes.append(dict(path=str(prim.GetPath()),body=path,vertices=world.tolist(),faces=faces,
                           source='USD collision proxy',approximation=approximation or kind))
    if unsupported:print('UNSUPPORTED',unsupported)
    payload=dict(schema=1,capture=directory.name,geometry=shapes,unsupported=unsupported,
                 geometry_source='Authored USD collision shapes; convexHull meshes triangulated for display. Not a dump of cooked PhysX meshes.',
                 simulation_sha256=meta['source_sha256'])
    (base/'view.json').write_text(json.dumps(payload,separators=(',',':')))
    print('DEBUG_GEOMETRY',len(shapes),'faces',sum(len(s['faces']) for s in shapes),'unsupported',len(unsupported))

if __name__=='__main__':main()

"""Native contact qualification of the brush module before a full factory run."""
import json,math,msvcrt
import numpy as np
from pxr import Usd,UsdPhysics,Gf,UsdGeom,Sdf
from config import OUT
from physx_engine import PhysXEngine
from scrub_station import ScrubContacts,brush_specs
from ovphysx.types import TensorType

def main():
    lock=(OUT/'simulation.lock').open('a+b');lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    stage=Usd.Stage.CreateNew(str(OUT/'scrub_probe.usda'));stage.GetRootLayer().subLayerPaths=['factory_physx_scrub.usda']
    potatoes=[f'/World/Potato_{i:03d}' for i in range(12)]
    brushpaths=['/World/'+b['name'] for b in brush_specs()]
    keep=potatoes+brushpaths
    m=json.loads((OUT/'manifest.json').read_text())
    keep+=['/World/'+b['name'] for b in m['rollers'] if 1.2<b['pos'][0]<4.75]
    for p in list(stage.GetPrimAtPath('/World').GetChildren()):
        if p.HasAPI(UsdPhysics.RigidBodyAPI) and str(p.GetPath()) not in keep:stage.OverridePrim(p.GetPath()).SetActive(False)
        if p.GetTypeName() in ('PhysxParticleSystem','PhysxParticleSet','FmuInstance'):stage.OverridePrim(p.GetPath()).SetActive(False)
    for p in list(stage.GetPrimAtPath('/World/Joints').GetChildren()):
        targets=UsdPhysics.Joint(p).GetBody1Rel().GetTargets()
        if not targets or str(targets[0]) not in keep:stage.OverridePrim(p.GetPath()).SetActive(False)
    stage.OverridePrim('/World/Water').SetActive(False)
    for i,path in enumerate(potatoes):
        xf=UsdGeom.Xformable(stage.OverridePrim(path));op=xf.MakeMatrixXform()
        op.Set(Gf.Matrix4d().SetTranslate(Gf.Vec3d(1.35+(i%4)*.085,((i//4)-1)*.12,1.56)))
        stage.GetPrimAtPath(path).CreateAttribute('physxRigidBody:angularDamping',Sdf.ValueTypeNames.Float).Set(12.)
    stage.GetRootLayer().Save();stage=None
    engine=PhysXEngine(str(OUT/'scrub_probe.usda'));sensor=ScrubContacts(engine.px,potatoes,brush_specs());frames=[]
    try:
        for tick in range(7200):
            engine.advance();sensor.sample(1/240,(tick+1)/240)
            if tick%8==7:frames.append(engine.read(potatoes,TensorType.RIGID_BODY_POSE))
            if tick%480==479:print('SCRUB_PROBE',round((tick+1)/240,2),'clean',len(sensor.times),'x',frames[-1][:,0].round(3).tolist(),'brush_w',sensor.bv[:,4].round(2).tolist(),flush=True)
            if len(sensor.times)==12 and min(frames[-1][:,0])>3.1:break
        final=frames[-1];report=sensor.report();report.update(passed=len(sensor.times)==12 and float(final[:,0].min())>3.1 and float(final[:,2].min())>1.3,seconds=(tick+1)/240,final_positions=final[:,:3].tolist())
        (OUT/'scrub_probe_validation.json').write_text(json.dumps(report,indent=2));np.save(OUT/'scrub_probe_poses.npy',frames)
        print('SCRUB_PROBE_RESULT',report['passed'],report['contact_rows'],report['slip_metres'],flush=True)
        if not report['passed']:raise RuntimeError('The isolated scrubber qualification failed')
    finally:sensor.close();engine.close();lock.close()
if __name__=='__main__':main()

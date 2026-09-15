"""Native moving/rotating body with off-centre COM and anisotropic inertia.

NVIDIA's zone policy decides both crossings. Our complete-state transaction
executes them. Zero gravity and no contacting geometry permit an independent
first-step ballistic check after each import.
"""
import json,copy,time
import numpy as np
from scipy.spatial.transform import Rotation
from config import OUT
from engine_process import EngineProcess
from coordinator import Coordinator
from framework.zone_bridge import NvidiaTeleportBridge
from framework.coupling import HandoffZone

def author():
    from pxr import Usd,UsdGeom,UsdPhysics,Gf
    path=OUT/'moving_boundary.usda';stage=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,'Z')
    scene=UsdPhysics.Scene.Define(stage,'/World/Physics');scene.CreateGravityDirectionAttr(Gf.Vec3f(0,0,-1));scene.CreateGravityMagnitudeAttr(0.)
    body=UsdGeom.Xform.Define(stage,'/World/Body');body.AddTranslateOp().Set(Gf.Vec3d(-.4,0,2));UsdPhysics.RigidBodyAPI.Apply(body.GetPrim())
    mass=UsdPhysics.MassAPI.Apply(body.GetPrim());mass.CreateMassAttr(1.7);mass.CreateCenterOfMassAttr(Gf.Vec3f(.012,-.009,.005));mass.CreateDiagonalInertiaAttr(Gf.Vec3f(.01,.02,.025))
    shape=UsdGeom.Cube.Define(stage,'/World/Body/Shape');shape.AddScaleOp().Set(Gf.Vec3d(.15,.11,.09));shape.CreateSizeAttr(1.);UsdPhysics.CollisionAPI.Apply(shape.GetPrim())
    stage.GetRootLayer().Save();return path

def world_com(row):return np.asarray(row['pose'][:3])+Rotation.from_quat(row['pose'][3:]).apply(row['com'])
def momentum(row):
    r=Rotation.from_quat(row['pose'][3:]).as_matrix();v=np.asarray(row['velocity']);p=row['mass']*v[:3]
    return np.r_[p,r@np.asarray(row['inertia'])@r.T@v[3:]+np.cross(world_com(row),p)]

def main():
    path=author();engines={};c=None;start=time.perf_counter();reports=[]
    try:
        for name in ['physx','newton']:
            engines[name]=EngineProcess(name);engines[name].call('load',source=str(path),inactive=['/World/Body'])
        row=engines['physx'].call('export_state',paths=['/World/Body'])[0]
        row['pose'][3:]=Rotation.from_euler('xyz',[18,24,-31],degrees=True).as_quat().tolist();row['velocity']=[.5,0,0,0,0,.3]
        r=Rotation.from_euler('xyz',[23,-31,47],degrees=True).as_matrix();row['inertia']=(r@np.diag([.01,.02,.025])@r.T).tolist()
        engines['physx'].call('import_state',states=[row]);engines['physx'].call('set_active',paths=['/World/Body'],active=True)
        c=Coordinator(engines,{'/World/Body':'physx'})
        bridge=NvidiaTeleportBridge(c,[HandoffZone('qualification',('physx','newton'),0,0,0,.03,1.,'teleport')],['/World/Body'])
        reversed_direction=False
        for tick in range(1000):
            old=len(c.events);bridge.update()
            if len(c.events)>old:
                event=c.events[-1];owner=c.owners['/World/Body'];before=engines[owner].call('export_state',paths=['/World/Body'])[0]
                c.advance();after=engines[owner].call('export_state',paths=['/World/Body'])[0]
                predicted=world_com(before)+np.asarray(before['velocity'][:3])/240
                error=float(np.linalg.norm(world_com(after)-predicted));delta=abs(momentum(event['states'][0])-momentum(event['echoed'][0]));transfer_momentum=float(np.max(delta))
                reports.append(dict(destination=owner,first_step_com_error_m=error,transfer_momentum_error=transfer_momentum,
                                    linear_momentum_error_kg_m_s=float(np.max(delta[:3])),angular_momentum_about_world_origin_error_kg_m2_s=float(np.max(delta[3:])),continuity=event['continuity']))
                if error>3e-5 or transfer_momentum>2e-5:raise RuntimeError('Moving handoff conservation failed')
                if len(c.events)==2:break
            else:c.advance()
            state=engines[c.owners['/World/Body']].call('export_state',paths=['/World/Body'])[0]
            if c.owners['/World/Body']=='newton' and state['pose'][0]>.2 and not reversed_direction:
                # An explicitly authored actuator reversal, separate from the
                # transfers under test; do not confuse it with a seam impulse.
                state['velocity'][:3]=[-.5,0,0];engine=engines['newton']
                engine.call('set_active',paths=['/World/Body'],active=False);engine.call('import_state',states=[state]);engine.call('set_active',paths=['/World/Body'],active=True);reversed_direction=True
        result=dict(passed=len(reports)==2,scope=__doc__,cases=reports,events=c.events,wall_seconds=time.perf_counter()-start)
        (OUT/'moving_boundary_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='events'},indent=2))
        if not result['passed']:raise RuntimeError('Both native boundary crossings did not complete')
    finally:
        if c:c.close()
        for engine in engines.values():engine.close()
if __name__=='__main__':main()

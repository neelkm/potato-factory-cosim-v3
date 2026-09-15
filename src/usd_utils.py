"""USD authoring helpers; stock pxr plus NVIDIA's codeless physics schemas."""
from pathlib import Path
import math
import numpy as np
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, UsdLux, UsdRender, Sdf, Gf, Vt, Plug
import ovphysx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
Plug.Registry().RegisterPlugins([str(p) for p in ovphysx.codeless_schema_paths()])

def attr(prim, name, kind, value):
    return prim.CreateAttribute(name, getattr(Sdf.ValueTypeNames, kind), custom=False).Set(value)

def api(prim, name):
    prim.AddAppliedSchema(name)

def xform(stage, path, pos=(0,0,0), quat=None):
    x=UsdGeom.Xform.Define(stage,path)
    x.AddTranslateOp().Set(Gf.Vec3d(*pos))
    if quat is not None: x.AddOrientOp().Set(Gf.Quatf(quat[3],Gf.Vec3f(*quat[:3])))
    return x.GetPrim()

def collision(prim, mesh=False):
    UsdPhysics.CollisionAPI.Apply(prim)
    if mesh: UsdPhysics.MeshCollisionAPI.Apply(prim).CreateApproximationAttr('convexHull')
    api(prim,'PhysxCollisionAPI')
    attr(prim,'physxCollision:contactOffset','Float',.003)
    attr(prim,'physxCollision:restOffset','Float',.0005)

def rigid(prim, mass=1, kinematic=False):
    rb=UsdPhysics.RigidBodyAPI.Apply(prim)
    rb.CreateKinematicEnabledAttr(kinematic)
    UsdPhysics.MassAPI.Apply(prim).CreateMassAttr(mass)
    api(prim,'PhysxRigidBodyAPI')
    attr(prim,'physxRigidBody:enableCCD','Bool',not kinematic)
    attr(prim,'physxRigidBody:solverPositionIterationCount','Int',16)
    attr(prim,'physxRigidBody:solverVelocityIterationCount','Int',4)

def cube(stage,path,pos,size,collide=False):
    c=UsdGeom.Cube.Define(stage,path); c.CreateSizeAttr(1)
    c.AddTranslateOp().Set(Gf.Vec3d(*pos)); c.AddScaleOp().Set(Gf.Vec3f(*size))
    if collide: collision(c.GetPrim())
    return c.GetPrim()

def material(stage,path,color,metal=0,rough=.4,opacity=1):
    m=UsdShade.Material.Define(stage,path)
    s=UsdShade.Shader.Define(stage,path+'/Surface'); s.CreateIdAttr('UsdPreviewSurface')
    for n,t,v in [('diffuseColor','Color3f',Gf.Vec3f(*color)),('metallic','Float',metal),('roughness','Float',rough),('opacity','Float',opacity)]:
        s.CreateInput(n,getattr(Sdf.ValueTypeNames,t)).Set(v)
    m.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(),'surface')
    return m

def bind(prim,mat):
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(mat)

def physics_scene(stage):
    p=UsdPhysics.Scene.Define(stage,'/World/Physics').GetPrim()
    attr(p,'physics:gravityDirection','Vector3f',Gf.Vec3f(0,0,-1))
    attr(p,'physics:gravityMagnitude','Float',9.81)
    api(p,'PhysxSceneAPI')
    for n,k,v in [('enableGPUDynamics','Bool',True),('broadphaseType','Token','GPU'),('solverType','Token','TGS'),('enableCCD','Bool',True),('gpuMaxNumPartitions','Int',8)]:
        attr(p,'physxScene:'+n,k,v)
    return p

def fluid(stage,points,velocities=None):
    p=stage.DefinePrim('/World/WaterSystem','PhysxParticleSystem')
    for n,k,v in [('particleContactOffset','Float',.023),('restOffset','Float',.012),('fluidRestOffset','Float',.013),('solidRestOffset','Float',.013),('solverPositionIterationCount','Int',6),('maxVelocity','Float',10.),('maxNeighborhood','Int',96)]: attr(p,n,k,v)
    p.CreateRelationship('simulationOwner').SetTargets(['/World/Physics'])
    m=UsdShade.Material.Define(stage,'/World/WaterPhysics'); api(m.GetPrim(),'PhysxPBDMaterialAPI')
    for n,v in [('density',1000.),('friction',.08),('viscosity',.02),('cohesion',.02),('surfaceTension',.01)]: attr(m.GetPrim(),'physxPBDMaterial:'+n,'Float',v)
    UsdShade.MaterialBindingAPI.Apply(p).Bind(m,materialPurpose='physics')
    ps=UsdGeom.Points.Define(stage,'/World/Water'); pr=ps.GetPrim(); api(pr,'PhysxParticleSetAPI')
    ps.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.asarray(points,np.float32)))
    ps.CreateWidthsAttr([.032]*len(points))
    ps.CreateVelocitiesAttr(Vt.Vec3fArray.FromNumpy(np.asarray(velocities if velocities is not None else np.zeros_like(points),np.float32)))
    attr(pr,'physxParticle:fluid','Bool',True)
    attr(pr,'physxParticle:selfCollision','Bool',True)
    pr.CreateRelationship('physxParticle:particleSystem').SetTargets([p.GetPath()])
    return pr

def camera_matrix(eye,target):
    return Gf.Matrix4d().SetLookAt(Gf.Vec3d(*eye),Gf.Vec3d(*target),Gf.Vec3d(0,0,1)).GetInverse()

def camera(stage,eye,target,width=1280,height=720,spp=32):
    c=UsdGeom.Camera.Define(stage,'/World/Camera')
    c.AddTransformOp().Set(camera_matrix(eye,target)); c.CreateFocalLengthAttr(35)
    c.CreateHorizontalApertureAttr(36); c.CreateVerticalApertureAttr(36*height/width)
    c.CreateClippingRangeAttr(Gf.Vec2f(.03,1000))
    api(c.GetPrim(),'OmniSensorGenericCameraCoreAPI')
    p=UsdRender.Product.Define(stage,'/Render/Camera'); p.CreateResolutionAttr(Gf.Vec2i(width,height))
    p.CreateCameraRel().SetTargets([c.GetPath()])
    v=UsdRender.Var.Define(stage,'/Render/Camera/LdrColor'); v.CreateSourceNameAttr('LdrColor')
    p.CreateOrderedVarsRel().SetTargets([v.GetPath()])
    for n,k,v in [('rendermode','Token','PathTracing'),('pt:samplesPerPixel','UInt',spp),('pt:denoising:enabled','Bool',True),('pt:limits:maxBounces','UInt',4)]: attr(p.GetPrim(),'omni:rtx:'+n,k,v)
    attr(p.GetPrim(),'omni:rtx:background:source:type','Token','color')
    attr(p.GetPrim(),'omni:rtx:background:source:color','Color3f',Gf.Vec3f(.18,.22,.22))
    return c

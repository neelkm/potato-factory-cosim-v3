import json,math
from usd_utils import *
from config import BELT_SPEED,FILL
from fmi_control import author
def make_stage():
    m=json.loads((OUT/'manifest.json').read_text());s=Usd.Stage.CreateNew(str(OUT/'factory.usda'))
    s.GetRootLayer().subLayerPaths=['factory_geometry.usdc'];s.SetDefaultPrim(s.GetPrimAtPath('/World'))
    UsdGeom.SetStageMetersPerUnit(s,1);UsdGeom.SetStageUpAxis(s,'Z');s.SetTimeCodesPerSecond(30);physics_scene(s)
    def friction(name,mu):
        mat=UsdShade.Material.Define(s,'/World/'+name);p=UsdPhysics.MaterialAPI.Apply(mat.GetPrim());p.CreateStaticFrictionAttr(mu);p.CreateDynamicFrictionAttr(mu*.85);p.CreateRestitutionAttr(0)
        return mat
    default=friction('Contact',.6);bedmat=friction('TruckContact',.22);beltmat=friction('BeltContact',.95);cardmat=friction('CardContact',.8);guide=friction('PolishedGuides',.035)
    api(guide.GetPrim(),'PhysxMaterialAPI');attr(guide.GetPrim(),'physxMaterial:frictionCombineMode','Token','min')
    def contact(p,mat=default):UsdShade.MaterialBindingAPI.Apply(p).Bind(mat,materialPurpose='physics')
    proxies=xform(s,'/World/CollisionProxies');UsdGeom.Imageable(proxies).CreateVisibilityAttr('invisible')
    for i,o in enumerate(m['static']):
        p=cube(s,f'/World/CollisionProxies/C{i:03}',o['pos'],o['size'],True);contact(p,guide if any(k in o['name'].lower() for k in ['guide','lane','funnel','chute']) else default)
        for axis in ['x','y','z']:
            if o.get('rotate_'+axis):
                xf=UsdGeom.Xformable(p);ops=xf.GetOrderedXformOps();r=getattr(xf,'AddRotate'+axis.upper()+'Op')();r.Set(o['rotate_'+axis]);xf.SetXformOpOrder([ops[0],r,ops[-1]])
    for o in m['bodies']:
        path='/World/'+o['name'];p=s.GetPrimAtPath(path);rigid(p,o['mass'],o['kinematic'])
        ma=guide if o.get('vibrating') or o['name']=='RejectGate' else bedmat if o['name']=='TruckBed' else beltmat if 'Belt' in o['name'] else cardmat
        for i,(pos,size) in enumerate(o['shapes']):
            c=cube(s,path+f'/Collider{i}',pos,size,True);UsdGeom.Imageable(c).CreateVisibilityAttr('invisible');contact(c,ma)
            if o['name'].startswith('Flap_'):
                attr(c,'physxCollision:contactOffset','Float',.0005);attr(c,'physxCollision:restOffset','Float',0.)
    for b in m['belts']:
        p=s.GetPrimAtPath('/World/'+b['name']);api(p,'PhysxSurfaceVelocityAPI')
        attr(p,'physxSurfaceVelocity:surfaceVelocity','Vector3f',Gf.Vec3f(*b['velocity']));attr(p,'physxSurfaceVelocity:surfaceVelocityEnabled','Bool',True);attr(p,'physxSurfaceVelocity:surfaceVelocityLocalSpace','Bool',False)
    for o in m['rollers']:
        path='/World/'+o['name'];p=s.GetPrimAtPath(path);rigid(p,1.2)
        c=UsdGeom.Cylinder.Define(s,path+'/Collider');c.CreateRadiusAttr(o['radius']);c.CreateHeightAttr(o['width']);c.CreateAxisAttr('Y');c.CreateVisibilityAttr('invisible');collision(c.GetPrim());contact(c.GetPrim(),beltmat)
        j=UsdPhysics.RevoluteJoint.Define(s,'/World/Joints/'+o['name']);j.CreateBody1Rel().SetTargets([path]);j.CreateLocalPos0Attr(Gf.Vec3f(*o['pos']));j.CreateAxisAttr('Y')
        d=UsdPhysics.DriveAPI.Apply(j.GetPrim(),'angular');d.CreateTypeAttr('force');d.CreateTargetVelocityAttr(math.degrees(BELT_SPEED/o['radius']));d.CreateDampingAttr(100);d.CreateStiffnessAttr(0);d.CreateMaxForceAttr(30)
    for o in m['potatoes']:
        p=s.GetPrimAtPath('/World/'+o['name']);rigid(p,o['mass']);attr(p,'physxRigidBody:angularDamping','Float',.25)
        for c in Usd.PrimRange(p):
            if c.IsA(UsdGeom.Mesh):collision(c,True);contact(c)
        attr(p,'factory:defectFraction','Float',o['defect_fraction']);attr(p,'factory:damaged','Bool',o['damaged'])
    for o in m['flaps']:
        j=UsdPhysics.Joint.Define(s,'/World/Joints/'+o['name']);j.CreateBody0Rel().SetTargets(['/World/'+o['box']]);j.CreateBody1Rel().SetTargets(['/World/'+o['name']]);j.CreateLocalPos0Attr(Gf.Vec3f(*o['anchor']));j.CreateCollisionEnabledAttr(False)
        for axis in ['transX','transY','transZ','rotX','rotY','rotZ']:
            l=UsdPhysics.LimitAPI.Apply(j.GetPrim(),axis);l.CreateLowAttr(1);l.CreateHighAttr(-1)
    points=[((x-26.5)*.026,(y-5.5)*.026,.925+z*.026) for x in range(54) for y in range(12) for z in range(4)]
    water=fluid(s,points,[(0,0,0)]*len(points));UsdGeom.Imageable(water).CreateVisibilityAttr('invisible')
    camera(s,(20,-27,17),(1,-.4,1),1920,1080,48)
    sky=UsdLux.DomeLight.Define(s,'/World/Sky');sky.CreateIntensityAttr(450);sky.CreateColorAttr(Gf.Vec3f(.82,.90,1))
    if (OUT/'hangar_interior_4k.hdr').exists():
        sky.CreateTextureFileAttr(Sdf.AssetPath('hangar_interior_4k.hdr'));sky.CreateTextureFormatAttr('latlong');sky.CreateIntensityAttr(160);sky.CreateColorAttr(Gf.Vec3f(1))
    sun=UsdLux.DistantLight.Define(s,'/World/Sun');sun.CreateIntensityAttr(1300);sun.CreateAngleAttr(3.0);sun.CreateColorAttr(Gf.Vec3f(1,.91,.78));sun.AddRotateXYZOp().Set((25,-35,-25))
    guard=UsdShade.Material.Define(s,'/World/GuardGlass');sh=UsdShade.Shader.Define(s,'/World/GuardGlass/Surface');sh.CreateImplementationSourceAttr('sourceAsset');sh.SetSourceAsset(Sdf.AssetPath('OmniGlass.mdl'),'mdl');sh.SetSourceAssetSubIdentifier('OmniGlass','mdl')
    sh.CreateInput('glass_color',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.96,.99,1));sh.CreateInput('glass_ior',Sdf.ValueTypeNames.Float).Set(1.05);sh.CreateInput('thin_walled',Sdf.ValueTypeNames.Bool).Set(True);sh.CreateInput('frosting_roughness',Sdf.ValueTypeNames.Float).Set(.06);sh.CreateOutput('out',Sdf.ValueTypeNames.Token);guard.CreateSurfaceOutput('mdl').ConnectToSource(sh.ConnectableAPI(),'out')
    for p in s.GetPrimAtPath('/World').GetChildren():
        if p.GetName().startswith('Guide_wash'):
            pos=p.GetAttribute('xformOp:translate').Get()
            if pos and pos[1]<0:UsdShade.MaterialBindingAPI.Apply(p).Bind(guard,bindingStrength=UsdShade.Tokens.strongerThanDescendants)
    author(s)
    from partition_stages import assemble_partitions
    assemble_partitions(s,m)
    s.GetRootLayer().Save();print('V3_STAGE_COMPLETE',flush=True)
if __name__=='__main__':make_stage()

"""An additive USD variant: originals, replay and imported assets stay intact."""
import json,math,random
from usd_utils import *
from scrub_station import brush_specs,START,END,RADIUS

def cylinder(stage,path,pos,radius,height,ma,axis='Y'):
    c=UsdGeom.Cylinder.Define(stage,path);c.CreateRadiusAttr(radius);c.CreateHeightAttr(height);c.CreateAxisAttr(axis)
    c.AddTranslateOp().Set(Gf.Vec3d(*pos));bind(c.GetPrim(),ma);return c.GetPrim()

def make():
    specs=brush_specs();m=json.loads((OUT/'manifest.json').read_text())
    removed=[]  # Continuous driven feed remains beneath the soft overhead brushes.
    visual=Usd.Stage.CreateNew(str(OUT/'scrub_visuals.usda'));UsdGeom.SetStageUpAxis(visual,'Z');UsdGeom.SetStageMetersPerUnit(visual,1)
    steel=material(visual,'/World/ScrubMaterials/Stainless',(.48,.54,.57),.92,.24)
    black=material(visual,'/World/ScrubMaterials/Nylon',(.025,.065,.085),.05,.67)
    nylon=material(visual,'/World/ScrubMaterials/NylonTips',(.09,.20,.23),.02,.74)
    accent=material(visual,'/World/ScrubMaterials/Safety',(.91,.60,.12),.18,.36)
    water=material(visual,'/World/ScrubMaterials/WetTray',(.07,.15,.17),.45,.15)
    rng=random.Random(105)
    for spec in specs:
        path='/World/'+spec['name'];xform(visual,path,spec['pos'])
        cylinder(visual,path+'/Hub',(0,0,0),.016,spec['width'],black)
        cylinder(visual,path+'/Axle',(0,0,0),.009,1.66,steel)
        # Joined tapered bristle bundles avoid thousands of separate USD prims.
        vertices=[];faces=[]
        for y in np.linspace(-spec['width']/2,spec['width']/2,65):
            for k in range(40):
                angle=k*2*math.pi/40+y*4;r=RADIUS+rng.uniform(-.001,.001)
                radial=np.array([math.sin(angle),0,math.cos(angle)]);side=np.array([math.cos(angle),0,-math.sin(angle)])*.001
                base=radial*.016+np.array([0,y,0]);tip=radial*r+np.array([0,y+rng.uniform(-.001,.001),0]);start=len(vertices)
                vertices.extend([base-side,base+side,tip+side*.35,tip-side*.35]);faces.append([start,start+1,start+2,start+3])
        mesh=UsdGeom.Mesh.Define(visual,path+'/NylonBristles');mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.asarray(vertices,np.float32)))
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray([4]*len(faces)));mesh.CreateFaceVertexIndicesAttr(Vt.IntArray(np.asarray(faces).ravel().tolist()))
        mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDoubleSidedAttr(True);bind(mesh.GetPrim(),nylon)
        for y in [-.84,.84]:
            housing=cube(visual,f'/World/ScrubStation/Bearing_{spec["name"]}_{"L" if y<0 else "R"}',(spec['pos'][0],y,spec['pos'][2]),(.066,.07,.08));bind(housing,steel)
    for y in [-.90,.90]:
        bind(cube(visual,f'/World/ScrubStation/Skirt_{"L" if y<0 else "R"}',(2.34,y,1.17),(1.37,.035,.43)),steel)
        bind(cube(visual,f'/World/ScrubStation/Rim_{"L" if y<0 else "R"}',(2.34,y,1.39),(1.42,.085,.035)),steel)
        for x in [1.79,2.87]:
            bind(cube(visual,f'/World/ScrubStation/Leg_{str(x).replace(".","_")}_{"L" if y<0 else "R"}',(x,y,.55),(.06,.06,1.10)),steel)
            cylinder(visual,f'/World/ScrubStation/Foot_{str(x).replace(".","_")}_{"L" if y<0 else "R"}',(x,y,.045),.075,.045,black,'Z')
    bind(cube(visual,'/World/ScrubStation/CollectionTray',(2.34,0,1.08),(1.35,1.72,.035)),water)
    # Slotted catch screen and a visible service drain: presentation geometry.
    for i,x in enumerate(np.linspace(1.8,2.88,37)):
        bind(cube(visual,f'/World/ScrubStation/DrainGrate_{i}',(float(x),0,1.105),(.012,1.64,.008)),steel)
    cylinder(visual,'/World/ScrubStation/Drain',(2.84,.66,.92),.035,.30,steel,'Z')
    cylinder(visual,'/World/ScrubStation/DriveMotor',(2.30,1.05,1.20),.095,.25,black,'Y')
    bind(cube(visual,'/World/ScrubStation/DriveCover',(2.34,.91,1.595),(1.36,.12,.19)),steel)
    bind(cube(visual,'/World/ScrubStation/ControlCabinet',(2.95,.99,1.44),(.20,.12,.31)),steel)
    cylinder(visual,'/World/ScrubStation/EmergencyStop',(2.95,.914,1.51),.025,.018,accent,'Y')
    for x in [1.85,2.35,2.85]:
        cylinder(visual,f'/World/ScrubStation/ServiceTube_{str(x).replace(".","_")}',(x,.84,1.60),.011,.30,steel,'Z')
    from scrub_presentation import service_light
    service_light(visual)
    visual.GetRootLayer().Save()
    stage=Usd.Stage.CreateNew(str(OUT/'factory_scrub.usda'));stage.GetRootLayer().subLayerPaths=(['scrub_labels.usdc'] if (OUT/'scrub_labels.usdc').exists() else [])+['scrub_visuals.usda','factory.usda']
    stage.SetDefaultPrim(stage.GetPrimAtPath('/World'));UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1)
    for name in removed:
        stage.OverridePrim('/World/'+name).SetActive(False);stage.OverridePrim('/World/Joints/'+name).SetActive(False)
    brushmat=UsdShade.Material.Define(stage,'/World/ScrubContact');ma=UsdPhysics.MaterialAPI.Apply(brushmat.GetPrim())
    ma.CreateStaticFrictionAttr(.85);ma.CreateDynamicFrictionAttr(.70);ma.CreateRestitutionAttr(0)
    api(brushmat.GetPrim(),'PhysxMaterialAPI');attr(brushmat.GetPrim(),'physxMaterial:compliantContactStiffness','Float',120.)
    attr(brushmat.GetPrim(),'physxMaterial:compliantContactDamping','Float',.8)
    for spec in specs:
        path='/World/'+spec['name'];p=stage.GetPrimAtPath(path);rigid(p,.35)
        api(p,'PhysxContactReportAPI');attr(p,'physxContactReport:threshold','Float',0.)
        c=UsdGeom.Cylinder.Define(stage,path+'/Collider');c.CreateRadiusAttr(spec['radius']);c.CreateHeightAttr(spec['width']);c.CreateAxisAttr('Y');c.CreateVisibilityAttr('invisible')
        collision(c.GetPrim());attr(c.GetPrim(),'physxCollision:contactOffset','Float',.001);attr(c.GetPrim(),'physxCollision:restOffset','Float',0.)
        UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(brushmat,materialPurpose='physics')
        joint=UsdPhysics.RevoluteJoint.Define(stage,'/World/Joints/'+spec['name']);joint.CreateBody1Rel().SetTargets([path]);joint.CreateLocalPos0Attr(Gf.Vec3f(*spec['pos']));joint.CreateAxisAttr('Y')
        drive=UsdPhysics.DriveAPI.Apply(joint.GetPrim(),'angular');drive.CreateTypeAttr('force');drive.CreateTargetVelocityAttr(math.degrees(.3/spec['radius']*spec['speed_ratio']))
        drive.CreateDampingAttr(2.);drive.CreateStiffnessAttr(0.);drive.CreateMaxForceAttr(.6)
    group=UsdPhysics.CollisionGroup.Get(stage,'/World/ConveyorFilters/Rollers')
    includes=group.GetCollidersCollectionAPI().GetIncludesRel().GetTargets()
    group.GetCollidersCollectionAPI().CreateIncludesRel().SetTargets(includes+[Sdf.Path('/World/'+s['name']+'/Collider') for s in specs])
    stage.GetPrimAtPath('/World').CreateAttribute('factory:scrubbingEnabled',Sdf.ValueTypeNames.Bool).Set(True)
    stage.GetRootLayer().Save()
    physx=Usd.Stage.CreateNew(str(OUT/'factory_physx_scrub.usda'));physx.GetRootLayer().subLayerPaths=['factory_scrub.usda']
    for name in ['Franka','Tool']:physx.OverridePrim('/World/'+name).SetActive(False)
    physx.SetDefaultPrim(physx.GetPrimAtPath('/World'));physx.GetRootLayer().Save()
    (OUT/'scrub_config.json').write_text(json.dumps(dict(brushes=specs,disabled_rollers=removed,source='factory_physx_scrub.usda',presentation='factory_scrub.usda'),indent=2))
    print('SCRUB_STAGE_READY',len(specs),'brushes',len(removed),'replaced rollers')
if __name__=='__main__':make()

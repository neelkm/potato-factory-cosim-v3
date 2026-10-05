"""Presentation-only service light; no change to the simulated brush geometry."""
from usd_utils import *
from pxr import UsdLux

def service_light(stage):
    steel=UsdShade.Material.Get(stage,'/World/ScrubMaterials/Stainless')
    for x in [1.82,2.85]:
        p=cube(stage,f'/World/ScrubStation/LightPost_{str(x).replace(".","_")}',(x,.88,2.06),(.024,.024,1.07));bind(p,steel)
    bind(cube(stage,'/World/ScrubStation/LightHousing',(2.34,.70,2.60),(1.30,.18,.04)),steel)
    light=UsdLux.RectLight.Define(stage,'/World/ScrubStation/ServiceLight')
    light.CreateWidthAttr(1.20);light.CreateHeightAttr(.12);light.CreateIntensityAttr(1600.)
    light.CreateColorAttr(Gf.Vec3f(.95,.98,1.))
    xf=UsdGeom.Xformable(light);xf.ClearXformOpOrder();xf.AddTranslateOp().Set(Gf.Vec3d(2.34,.70,2.57))

if __name__=='__main__':
    s=Usd.Stage.Open(str(OUT/'scrub_visuals.usda'));service_light(s);s.GetRootLayer().Save()
    layer=Sdf.Layer.FindOrOpen(str(OUT/'factory_scrub.usda'))
    if (OUT/'scrub_labels.usdc').exists() and 'scrub_labels.usdc' not in layer.subLayerPaths:
        layer.subLayerPaths.insert(0,'scrub_labels.usdc');layer.Save()
    print('SCRUB_PRESENTATION_READY')

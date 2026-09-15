"""Author standard NVIDIA cosim cell/port topology and a separate FMI stage."""
from pathlib import Path
from pxr import Usd,Sdf,UsdGeom
from fmi_control import author,INPUTS,OUTPUTS
from config import ROOT,OUT

def main():
    stage=Usd.Stage.CreateNew(str(ROOT/'configs/factory_topology.usda'))
    root=stage.DefinePrim('/Factory','Scope');stage.SetDefaultPrim(root)
    def attr(prim,name,kind,value):prim.CreateAttribute(name,kind,custom=True).Set(value)
    attr(root,'factory:version',Sdf.ValueTypeNames.String,'3.0.0')
    attr(root,'factory:contactPolicy',Sdf.ValueTypeNames.Token,'assembly_transaction')
    descriptions={'sensors':('sense',[('Inputs','output','inputs')]),'controller':('control',[('Inputs','input','inputs'),('Outputs','output','outputs')]),
                  'line':('line',[('Outputs','input','outputs')]),'packing':('packing',[('Interlocks','input','outputs')])}
    for name,(callback,ports) in descriptions.items():
        cell=stage.DefinePrim('/Factory/'+name,'OmniSimCell')
        attr(cell,'sim:cell:role',Sdf.ValueTypeNames.Token,'controlPlant' if name in ('sensors','controller') else 'workcell')
        engine=stage.DefinePrim(str(cell.GetPath())+'/Engine','OmniSimEngine')
        for key,value in [('kind','script'),('script',callback),('device','cpu')]:attr(engine,'sim:engine:'+key,Sdf.ValueTypeNames.Token,value)
        attr(engine,'sim:engine:rateHz',Sdf.ValueTypeNames.Double,30.)
        attr(engine,'factory:backend',Sdf.ValueTypeNames.Token,{'sensors':'ovphysx','controller':'ovfmi','line':'ovphysx','packing':'ovnewton'}[name])
        for port_name,direction,layout in ports:
            port=stage.DefinePrim(str(cell.GetPath())+'/'+port_name,'OmniSimPort')
            for key,value in [('direction',direction),('quantity','signal'),('frame','controller')]:attr(port,'sim:port:'+key,Sdf.ValueTypeNames.Token,value)
            attr(port,'sim:port:rateHz',Sdf.ValueTypeNames.Double,30.)
            attr(port,'sim:port:count',Sdf.ValueTypeNames.Int,1);attr(port,'sim:port:width',Sdf.ValueTypeNames.Int,10)
            attr(port,'factory:layout',Sdf.ValueTypeNames.String,','.join((INPUTS if layout=='inputs' else OUTPUTS)+['physicsTick']))
            attr(port,'factory:units',Sdf.ValueTypeNames.String,'dimensionless values; integer physics tick at 240 Hz')
    for index,(source,target) in enumerate([('sensors/Inputs','controller/Inputs'),('controller/Outputs','line/Outputs'),('controller/Outputs','packing/Interlocks')]):
        edge=stage.DefinePrim('/Factory/Edge'+str(index),'OmniSimCoupling')
        for key,value in [('source',source),('target',target),('mode','signalExchange')]:attr(edge,'sim:coupling:'+key,Sdf.ValueTypeNames.String,value)
    stage.GetRootLayer().Save()
    control=Usd.Stage.CreateNew(str(OUT/'factory_fmi.usda'));UsdGeom.Xform.Define(control,'/World');control.SetDefaultPrim(control.GetPrimAtPath('/World'));author(control);control.GetRootLayer().Save()
    factory=Usd.Stage.Open(str(OUT/'factory.usda'));attr(factory.GetPrimAtPath('/World'),'factory:releaseVersion',Sdf.ValueTypeNames.String,'3.0.0')
    attr(factory.GetPrimAtPath('/World'),'factory:topology',Sdf.ValueTypeNames.Asset,Sdf.AssetPath('../configs/factory_topology.usda'))
    factory.GetRootLayer().Save()
    print('V3_TOPOLOGY_AUTHORED')
if __name__=='__main__':main()

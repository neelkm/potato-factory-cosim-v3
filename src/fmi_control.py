"""Real native FMI2 controller hosted by ovfmi, with USD-declared I/O."""
import json,os,sys
import numpy as np
from config import OUT
INPUTS=['presence','objectId','defectScore','washed','boxCount','boxReady','armBusy','palletCount','targetCount']
OUTPUTS=['acceptPulse','rejectPulse','decisionId','valvePressure','conveyorRun','packRequest','forkliftRequest','acceptedTotal','rejectedTotal']
def author(s):
    from pxr import Sdf,Gf
    c=s.DefinePrim('/World/Control','Scope')
    f=s.DefinePrim('/World/FactoryController','FmuInstance')
    f.CreateAttribute('fmi:enabled',Sdf.ValueTypeNames.Bool).Set(True)
    f.CreateAttribute('fmi:fmu',Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath('FactoryController.fmu'))
    io=s.DefinePrim(str(f.GetPath())+'/IO','FmuConnection');io.CreateRelationship('fmi:targets').SetTargets([c.GetPath()])
    for name in INPUTS+OUTPUTS:
        c.CreateAttribute('qc:'+name,Sdf.ValueTypeNames.Double).Set(18. if name=='targetCount' else 0.)
        m=s.DefinePrim(str(io.GetPath())+'/'+name,'FmuMapping')
        for k,v in [('direction','input' if name in INPUTS else 'output'),('fmuAttribute',name),('usdAttribute','qc:'+name)]:m.CreateAttribute('fmi:'+k,Sdf.ValueTypeNames.Token).Set(v)
        # Explicit scalar component avoids ovfmi 0.2's (0,0) list start-value bug.
        m.CreateAttribute('fmi:usdMapping',Sdf.ValueTypeNames.Int2).Set(Gf.Vec2i(0,1))
class Controller:
    def __init__(self,stage,source=None):
        from ovfmi import FmiHost
        os.environ['USD_PYTHON']=sys.executable
        self.host=FmiHost();self.report=self.host.attach_ovstage(stage,source_asset=str(source or OUT/'factory.usda'))
        assert len(self.report.instances)==1,self.report
    def step(self,dt,**inputs):
        from ovfmi import AttributeWrite
        op=self.host.write([AttributeWrite(('/World/Control',),'qc:'+k,[float(v)]) for k,v in inputs.items()]);self.host.wait_op(op)
        self.host.step_sync(dt)
        with self.host.read() as r:return {g.attribute_name.split(':')[-1]:float(np.asarray(g.tensors[0]).reshape(-1)[0]) for g in r.groups}
    def close(self):self.host.release()
if __name__=='__main__':
    from pxr import Usd,UsdGeom
    import ovstage
    path=OUT/'fmi_probe.usda';s=Usd.Stage.CreateNew(str(path));UsdGeom.Xform.Define(s,'/World');author(s);s.GetRootLayer().Save()
    st=ovstage.Stage('fmi-validation');ovstage.population.open_usd(st,str(path),ordinal=1);st.advance_write_floor(1).wait();c=Controller(st,path)
    good=[]
    for i in range(5):good.append(c.step(1/30,presence=1,objectId=1,defectScore=.01,washed=1,boxCount=0,boxReady=1,armBusy=0,palletCount=0))
    assert good[-1]['acceptedTotal']==1 and good[-1]['rejectedTotal']==0,good
    bad=[c.step(1/30,presence=1,objectId=2,defectScore=.25,washed=1) for _ in range(5)]
    assert bad[-1]['acceptedTotal']==1 and bad[-1]['rejectedTotal']==1,bad
    full=c.step(1/30,presence=0,boxCount=18);assert full['packRequest']==1 and full['conveyorRun']==0,full
    partial=c.step(1/30,boxCount=16,targetCount=17);assert partial['packRequest']==0 and partial['conveyorRun']==1,partial
    balanced=c.step(1/30,boxCount=17,targetCount=17);assert balanced['packRequest']==1 and balanced['conveyorRun']==0,balanced
    six=c.step(1/30,palletCount=6);assert six['forkliftRequest']==1,six
    (OUT/'fmi_validation.json').write_text(json.dumps({'good':good,'bad':bad,'full':full,'partial':partial,'balanced':balanced,'six':six},indent=2));print('OVFMI_VALIDATED',flush=True);c.close();st.destroy()

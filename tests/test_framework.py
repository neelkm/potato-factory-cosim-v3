import copy
import numpy as np
import pytest
from coordinator import Coordinator
from state_protocol import Transfer,continuity
from framework.shared_snapshot import SharedSnapshot
from framework.graph import FactoryGraph,validate_contracts,ROOT
from framework.profiles import get_profile,Profile
from fmi_control import INPUTS,OUTPUTS

def body(path='/Box'):
    return dict(path=path,pose=[1,2,3,0,0,0,1],velocity=[.2,0,0,0,0,.1],mass=2.,com=[.01,0,0],inertia=np.diag([.1,.2,.25]).tolist())

class Worker:
    def __init__(self,states=(),inactive=()):
        self.states={r['path']:copy.deepcopy(r) for r in states};self.inactive=set(inactive)
        self.tick=0;self.metrics={};self.calls=[];self.corrupt=False;self.bad_clock=False
    def call(self,method,**args):
        self.calls.append((method,args))
        if method=='export_state':
            result=copy.deepcopy([self.states[p] for p in args['paths']])
            if self.corrupt:result[0]['pose'][0]+=1
            return result
        if method=='import_state':self.states.update({r['path']:copy.deepcopy(r) for r in args['states']});return True
        if method=='set_active':
            for p in args['paths']:
                if args['active']:self.inactive.discard(p)
                else:self.inactive.add(p)
            return {'inactive':list(self.inactive)}
        if method=='advance':self.tick+=args['steps']+(1 if self.bad_clock else 0);return {'tick':self.tick}
        if method=='collect_inputs':return dict.fromkeys(INPUTS,0.)
        if method=='control':self.tick+=8;return dict.fromkeys(OUTPUTS,0.)
        if method=='apply_controls':return True
        raise AssertionError(method)

def test_native_tick_divergence_prevents_every_later_step():
    a=Worker();b=Worker();b.bad_clock=True;c=Coordinator({'a':a,'b':b},{})
    try:
        with pytest.raises(RuntimeError,match='clocks'):c.advance(8)
        calls=len(a.calls)+len(b.calls)
        with pytest.raises(RuntimeError,match='failed'):c.advance(8)
        assert len(a.calls)+len(b.calls)==calls and c.tick==0
    finally:c.close()

def test_transfer_rollback_restores_sender_and_remains_halted():
    a=Worker([body()]);b=Worker([body()],['/Box']);b.corrupt=True
    c=Coordinator({'a':a,'b':b},{'/Box':'a'})
    try:
        with pytest.raises(RuntimeError,match='continuity'):c.transfer(['/Box'],'a','b')
        assert c.pending_transfer['phase']=='rolled_back' and c.owners['/Box']=='a'
        assert '/Box' not in a.inactive and '/Box' in b.inactive
        with pytest.raises(RuntimeError,match='failed'):c.advance()
    finally:c.close()

def test_transfer_records_receiver_evidence():
    a=Worker([body()]);b=Worker([body()],['/Box']);c=Coordinator({'a':a,'b':b},{'/Box':'a'})
    try:
        event=c.transfer(['/Box'],'a','b');assert event['echoed']==event['states']
        assert event['protocol_version']==2 and c.owners['/Box']=='b'
        assert '/Box' in a.inactive and '/Box' not in b.inactive
    finally:c.close()

def test_invalid_joint_or_membership_is_rejected_before_freeze():
    with pytest.raises(ValueError,match='Incomplete'):Transfer(0,'a','b',[body()],{'/Box':['/Missing']},{}).validate()
    with pytest.raises(ValueError,match='boundary'):Transfer(0,'a','b',[body()],{}, {'/Joint':{'parent':'/Box','child':'/Missing'}}).validate()
    with pytest.raises(ValueError,match='joint frame'):Transfer(0,'a','b',[body(),body('/Lid')],{}, {'/Joint':{'parent':'/Box','child':'/Lid'}}).validate()

def test_quaternion_sign_and_small_body_inertia():
    a=body();b=copy.deepcopy(a);b['pose'][6]=-1
    assert continuity([a],[b])['orientation_rad']==0
    a['inertia']=(np.eye(3)*1e-6).tolist();b=copy.deepcopy(a);b['inertia'][0][0]*=1.01
    with pytest.raises(RuntimeError,match='continuity'):continuity([a],[b])

def test_shared_snapshot_roundtrip_and_order_guard():
    owner=SharedSnapshot(['/Box'],2);child=SharedSnapshot(descriptor=owner.descriptor())
    try:
        receipt=child.write({'paths':['/Box'],'poses':[body()['pose']],'water':[[1,2,3]],'status':{'tick':8}})
        read=owner.read(receipt)
        np.testing.assert_array_equal(read['poses'],[body()['pose']]);assert read['tick']==8 and len(read['water'])==1
        with pytest.raises(RuntimeError,match='ordering'):child.write({'paths':['/Other'],'poses':[[0]*7]})
        del read
    finally:child.close();owner.close()

def test_actual_nvidia_graph_routes_fresh_samples_and_halts_on_clock_error():
    a,b,fmi=Worker(),Worker(),Worker();c=Coordinator({'physx':a,'newton':b},{})
    g=FactoryGraph(c,fmi,get_profile('production'))
    try:
        for _ in range(3):g.step()
        assert c.tick==a.tick==b.tick==fmi.tick==24 and g.samples==3
        assert g.report()['batches']==[['sensors'],['controller'],['line','packing']]
        b.bad_clock=True
        with pytest.raises(RuntimeError,match='clocks'):g.step()
        with pytest.raises(RuntimeError,match='failed'):g.step()
    finally:g.close();c.close()

def test_contract_rate_mismatch_requires_adapter(tmp_path):
    from pxr import Usd
    stage=Usd.Stage.Open(str(ROOT/'configs/factory_topology.usda'))
    path=tmp_path/'wrong_rate.usda';stage.GetRootLayer().Export(str(path));stage=Usd.Stage.Open(str(path))
    stage.GetPrimAtPath('/Factory/line/Outputs').GetAttribute('sim:port:rateHz').Set(60.)
    stage.GetRootLayer().Save()
    with pytest.raises(ValueError,match='rate adapter'):validate_contracts(path)

def test_factory_rejects_unqualified_contact_policy():
    with pytest.raises(ValueError,match='assemblies'):Profile('unsafe',contact_policy='nvidia_proxy_force').validate()

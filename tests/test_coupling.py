import numpy as np
import pytest
from framework.coupling import *

def test_factory_auto_keeps_contacts_together():
    assert select_policy(assembly=True,contact_across_boundary=True,capabilities=FACTORY_CAPABILITIES)=='assembly_transaction'
    with pytest.raises(ValueError,match='split'):select_policy(assembly=True,contact_across_boundary=True,capabilities=FACTORY_CAPABILITIES,requested='nvidia_replica')
    with pytest.raises(ValueError,match='wrench'):select_policy(assembly=False,contact_across_boundary=True,capabilities=FACTORY_CAPABILITIES)

def test_replica_overflow_does_not_half_commit_ownership():
    router=TransactionalReplicaRouter({0:{'workers':(0,1),'plane':(0,0,1,0)}},[0,0],.1)
    records=np.zeros((2,16),np.float32);records[:,0]=[0,1];records[:,3]=.2;records[:,9]=1
    inputs=[np.full((1,16),17,np.float32) for _ in range(2)]
    with pytest.raises(RuntimeError,match='overflow'):router.route([records,np.empty((0,16))],inputs)
    assert list(router.native.owners)==[0,0] and router.native.transitions==0
    assert all(np.all(a==17) for a in inputs)

def test_replica_router_commits_complete_batch():
    router=TransactionalReplicaRouter({0:{'workers':(0,1),'plane':(0,0,1,0)}},[0],.1)
    records=np.zeros((1,16),np.float32);records[0,3]=.2;records[0,9]=1
    inputs=[np.zeros((2,16),np.float32) for _ in range(2)]
    counts=router.route([records,np.empty((0,16))],inputs)
    assert counts==[1,1] and router.native.owners[0]==1 and router.native.transitions==1

def test_invalid_identity_never_enters_native_router():
    router=TransactionalReplicaRouter({},[0],.1)
    records=np.zeros((1,16),np.float32);records[0,0]=.5
    with pytest.raises(ValueError,match='identifiers'):router.route([records],[])

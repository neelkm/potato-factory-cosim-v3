import numpy as np
from physics_debug import contacts_at,unique_contacts,rotation,visible_edges

def test_contacts_use_exact_step_not_previous_payload():
    rows=np.zeros((3,10));rows[:,0]=[10,20,30]
    arrays={'contacts':rows,'contact_offsets':np.array([0,0,2,3])}
    assert len(contacts_at(arrays,0))==0
    assert contacts_at(arrays,1)[:,0].tolist()==[10,20]
    assert contacts_at(arrays,2)[:,0].tolist()==[30]

def test_sensor_pair_dedup_preserves_other_contacts():
    rows=np.zeros((3,10));rows[:,8:]=[[0,0],[1,1],[0,2]]
    result=unique_contacts(rows,['/World/Pallet','/World/Forks'],['/World/Forks','/World/Pallet','/World/Box_0'])
    assert result[:,8:].tolist()==[[1,1],[0,2]]

def test_body_local_com_rotation():
    q=np.array([0,0,np.sin(np.pi/4),np.cos(np.pi/4)])
    np.testing.assert_allclose(rotation(q)@np.array([1,0,0]),[0,1,0],atol=1e-15)

def test_wireframe_suppresses_triangulation_diagonal():
    v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],float)
    assert set(visible_edges(v,np.array([[0,1,2],[0,2,3]])))=={(0,1),(1,2),(2,3),(0,3)}

"""Engine-neutral rigid-body state in metres, kilograms, seconds and radians.

Pose is body-origin world position + xyzw orientation. Twist is world COM
linear velocity followed by world angular velocity. Inertia is a full tensor
about COM in body axes. This module has no native engine dependencies.
"""
from dataclasses import dataclass,asdict
import hashlib,json
import numpy as np
VERSION=2
@dataclass
class RigidState:
    path:str
    pose:list
    velocity:list
    mass:float
    com:list
    inertia:list
    def validate(self):
        q=np.asarray(self.pose,float);v=np.asarray(self.velocity,float);c=np.asarray(self.com,float);i=np.asarray(self.inertia,float)
        if q.shape!=(7,) or v.shape!=(6,) or c.shape!=(3,) or i.shape!=(3,3):raise ValueError('Invalid state dimensions: '+self.path)
        if not np.isfinite(np.r_[q,v,c,i.ravel(),self.mass]).all():raise ValueError('Non-finite transfer state: '+self.path)
        if abs(np.linalg.norm(q[3:])-1)>2e-4:raise ValueError('Non-unit quaternion: '+self.path)
        if self.mass<=0 or np.linalg.eigvalsh(i).min()<=0:raise ValueError('Invalid mass/inertia: '+self.path)
        if not np.allclose(i,i.T,atol=1e-7):raise ValueError('Non-symmetric inertia: '+self.path)
        return self
@dataclass
class Transfer:
    tick:int
    source:str
    destination:str
    states:list
    membership:dict
    joint_states:dict
    version:int=VERSION
    def validate(self):
        if self.version!=VERSION or not isinstance(self.tick,int) or self.tick<0 or self.source==self.destination or not self.states:raise ValueError('Invalid transfer header')
        paths=[]
        for row in self.states:RigidState(**row).validate();paths.append(row['path'])
        if len(paths)!=len(set(paths)):raise ValueError('Duplicate transfer body')
        for carton,members in self.membership.items():
            if carton not in paths or not set(members).issubset(paths):raise ValueError('Incomplete carton transfer')
            if len(members)!=len(set(members)) or carton in members:raise ValueError('Invalid assembly membership')
        for joint,description in self.joint_states.items():
            if description.get('parent') not in paths or description.get('child') not in paths:raise ValueError('Joint crosses transfer boundary: '+joint)
            for key in ['parent_frame','child_frame']:
                frame=np.asarray(description.get(key),float)
                if frame.shape!=(7,) or not np.isfinite(frame).all() or abs(np.linalg.norm(frame[3:])-1)>2e-4:raise ValueError('Invalid joint frame: '+joint)
        return self
    @property
    def digest(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,allow_nan=False).encode()).hexdigest()
def continuity(before,after):
    # Reject malformed receiver replies explicitly: max(0, NaN) can otherwise
    # hide a non-finite residual and incorrectly acknowledge a broken import.
    for row in before+after:RigidState(**row).validate()
    a={r['path']:r for r in before};b={r['path']:r for r in after}
    if len(a)!=len(before) or len(b)!=len(after):raise ValueError('Duplicate continuity body')
    if a.keys()!=b.keys():raise ValueError('Transfer membership changed')
    result=dict(position=0.,orientation=0.,velocity=0.,mass=0.,com=0.,inertia=0.)
    result.update(orientation_rad=0.,linear_velocity_m_s=0.,angular_velocity_rad_s=0.,relative_inertia=0.)
    for p,x in a.items():
        y=b[p];q=np.asarray(x['pose']);r=np.asarray(y['pose'])
        result['position']=max(result['position'],float(np.linalg.norm(q[:3]-r[:3])))
        result['orientation']=max(result['orientation'],float(min(np.linalg.norm(q[3:]-r[3:]),np.linalg.norm(q[3:]+r[3:]))))
        qa=q[3:]/np.linalg.norm(q[3:]);qb=r[3:]/np.linalg.norm(r[3:]);chord=min(np.linalg.norm(qa-qb),np.linalg.norm(qa+qb))
        result['orientation_rad']=max(result['orientation_rad'],float(4*np.arcsin(min(1.,chord/2))))
        dv=np.abs(np.asarray(x['velocity'])-y['velocity'])
        result['linear_velocity_m_s']=max(result['linear_velocity_m_s'],float(np.max(dv[:3])))
        result['angular_velocity_rad_s']=max(result['angular_velocity_rad_s'],float(np.max(dv[3:])))
        result['relative_inertia']=max(result['relative_inertia'],float(np.linalg.norm(np.asarray(x['inertia'])-y['inertia'])/max(np.linalg.norm(x['inertia']),1e-12)))
        for key in ['velocity','mass','com','inertia']:result[key]=max(result[key],float(np.max(np.abs(np.asarray(x[key])-y[key]))))
    if result['position']>2e-5 or result['orientation']>2e-5 or result['velocity']>2e-4 or result['mass']>2e-5 or result['com']>2e-5 or result['inertia']>2e-5 or result['relative_inertia']>2e-4:raise RuntimeError('Transfer continuity failed: '+str(result))
    return result

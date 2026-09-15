"""FR3 forward/inverse kinematics from the downloaded USD joint frames.

This plans joint references. Only the Newton force controller moves the arm.
"""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]
HOME=np.array([0,-.45,0,-1.95,0,1.55,.785])
LIMITS=np.array([87,87,87,87,12,12,12],float)
def transform(pose):
    t=np.eye(4);t[:3,:3]=R.from_quat(pose[3:]).as_matrix();t[:3,3]=pose[:3];return t
class FrankaKinematics:
    def __init__(self,base=(0,0,0)):
        self.joints=json.loads((ROOT/'output/franka_kinematics.json').read_text())['joints']
        self.frames=[(transform(j['frames'][0]),np.linalg.inv(transform(j['frames'][1]))) for j in self.joints]
        self.axes=np.array([np.eye(3)['XYZ'.index(j['axis'])] for j in self.joints])
        self.bounds=np.array([j['limits'] for j in self.joints]);self.base=np.array(base,float)
    def chain(self,q):
        t=np.eye(4);t[:3,3]=self.base;links=[t.copy()];origins=[];axes=[]
        for i,(parent,child_inv) in enumerate(self.frames):
            anchor=t@parent;origins.append(anchor[:3,3]);axes.append(anchor[:3,:3]@self.axes[i])
            rotation=np.eye(4);rotation[:3,:3]=R.from_rotvec(self.axes[i]*q[i]).as_matrix()
            t=anchor@rotation@child_inv;links.append(t.copy())
        return links,np.asarray(origins),np.asarray(axes)
    def tip(self,q):
        links,_,_=self.chain(q);t=links[-1].copy();t[:3,3]+=t[:3,:3]@np.array([0,0,.227]);return t
    def solve(self,position,seed=HOME,orientation=None):
        target=R.from_euler('x',np.pi) if orientation is None else R.from_quat(orientation)
        def residual(q):
            t=self.tip(q);rot=target*R.from_matrix(t[:3,:3]).inv()
            return np.r_[(t[:3,3]-position),rot.as_rotvec()*.25,(q-seed)*.0002]
        seed=np.asarray(seed,float)
        starts=[seed];heading=np.arctan2(position[1]-self.base[1],position[0]-self.base[0])
        for shoulder in [-.5,.3,.9]:
            s=HOME.copy();s[0]=heading;s[1]=shoulder;s[6]=heading;starts.append(s)
        fits=[]
        for start in starts:
            fit=least_squares(residual,np.clip(start,self.bounds[:,0]+.01,self.bounds[:,1]-.01),bounds=(self.bounds[:,0]+.005,self.bounds[:,1]-.005),max_nfev=180,ftol=1e-10,xtol=1e-10,gtol=1e-10)
            fits.append(fit)
            if np.linalg.norm(residual(fit.x)[:6])<.001:break
        fit=min(fits,key=lambda f:np.linalg.norm(residual(f.x)[:6]))
        t=self.tip(fit.x);error=float(np.linalg.norm(t[:3,3]-position));angle=float(np.linalg.norm((target*R.from_matrix(t[:3,:3]).inv()).as_rotvec()))
        if error>.004 or angle>.025:raise ValueError(f'FR3 target outside usable reach: {position}, error {error:.4f}m/{angle:.4f}rad')
        return fit.x
    def gravity(self,q,masses,coms,extra_mass=0.):
        links,origins,axes=self.chain(q);torque=np.zeros(7)
        for body in range(1,8):
            point=links[body][:3,3]+links[body][:3,:3]@coms[body]
            for j in range(body):torque[j]-=np.dot(axes[j],np.cross(point-origins[j],[0,0,-9.81*masses[body]]))
        tip=self.tip(q)[:3,3]
        for j in range(7):torque[j]-=np.dot(axes[j],np.cross(tip-origins[j],[0,0,-9.81*(.35+extra_mass)]))
        return torque
if __name__=='__main__':
    k=FrankaKinematics();print('HOME_TIP',k.tip(HOME)[:3,3]);q=k.solve(np.array([.50,0,.25]));print('IK',q,'TIP',k.tip(q)[:3,3])

"""Measured pallet docking with a physical side-shifting fork carriage."""
import math
import numpy as np
from scipy.spatial.transform import Rotation

def smooth(u):
    u=float(np.clip(u,0,1));return u*u*u*(10+u*(-15+6*u))

def mix(a,b,u):return np.asarray(a)+(np.asarray(b)-a)*smooth(u)

class ForkliftMotion:
    def __init__(self,pallet_pose):
        self.pallet=np.asarray(pallet_pose,float)
        angles=Rotation.from_quat(self.pallet[3:]).as_euler('xyz')
        self.side_shift=float(self.pallet[0]-8.17)
        self.dock_y=float(self.pallet[1]-2.09)
        if abs(self.side_shift)>.15:raise RuntimeError('Pallet lies beyond the fork carriage side-shift range')
        if max(abs(angles[:2]))>.01 or abs(angles[2])>.004:raise RuntimeError('Pallet requires reorientation before fork insertion')
        if abs(self.pallet[2]-.62)>.01:raise RuntimeError('Pallet is outside the qualified loading-table height')
    def targets(self,e):
        p=np.array((8.17,-7.5,0.));lift=-.03;yaw=0.
        if e<3:lift=-.03+.61*smooth(e/3)
        elif e<12:p=mix(p,(8.17,self.dock_y,0),(e-3)/9);lift=.58
        elif e<15:p=np.array((8.17,self.dock_y,0));lift=.58+.20*smooth((e-12)/3)
        elif e<23:p=mix((8.17,self.dock_y,0),(8.17,-4.4,0),(e-15)/8);lift=.78
        elif e<44:
            yaw=math.pi*smooth((e-23)/21);p=np.array((10.585-2.415*math.cos(yaw),-4.4-2.415*math.sin(yaw),0));lift=.78
        elif e<48:p=np.array((13.,-4.4,0));yaw=math.pi;lift=.78-.81*smooth((e-44)/4)
        else:p=mix((13,-4.4,0),(13,-2.0,0),(e-48)/6);yaw=math.pi;lift=-.03
        shift=self.side_shift*smooth(e/3)
        carriage=p+np.array((math.cos(yaw)*shift,math.sin(yaw)*shift,lift))
        return p,carriage,yaw
    def describe(self):return dict(measured_pallet_pose=self.pallet.tolist(),side_shift_m=self.side_shift,dock_y_m=self.dock_y)

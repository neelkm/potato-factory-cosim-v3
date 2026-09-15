import ctypes as C
import numpy as np
from config import ROOT
from ovphysx._bindings import ovphysx_string_t,ovphysx_result_t
class Mechanics:
    def __init__(self,px):
        self.px=px;self.dll=C.CDLL(str(ROOT/'tools/mechanics_bridge.dll'));self.cache={};self.last_quaternion={}
        for name,args,ret in [('target',[C.c_void_p,C.c_void_p],None),('push',[C.c_void_p,C.c_void_p],None),('tune',[C.c_void_p],None),('grip',[C.c_void_p,C.c_void_p,C.c_void_p,C.c_int],None),('grip_force',[C.c_void_p],C.c_float)]:
            f=getattr(self.dll,name);f.argtypes=args;f.restype=ret
        self.fn=px._lib.ovphysx_get_physx_ptr;self.fn.argtypes=[C.c_uint64,ovphysx_string_t,C.c_int,C.POINTER(C.c_void_p)];self.fn.restype=ovphysx_result_t
        self.dll.fold.argtypes=[C.c_void_p,C.c_int,C.c_float];self.dll.fold.restype=None
    def ptr(self,path,kind=5):
        key=(path,kind)
        if key not in self.cache:
            ptr=C.c_void_p();r=self.fn(self.px._omni_physx_sdk_handle.value,ovphysx_string_t(path),kind,C.byref(ptr))
            if r.status or not ptr.value:raise RuntimeError(f'Missing native PhysX object {path} type {kind}: {r.status}')
            self.cache[key]=ptr
        return self.cache[key]
    def target(self,path,pos,quat=(0,0,0,1)):
        q=np.asarray(quat,np.float32)
        if path in self.last_quaternion and np.dot(q,self.last_quaternion[path])<0:q=-q
        self.last_quaternion[path]=q.copy()
        a=np.array([*pos,*q],np.float32);self.dll.target(self.ptr(path),a.ctypes.data)
    def tune(self,path):self.dll.tune(self.ptr(path))
    def push(self,path,force):
        a=np.asarray(force,np.float32);self.dll.push(self.ptr(path),a.ctypes.data)
    def grip(self,joint,tool,box,active):self.dll.grip(self.ptr(joint,6),self.ptr(tool),self.ptr(box),int(active))
    def force(self,joint):return self.dll.grip_force(self.ptr(joint,6))
    def fold(self,joint,axis,angle):self.dll.fold(self.ptr(joint,6),0 if axis=='X' else 1,float(angle))

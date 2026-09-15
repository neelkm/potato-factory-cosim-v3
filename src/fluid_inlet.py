"""A closed-loop inlet/drain boundary on the actual PhysX GPU particle buffer.

Uses ovphysx's public native-pointer interop and PxParticleBuffer methods.
Only recycled particles receive prescribed nozzle positions/velocities;
all particles between nozzle and drain are integrated by GPU PhysX PBD.
"""
import ctypes as C
from pathlib import Path
import numpy as np
from ovphysx._bindings import ovphysx_string_t,ovphysx_result_t

ROOT=Path(__file__).resolve().parents[1]
class FluidInlet:
    def __init__(self,px,path='/World/Water'):
        self.bridge=C.CDLL(str(ROOT/'tools/fluid_bridge.dll'))
        for name in ['particle_positions','particle_velocities']:
            f=getattr(self.bridge,name);f.argtypes=[C.c_void_p];f.restype=C.c_void_p
        self.bridge.particle_count.argtypes=[C.c_void_p];self.bridge.particle_count.restype=C.c_uint
        self.bridge.particles_changed.argtypes=[C.c_void_p];self.bridge.particles_changed.restype=None
        fn=px._lib.ovphysx_get_physx_ptr;fn.argtypes=[C.c_uint64,ovphysx_string_t,C.c_int,C.POINTER(C.c_void_p)];fn.restype=ovphysx_result_t
        ptr=C.c_void_p();result=fn(px._omni_physx_sdk_handle.value,ovphysx_string_t(path),12,C.byref(ptr))
        if result.status!=0 or not ptr.value:raise RuntimeError('PhysX particle buffer was not found')
        self.ptr=ptr;self.n=self.bridge.particle_count(ptr)
        if not 0<self.n<100000:raise RuntimeError('Unexpected particle buffer size; check SDK ABI')
        self.paddr=self.bridge.particle_positions(ptr);self.vaddr=self.bridge.particle_velocities(ptr)
        self.cuda=C.WinDLL('nvcuda.dll')
        for name,args in [('cuInit',[C.c_uint]),('cuPointerGetAttribute',[C.c_void_p,C.c_int,C.c_uint64]),('cuCtxPushCurrent_v2',[C.c_void_p]),('cuCtxPopCurrent_v2',[C.POINTER(C.c_void_p)]),('cuMemcpyDtoH_v2',[C.c_void_p,C.c_uint64,C.c_size_t]),('cuMemcpyHtoD_v2',[C.c_uint64,C.c_void_p,C.c_size_t]),('cuCtxSynchronize',[])]:
            f=getattr(self.cuda,name);f.argtypes=args;f.restype=C.c_int
        self.check(self.cuda.cuInit(0));self.ctx=C.c_void_p();self.check(self.cuda.cuPointerGetAttribute(C.byref(self.ctx),1,self.paddr))
        self.positions=np.empty((self.n,4),np.float32);self.velocities=np.empty_like(self.positions)
        self.age=np.arange(self.n)%60/60*1.0;self.rng=np.random.default_rng(181);self.recycled=0;self.budget=0.;self.emitted=0
        self.read()
    def check(self,status):
        if status:raise RuntimeError(f'CUDA driver operation failed: {status}')
    def enter(self):self.check(self.cuda.cuCtxPushCurrent_v2(self.ctx))
    def leave(self):
        ctx=C.c_void_p();self.check(self.cuda.cuCtxPopCurrent_v2(C.byref(ctx)))
    def read(self):
        self.enter()
        try:
            self.check(self.cuda.cuMemcpyDtoH_v2(self.positions.ctypes.data,self.paddr,self.positions.nbytes))
            self.check(self.cuda.cuMemcpyDtoH_v2(self.velocities.ctypes.data,self.vaddr,self.velocities.nbytes))
        finally:self.leave()
        return self.positions
    def write(self):
        self.enter()
        try:
            self.check(self.cuda.cuMemcpyHtoD_v2(self.paddr,self.positions.ctypes.data,self.positions.nbytes))
            self.check(self.cuda.cuMemcpyHtoD_v2(self.vaddr,self.velocities.ctypes.data,self.velocities.nbytes))
            self.check(self.cuda.cuCtxSynchronize())
        finally:self.leave()
        self.bridge.particles_changed(self.ptr)
    def update(self,dt):
        self.read();self.age+=dt
        p=self.positions
        # The pan is the sink; occasional long-lived particles are drained too.
        recycle=(p[:,2]<1.10)|((self.age>1.2)&(p[:,2]<1.70))|(abs(p[:,1])>1.18)|(abs(p[:,0])>1.88)
        self.budget+=dt*(80772/90)*2
        available=np.flatnonzero(recycle);number=min(int(self.budget),len(available))
        ids=available[np.argsort(self.age[available])[-number:]] if number else np.empty(0,np.int64)
        if len(ids):
            nozzle=(np.arange(len(ids))+self.emitted)%9;self.emitted+=len(ids);self.budget-=len(ids)
            p[ids,0]=np.array([-1.5,0,1.5])[nozzle//3]+self.rng.uniform(-.020,.020,len(ids))
            p[ids,1]=np.array([-.4,0,.4])[nozzle%3]+self.rng.uniform(-.020,.020,len(ids))
            p[ids,2]=self.rng.uniform(2.385,2.405,len(ids))
            self.velocities[ids,:3]=np.stack((self.rng.uniform(-.2,.2,len(ids)),self.rng.uniform(-.55,.55,len(ids)),np.full(len(ids),-2.8)),axis=1)
            self.age[ids]=0;self.recycled+=len(ids);self.write()

if __name__=='__main__':
    import ovstage
    from ovphysx import PhysX
    from ovphysx.types import SimObjectType,ObjectScope
    px=PhysX();st=ovstage.Stage('native-fluid-probe')
    ovstage.population.open_usd(st,str(ROOT/'output/smoke.usda'),ordinal=1,domains=ovstage.PopulationDomain.PHYSICS);st.advance_write_floor(1).wait();px.attach_ovstage(st,read_ordinal=1)
    for i in range(60):px.step_sync(1/120)
    inlet=FluidInlet(px);print('GPU_BUFFER',inlet.n,inlet.positions[:2],flush=True)
    inlet.positions[:,2]+=2;inlet.write();px.step_sync(1/120)
    with px.read(SimObjectType.PARTICLE_SET,['points'],ObjectScope.ALL) as r:
        z=r.groups[0].tensors[0][:,2];print('RECYCLED_Z',z.min(),z.max(),flush=True);assert z.min()>1.5
    px.detach_ovstage();px.release();st.destroy()

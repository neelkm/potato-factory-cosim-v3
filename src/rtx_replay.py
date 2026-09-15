"""Shared RTX viewport for the desktop app and movie renderer."""
from pathlib import Path
import json,math,sys,time
import ovrtx
import ovstage
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
VIEWS={
 'Overall':((15.5,-24.5,14),(1,-2.0,1.0)),
 'Truck unloading':((-3.2,-4.2,7.8),(-5.65,0,2.25)),
 'Water wash':((1.4,-3.4,3.7),(0,0,1.8)),
 'Quality & rejection':((5.8,-6.2,4.5),(4.15,-.65,1.0)),
 'Carton filling':((8.05,.6,3.3),(7.95,0,1.25)),
 'Carton closing':((8.1,.7,2.9),(7.95,0,1.32)),
 'Robot palletizing':((10.5,-3.8,3.15),(8.15,-.6,1.1)),
 'Forklift dispatch':((16,-12,7),(10.6,-4.5,.8)),
 'Factory hero':((20,-29,14),(2,-2,.65)),
}

def look_at(eye,target):
    eye=np.asarray(eye,float);forward=np.asarray(target,float)-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    m=np.eye(4,dtype=np.float64);m[0,:3]=right;m[1,:3]=up;m[2,:3]=-forward;m[3,:3]=eye
    return m[None,:,:]

class Replay:
    def __init__(self,width=1280,height=720,spp=32,source='factory_replay.usdc',tag='viewer',cache='cache',reset_history=False):
        self.meta=json.loads((OUT/cache/'simulation.json').read_text())
        self.ordinal=1
        self.last_eye=None
        self.last_time=None
        self.spp=spp
        self.reset_history=reset_history
        # Composition keeps the source scene and simulation replay reusable.
        layer=OUT/f'{tag}_settings.usda'
        layer.write_text(f'''#usda 1.0
(subLayers = [@{source}@])
over "Render" {{
 over "Camera" {{
 int2 resolution = ({width},{height})
 uint omni:rtx:pt:samplesPerPixel = {spp}
 int omni:rtx:pt:samplesPerIteration = {spp}
 bool omni:rtx:pt:denoising:enabled = true
 bool omni:rtx:post:motionblur:enabled = false
 }}
}}
''')
        self.r=ovrtx.Renderer(ovrtx.RendererConfig(log_level='error'))
        self.s=ovstage.Stage('field-flow-'+tag);self.r.attach_ovstage(self.s)
        ovstage.population.open_usd(self.s,str(layer),ordinal=1,time_code=0)
        self.s.advance_write_floor(1).wait()
        self.d=ovstage.PathDictionary(self.s);pl=self.d.create_path_list_from_strings(['/World/Camera']);self.q=self.s.query_from_path_list(pl);self.d.destroy_path_list(pl)
        # Instantiate the imported render camera before applying the first
        # interactive override; otherwise the first returned image uses the
        # authored camera even though subsequent images use the chosen view.
        primed=self.r.step(render_products={'/Render/Camera'},delta_time=1/24,ordinal=1)
        del primed
    def render(self,t,eye,target):
        started=time.perf_counter()
        trace='--smoke-ui' in sys.argv
        if trace:print('RTX_FRAME begin',round(float(t),3),flush=True)
        self.ordinal+=1
        # Sampling exact cache times prevents interpolation across the drain /
        # nozzle reset of an individual fluid particle.
        ovstage.population.update_from_usd_time(self.s,self.ordinal,round(float(t)*30)/30)
        if trace:print('RTX_FRAME time set',flush=True)
        transforms=look_at(eye,target)
        tensor=ovstage.make_dltensor(transforms,dtype=ovstage.DLDataType(ovstage.DLDataTypeCode.kDLFloat,64,16),shape=[1],ndim=1)
        self.s.write_attribute(self.q,'omni:xform',self.ordinal,tensor,is_array=False,semantic=ovstage.AttributeSemantic.MATRIX).wait()
        self.s.advance_write_floor(self.ordinal).wait();self.r.update_from_stage(self.ordinal)
        # The native path tracer invalidates accumulation when scene/camera
        # changes are committed. Repeated full sensor-history resets retain
        # large GPU allocations in this SDK build. USD time is independent of
        # the sensor clock, and motion blur is disabled for this replay.
        if self.reset_history:self.r.reset(time=float(t))
        self.last_eye=np.asarray(eye).copy()
        self.last_time=float(t)
        if trace:print('RTX_FRAME stage synced',flush=True)
        synced=time.perf_counter()
        if not self.reset_history:
            # Sensor frames span the previous/current stage snapshots. Advance
            # once with the requested snapshot held fixed, then expose only a
            # frame whose two endpoints both contain that exact snapshot.
            # This also handles arbitrary backward seeks and camera jumps.
            transition=self.r.step(render_products={'/Render/Camera'},delta_time=1/24,ordinal=self.ordinal)
            del transition
        for iteration in range(16):
            products=self.r.step(render_products={'/Render/Camera'},delta_time=1/24,ordinal=self.ordinal)
            frames=[frame for product in products.values() for frame in product.frames]
            if iteration>=2:print('RTX_CONVERGENCE',float(t),iteration+1,[(frame.progression,frame.converged) for frame in frames],flush=True)
            if frames and all(frame.converged for frame in frames):break
        else:raise RuntimeError('RTX path tracing did not reach the requested sample count')
        self.last_render_progress=[(frame.progression,frame.converged) for frame in frames]
        traced=time.perf_counter()
        if trace:print('RTX_FRAME rendered',flush=True)
        image=None
        for p in products.values():
            for f in p.frames:
                key=next(k for k in f.render_vars if k.endswith('LdrColor'))
                v=f.render_vars[key].map(device=ovrtx.Device.CPU);image=np.from_dlpack(v).copy();v.unmap();del v
        if image is None:raise RuntimeError('RTX produced no color frame')
        self.last_timing=dict(stage_seconds=round(synced-started,3),render_seconds=round(traced-synced,3),readback_seconds=round(time.perf_counter()-traced,3),iterations=iteration+1)
        return image
    def close(self):
        self.s.release_query(self.q).wait();self.d.destroy();self.r.detach_ovstage();self.s.destroy();self.r.destroy()

def metrics(meta,t):
    ev=[e for e in meta.get('events',[]) if e['time']<=t]
    history=[h for h in meta.get('history',[]) if h['time']<=t];h=history[-1] if history else {}
    return {'washed':sum(v<=t for v in meta.get('wash_times',{}).values()),'accepted':sum(e['kind']=='accept' for e in ev),'rejected':sum(e['kind']=='reject' for e in ev),'pallet':h.get('pallet',0),'box_count':h.get('box_count',0),'box_target':h.get('box_target',18)}

def station_times(meta):
    """Navigation follows the loaded run, including freshly computed batches."""
    events=meta.get('events',[])
    full=next((e['time'] for e in events if e['kind']=='box_full'),0.)
    reject=next((e['time'] for e in events if e['kind']=='reject'),0.)
    fork=next((e['time'] for e in events if e['kind']=='forklift_start'),0.)
    wash=min(meta.get('wash_times',{}).values(),default=0.)+4
    grip=next((e['time'] for e in events if e['kind']=='vacuum_attached'),full+4)
    moments={'Overall':wash,'Truck unloading':15.5,'Water wash':wash,
             'Quality & rejection':reject-.7,'Carton filling':full-4.8,
             'Carton closing':full+.3,'Robot palletizing':grip,
             'Forklift dispatch':fork+7,'Factory hero':meta['seconds']-3}
    return {view:max(0.,min(meta['seconds'],t)) for view,t in moments.items()}

if __name__=='__main__':
    from PIL import Image
    r=Replay(960,540,8,source='probe_replay.usdc',tag='runtime_probe')
    for i,view in enumerate(['Overall','Truck unloading','Truck unloading','Truck unloading']):
        Image.fromarray(r.render(8+i,*VIEWS[view])).save(OUT/f'runtime_probe_{i}.png');print('FRAME',i,flush=True)
    r.close()

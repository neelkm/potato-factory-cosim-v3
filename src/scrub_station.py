"""Post-wash brush bed parameters and measured native-contact cleaning proxy."""
import math
import numpy as np

START=1.76
END=2.91
RADIUS=.060
PITCH=.205
WIDTH=1.32
MIN_CONTACT_SECONDS=.6
MIN_SLIP_METRES=.025

def brush_specs():
    return [dict(name=f'ScrubBrush_{i:02d}',pos=[1.84+i*PITCH,0,1.535+RADIUS],
                 radius=RADIUS,width=2*(.80-(1.84+i*PITCH-1.05)*.748/2.25)-.075,
                 speed_ratio=[-.40,-.75,-.55][i%3]) for i in range(6)]

def scrub_complete(seconds,slip):
    return seconds>=MIN_CONTACT_SECONDS and slip>=MIN_SLIP_METRES

class ScrubContacts:
    """No cleaning based on location alone: dose requires native brush contacts.

    Slip integrates tangential relative speed at actual contact points. This
    is a transparent cleaning proxy, not a calibrated soil detachment model.
    """
    def __init__(self,px,potato_paths,specs):
        from ovphysx.types import TensorType
        self.px=px;self.specs={('/World/'+s['name']):s for s in specs}
        self.binding=px.create_contact_binding(sensor_patterns=list(self.specs),max_contact_data_count=8192)
        self.sensors=self.binding.sensor_paths;self.paths=list(potato_paths)
        self.pose=px.create_tensor_binding(prim_paths=self.paths,tensor_type=TensorType.RIGID_BODY_POSE,raise_if_empty=True)
        self.velocity=px.create_tensor_binding(prim_paths=self.paths,tensor_type=TensorType.RIGID_BODY_VELOCITY,raise_if_empty=True)
        self.com=px.create_tensor_binding(prim_paths=self.paths,tensor_type=TensorType.RIGID_BODY_COM_POSE,raise_if_empty=True)
        self.brush_velocity=px.create_tensor_binding(prim_paths=self.sensors,tensor_type=TensorType.RIGID_BODY_VELOCITY,raise_if_empty=True)
        self.index={p:i for i,p in enumerate(self.pose.prim_paths)}
        assert self.pose.prim_paths==self.velocity.prim_paths==self.com.prim_paths
        self.p=np.zeros(self.pose.shape,np.float32);self.v=np.zeros(self.velocity.shape,np.float32)
        self.c=np.zeros(self.com.shape,np.float32);self.com.read(self.c)
        self.bv=np.zeros(self.brush_velocity.shape,np.float32);self.bi={p:i for i,p in enumerate(self.brush_velocity.prim_paths)}
        n=self.binding.max_contact_data_count
        self.f=np.zeros((n,1),np.float32);self.pos=np.zeros((n,3),np.float32);self.normal=np.zeros_like(self.pos);self.sep=np.zeros_like(self.f)
        self.count=np.zeros(len(self.sensors),np.uint32);self.offset=np.zeros_like(self.count);self.ids=np.zeros(n,np.uint64)
        self.names={};self.seconds={};self.slip={};self.times={};self.history=[];self.contact_rows=0;self.peak_force=0.;self.peak_penetration=0.
    def sample(self,dt,t):
        self.binding.read_raw_contact_data(self.f,self.pos,self.normal,self.sep,self.count,self.offset,self.ids)
        if not self.count.any():return []
        self.pose.read(self.p);self.velocity.read(self.v);self.brush_velocity.read(self.bv)
        speeds={};new=[]
        for s,(n,offset) in enumerate(zip(self.count,self.offset)):
            brush=self.specs[self.sensors[s]];bv=self.bv[self.bi[self.sensors[s]]]
            for i in range(int(offset),int(offset+n)):
                identity=int(self.ids[i])
                if identity not in self.names:self.names[identity]=self.binding.get_other_actor_paths_from_ids(np.asarray([identity],np.uint64))[0]
                path=self.names[identity]
                if path not in self.index or abs(self.f[i,0])<1e-5:continue
                j=self.index[path];q=self.p[j,3:];local=self.c[j,:3]
                world_com=self.p[j,:3]+local+2*np.cross(q[:3],np.cross(q[:3],local)+q[3]*local)
                produce_velocity=self.v[j,:3]+np.cross(self.v[j,3:],self.pos[i]-world_com)
                surface_velocity=bv[:3]+np.cross(bv[3:],self.pos[i]-brush['pos'])
                relative=produce_velocity-surface_velocity;normal=self.normal[i]
                slip=float(np.linalg.norm(relative-normal*np.dot(relative,normal)))
                speeds.setdefault(path,[]).append(slip);self.contact_rows+=1
                self.peak_force=max(self.peak_force,float(abs(self.f[i,0])));self.peak_penetration=max(self.peak_penetration,float(-self.sep[i,0]))
        for path,values in speeds.items():
            self.seconds[path]=self.seconds.get(path,0)+dt
            self.slip[path]=self.slip.get(path,0)+float(np.mean(values))*dt
            if path not in self.times and scrub_complete(self.seconds[path],self.slip[path]):self.times[path]=t;new.append(path)
        return new
    def report(self):
        return dict(model='Native loaded brush-contact time and tangential slip; empirical cleaning proxy, not soil-grain simulation',
                    contact_seconds=self.seconds,slip_metres=self.slip,scrub_times=self.times,contact_rows=self.contact_rows,
                    peak_normal_force_N=self.peak_force,max_penetration_m=self.peak_penetration,
                    thresholds=dict(seconds=MIN_CONTACT_SECONDS,slip_metres=MIN_SLIP_METRES))
    def close(self):
        for b in [self.binding,self.pose,self.velocity,self.com,self.brush_velocity]:b.destroy()

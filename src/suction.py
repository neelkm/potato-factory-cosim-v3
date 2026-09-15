"""Contact-checked, force-limited four-cup vacuum attachment in Newton.

Closed lids are fixed to the carton after sealing. Cup wrenches act on that
rigid assembly at the measured surface points, with equal reaction on the tool.
"""
import numpy as np
import warp as wp
from scipy.spatial.transform import Rotation
@wp.kernel
def vacuum_forces(q:wp.array[wp.transform],qd:wp.array[wp.spatial_vector],com:wp.array[wp.vec3],tool:int,box:wp.array[int],active:wp.array[int],tool_points:wp.array[wp.vec3],box_points:wp.array[wp.vec3],max_force:float,peak:wp.array[float],deflection:wp.array[float],body_f:wp.array[wp.spatial_vector]):
    i=wp.tid()
    if active[0]==0:return
    b=box[0];a=wp.transform_point(q[tool],tool_points[i]);p=wp.transform_point(q[b],box_points[i]);ra=a-wp.transform_point(q[tool],com[tool]);rb=p-wp.transform_point(q[b],com[b])
    va=wp.spatial_top(qd[tool])+wp.cross(wp.spatial_bottom(qd[tool]),ra);vb=wp.spatial_top(qd[b])+wp.cross(wp.spatial_bottom(qd[b]),rb)
    error=a-p;distance=wp.length(error)
    # A bellows seal fails if it cannot keep the load within its travel.
    if distance>.030:wp.atomic_exch(active,0,0);return
    force=1500.*error+20.*(va-vb);length=wp.length(force)
    if length>max_force:force*=max_force/length
    peak[i]=wp.max(peak[i],wp.length(force));deflection[i]=wp.max(deflection[i],distance)
    wp.atomic_add(body_f,b,wp.spatial_vector(force,wp.cross(rb,force)))
    wp.atomic_sub(body_f,tool,wp.spatial_vector(force,wp.cross(ra,force)))
def ray_box(origin,direction,pose,center,half,max_distance):
    rotation=Rotation.from_quat(pose[3:]);o=rotation.inv().apply(origin-pose[:3])-center;d=rotation.inv().apply(direction)
    enter=0.;leave=max_distance;axis=-1;sign=0
    for k in range(3):
        if abs(d[k])<1e-10:
            if abs(o[k])>half[k]:return None
        else:
            a=(-half[k]-o[k])/d[k];b=(half[k]-o[k])/d[k];lo=min(a,b);hi=max(a,b)
            if lo>enter:enter=lo;axis=k;sign=-1 if d[k]>0 else 1
            leave=min(leave,hi)
            if enter>leave:return None
    if axis<0:return None
    normal=np.zeros(3);normal[axis]=sign
    return origin+direction*enter,rotation.apply(normal),enter
class VacuumGripper:
    def __init__(self,model):
        self.model=model;self.tool=model.body_label.index('/World/Tool');self.box=wp.zeros(1,dtype=wp.int32);self.active=wp.zeros(1,dtype=wp.int32)
        self.tool_points=wp.zeros(4,dtype=wp.vec3);self.box_points=wp.zeros(4,dtype=wp.vec3);self.peak=wp.zeros(4,dtype=wp.float32);self.deflection=wp.zeros(4,dtype=wp.float32)
        self.max_force=22.;self.contact_log=[]
    def try_seal(self,state,box_path,flap_shapes):
        poses=state.body_q.numpy();tp=poses[self.tool];tr=Rotation.from_quat(tp[3:]);direction=tr.apply([0,0,1]);box_index=self.model.body_label.index(box_path);bp=poses[box_index];br=Rotation.from_quat(bp[3:])
        hits=[]
        for x,y in [(-.06,-.04),(-.06,.04),(.06,-.04),(.06,.04)]:
            tip=tp[:3]+tr.apply([x,y,.12]);origin=tip-direction*.008;nearest=None
            for path,center,size in flap_shapes:
                hit=ray_box(origin,direction,poses[self.model.body_label.index(path)],np.asarray(center),np.asarray(size)*.5,.019)
                if hit and abs(hit[2]-.008)<=.004 and np.dot(hit[1],-direction)>.90 and (nearest is None or hit[2]<nearest[2]):nearest=(*hit,path)
            if nearest is None:return dict(sealed=False,contacts=len(hits))
            hits.append(nearest)
        points=np.asarray([h[0] for h in hits]);self.tool_points.assign(tr.inv().apply(points-tp[:3]).astype(np.float32));self.box_points.assign(br.inv().apply(points-bp[:3]).astype(np.float32));self.box.assign(np.asarray([box_index],np.int32));self.active.assign(np.ones(1,np.int32))
        self.contact_log=[dict(surface=h[3],point=h[0].tolist(),normal=h[1].tolist(),distance=float(h[2])) for h in hits]
        return dict(sealed=True,contacts=self.contact_log,max_force_per_cup=self.max_force)
    def release(self):self.active.zero_()
    def apply(self,state):wp.launch(vacuum_forces,dim=4,inputs=[state.body_q,state.body_qd,self.model.body_com,self.tool,self.box,self.active,self.tool_points,self.box_points,self.max_force,self.peak,self.deflection],outputs=[state.body_f])
    def metrics(self):return dict(active=bool(self.active.numpy()[0]),peak_cup_force=self.peak.numpy().tolist(),peak_cup_deflection=self.deflection.numpy().tolist(),contacts=self.contact_log)

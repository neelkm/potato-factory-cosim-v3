"""GPU PID/gravity control with explicit FR3 motor torque limits.

References are planned joint angles; all arm movement comes from Newton forces.
XPBD does not enforce joint_effort_limit, so the control kernel clamps torque.
"""
import numpy as np
import warp as wp
import newton
from franka_motion import HOME,LIMITS
@wp.kernel
def motor_control(
    body_q:wp.array[wp.transform], body_com:wp.array[wp.vec3],body_mass:wp.array[float],
    joint_xp:wp.array[wp.transform],joint_parent:wp.array[int],joint_q_start:wp.array[int],joint_qd_start:wp.array[int],joint_axis:wp.array[wp.vec3],
    q:wp.array[float],qd:wp.array[float],joints:wp.array[int],links:wp.array[int],tool:int,
    target:wp.array[float],kp:wp.array[float],kd:wp.array[float],ki:wp.array[float],limits:wp.array[float],
    integral:wp.array[float],peak:wp.array[float],payload:wp.array[float],dt:float,forces:wp.array[float]):
    i=wp.tid();j=joints[i];qs=joint_q_start[j];ds=joint_qd_start[j]
    anchor=body_q[joint_parent[j]]*joint_xp[j];origin=wp.transform_get_translation(anchor);axis=wp.transform_vector(anchor,joint_axis[ds])
    grav=float(0.)
    for link in range(i+1,8):
        b=links[link];com=wp.transform_point(body_q[b],body_com[b]);force=wp.vec3(0.,0.,-9.81*body_mass[b]);grav-=wp.dot(axis,wp.cross(com-origin,force))
    com=wp.transform_point(body_q[tool],body_com[tool]);force=wp.vec3(0.,0.,-9.81*body_mass[tool]);grav-=wp.dot(axis,wp.cross(com-origin,force))
    point=wp.transform_point(body_q[tool],wp.vec3(0.,0.,.20));grav-=wp.dot(axis,wp.cross(point-origin,wp.vec3(0.,0.,-9.81*payload[0])))
    error=target[i]-q[qs];acc=wp.clamp(integral[i]+error*dt,-.08,.08)
    raw=kp[i]*error-kd[i]*qd[ds]+ki[i]*acc+grav
    torque=wp.clamp(raw,-limits[i],limits[i])
    if wp.abs(raw)<=limits[i] or raw*error<0.:integral[i]=acc
    forces[ds]=torque;peak[i]=wp.max(peak[i],wp.abs(torque))
class FrankaController:
    def __init__(self,model,target=HOME):
        self.model=model
        self.joints=wp.array([model.joint_label.index(f'/World/Franka/fr3_link{i}/fr3_joint{i+1}') for i in range(7)],dtype=wp.int32)
        self.links=wp.array([model.body_label.index('/World/Franka/fr3_link'+str(i)) for i in range(8)],dtype=wp.int32)
        self.tool=model.body_label.index('/World/Tool')
        self.target=wp.array(np.asarray(target,np.float32),dtype=wp.float32)
        self.kp=wp.array([800.,800.,800.,600.,160.,160.,100.],dtype=wp.float32)
        self.kd=wp.array([12.,12.,10.,8.,.65,.65,.35],dtype=wp.float32)
        self.ki=wp.array([200.,200.,200.,150.,40.,40.,25.],dtype=wp.float32)
        self.limits=wp.array(LIMITS.astype(np.float32),dtype=wp.float32)
        self.integral=wp.zeros(7,dtype=wp.float32);self.peak=wp.zeros(7,dtype=wp.float32);self.payload=wp.zeros(1,dtype=wp.float32)
    def set_target(self,target,payload=0.):
        self.target.assign(np.asarray(target,np.float32));self.payload.assign(np.asarray([payload],np.float32))
    def apply(self,state,control,dt):
        m=self.model;newton.eval_ik(m,state,state.joint_q,state.joint_qd)
        wp.launch(motor_control,dim=7,inputs=[state.body_q,m.body_com,m.body_mass,m.joint_X_p,m.joint_parent,m.joint_q_start,m.joint_qd_start,m.joint_axis,state.joint_q,state.joint_qd,self.joints,self.links,self.tool,self.target,self.kp,self.kd,self.ki,self.limits,self.integral,self.peak,self.payload,dt],outputs=[control.joint_f])

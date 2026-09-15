#include "PxRigidDynamic.h"
#include "extensions/PxD6Joint.h"
#include "PxConstraint.h"
#include <initializer_list>
using namespace physx;
extern "C" {
__declspec(dllexport) void mass_properties(void* p,float* out){
 auto a=static_cast<PxRigidDynamic*>(p);auto c=a->getCMassLocalPose();auto i=a->getMassSpaceInertiaTensor();
 out[0]=a->getMass();out[1]=c.p.x;out[2]=c.p.y;out[3]=c.p.z;
 out[4]=c.q.x;out[5]=c.q.y;out[6]=c.q.z;out[7]=c.q.w;
 out[8]=i.x;out[9]=i.y;out[10]=i.z;
}
__declspec(dllexport) void target(void* p,const float* v){static_cast<PxRigidDynamic*>(p)->setKinematicTarget(PxTransform(PxVec3(v[0],v[1],v[2]),PxQuat(v[3],v[4],v[5],v[6])));}
__declspec(dllexport) void tune(void* p){auto a=static_cast<PxRigidDynamic*>(p);a->setMaxDepenetrationVelocity(.7f);a->setSleepThreshold(0);a->setStabilizationThreshold(0);}
__declspec(dllexport) void push(void* p,const float* f){static_cast<PxRigidDynamic*>(p)->addForce(PxVec3(f[0],f[1],f[2]),PxForceMode::eFORCE,true);}
__declspec(dllexport) void grip(void* p,void* a,void* b,int active){
 auto j=static_cast<PxD6Joint*>(p);
 if(active){auto aa=static_cast<PxRigidDynamic*>(a);auto bb=static_cast<PxRigidDynamic*>(b);auto world=aa->getGlobalPose();
 j->setLocalPose(PxJointActorIndex::eACTOR0,PxTransform(PxIdentity));
 j->setLocalPose(PxJointActorIndex::eACTOR1,bb->getGlobalPose().getInverse()*world);j->setBreakForce(1600,500);bb->wakeUp();}
 // Bellows compliance cushions loose produce. Drives act through PhysX;
 // their finite force limits cannot move a carton through an obstruction.
 for(int i=0;i<6;i++)j->setMotion(static_cast<PxD6Axis::Enum>(i),PxD6Motion::eFREE);
 j->setConstraintFlag(PxConstraintFlag::eDRIVE_LIMITS_ARE_FORCES,true);
 auto linear=active?PxD6JointDrive(20000,1400,800,false):PxD6JointDrive();linear.flags|=PxD6JointDriveFlag::eOUTPUT_FORCE;
 for(auto axis:{PxD6Drive::eX,PxD6Drive::eY,PxD6Drive::eZ})j->setDrive(axis,linear);
 j->setAngularDriveConfig(PxD6AngularDriveConfig::eSLERP);
 auto angular=active?PxD6JointDrive(300,60,200,false):PxD6JointDrive();angular.flags|=PxD6JointDriveFlag::eOUTPUT_FORCE;j->setDrive(PxD6Drive::eSLERP,angular);
 j->setDrivePosition(PxTransform(PxIdentity));
}
__declspec(dllexport) float grip_force(void* p){PxVec3 f,t;static_cast<PxD6Joint*>(p)->getConstraint()->getForce(f,t);return f.magnitude();}
__declspec(dllexport) void fold(void* p,int axis,float angle){
 auto j=static_cast<PxD6Joint*>(p);for(int i=0;i<6;i++)j->setMotion(static_cast<PxD6Axis::Enum>(i),i<3?PxD6Motion::eLOCKED:PxD6Motion::eFREE);
 j->setAngularDriveConfig(PxD6AngularDriveConfig::eSLERP);j->setDrive(PxD6Drive::eSLERP,PxD6JointDrive(100,4,20,false));
 j->setDrivePosition(PxTransform(PxQuat(angle,axis==0?PxVec3(1,0,0):PxVec3(0,1,0))));
}
}

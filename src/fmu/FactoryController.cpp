// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
// Modified for FIELD / FLOW: quality decisions, valve response and packing interlocks.
// FIELD / FLOW controller. FMI wrapper adapted from NVIDIA's Apache-2.0 demo.
#include "fmi2_minimal.h"
#include <new>
#include <cmath>
#include <algorithm>
struct Controller {
 double v[64]={}; bool done[512]={}; double dwell=0,jet=0; int current=-1;
 Controller(){v[8]=18;v[50]=.10;v[51]=18;v[24]=1;v[22]=-1;}
};
FMI_EXPORT const char* fmi2GetTypesPlatform(){return "default";}
FMI_EXPORT const char* fmi2GetVersion(){return "2.0";}
FMI_EXPORT fmi2Component fmi2Instantiate(fmi2String,int,fmi2String,fmi2String,const fmi2CallbackFunctions*,fmi2Boolean,fmi2Boolean){return new(std::nothrow) Controller();}
FMI_EXPORT void fmi2FreeInstance(fmi2Component c){delete static_cast<Controller*>(c);}
FMI_EXPORT fmi2Status fmi2SetDebugLogging(fmi2Component,fmi2Boolean,size_t,const fmi2String*){return fmi2OK;}
FMI_EXPORT fmi2Status fmi2SetupExperiment(fmi2Component c,fmi2Boolean,fmi2Real,fmi2Real,fmi2Boolean,fmi2Real){return c?0:3;}
FMI_EXPORT fmi2Status fmi2EnterInitializationMode(fmi2Component c){return c?0:3;}
FMI_EXPORT fmi2Status fmi2ExitInitializationMode(fmi2Component c){return c?0:3;}
FMI_EXPORT fmi2Status fmi2Terminate(fmi2Component c){return c?0:3;}
FMI_EXPORT fmi2Status fmi2Reset(fmi2Component c){if(!c)return 3;*static_cast<Controller*>(c)=Controller();return 0;}
FMI_EXPORT fmi2Status fmi2SetReal(fmi2Component c,const fmi2ValueReference* vr,size_t n,const fmi2Real* values){if(!c)return 3;auto*p=static_cast<Controller*>(c);for(size_t i=0;i<n;i++){if(vr[i]>=64)return 3;p->v[vr[i]]=values[i];}return 0;}
FMI_EXPORT fmi2Status fmi2GetReal(fmi2Component c,const fmi2ValueReference* vr,size_t n,fmi2Real* values){if(!c)return 3;auto*p=static_cast<Controller*>(c);for(size_t i=0;i<n;i++){if(vr[i]>=64)return 3;values[i]=p->v[vr[i]];}return 0;}
FMI_EXPORT fmi2Status fmi2DoStep(fmi2Component c,fmi2Real,fmi2Real dt,fmi2Boolean){
 if(!c||dt<=0)return 3;auto*p=static_cast<Controller*>(c);auto*v=p->v;
 int id=static_cast<int>(v[1]);
 if(v[0]>.5&&id>=0&&id<512&&!p->done[id]){
  if(p->current!=id){p->current=id;p->dwell=0;v[20]=v[21]=0;}
  p->dwell+=dt;
  if(p->dwell>=.06){bool bad=v[2]>v[50]||v[3]<.5;p->done[id]=true;v[22]=id;
   if(bad){v[21]=1;v[28]+=1;p->jet=.32;}else{v[20]=1;v[27]+=1;}}
 }else if(v[0]<.5){p->current=-1;p->dwell=0;v[20]=v[21]=0;}
 p->jet=std::max(0.,p->jet-dt);double command=p->jet>0?1.:0.;v[23]+=(command-v[23])*(1-std::exp(-dt/.035));
 const double target=(v[8]>=15&&v[8]<=20)?v[8]:v[51];
 v[25]=(v[4]>=target&&v[5]>.5&&v[6]<.5)?1.:0.;
 v[26]=v[7]>=6?1.:0.;
 v[24]=(v[5]>.5&&v[4]<target&&v[6]<.5&&v[7]<6)?1.:0.;
 return 0;
}

FMI_EXPORT fmi2Status fmi2GetInteger(fmi2Component, const fmi2ValueReference*, size_t, fmi2Integer*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2SetInteger(fmi2Component, const fmi2ValueReference*, size_t, const fmi2Integer*) { return fmi2OK; }
FMI_EXPORT fmi2Status fmi2GetBoolean(fmi2Component, const fmi2ValueReference*, size_t, fmi2Boolean*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2SetBoolean(fmi2Component, const fmi2ValueReference*, size_t, const fmi2Boolean*) { return fmi2OK; }
FMI_EXPORT fmi2Status fmi2GetString(fmi2Component, const fmi2ValueReference*, size_t, fmi2String*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2SetString(fmi2Component, const fmi2ValueReference*, size_t, const fmi2String*) { return fmi2OK; }
FMI_EXPORT fmi2Status fmi2GetFMUstate(fmi2Component, void**) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2SetFMUstate(fmi2Component, void*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2FreeFMUstate(fmi2Component, void**) { return fmi2OK; }
FMI_EXPORT fmi2Status fmi2SerializedFMUstateSize(fmi2Component, void*, size_t*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2SerializeFMUstate(fmi2Component, void*, fmi2Byte*, size_t) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2DeSerializeFMUstate(fmi2Component, const fmi2Byte*, size_t, void**) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2GetDirectionalDerivative(fmi2Component, const fmi2ValueReference*, size_t, const fmi2ValueReference*, size_t, const fmi2Real*, fmi2Real*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2SetRealInputDerivatives(fmi2Component, const fmi2ValueReference*, size_t, const fmi2Integer*, const fmi2Real*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2GetRealOutputDerivatives(fmi2Component, const fmi2ValueReference*, size_t, const fmi2Integer*, fmi2Real*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2CancelStep(fmi2Component) { return fmi2OK; }
FMI_EXPORT fmi2Status fmi2GetStatus(fmi2Component, int, fmi2Status*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2GetRealStatus(fmi2Component, int, fmi2Real*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2GetIntegerStatus(fmi2Component, int, fmi2Integer*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2GetBooleanStatus(fmi2Component, int, fmi2Boolean*) { return fmi2Error; }
FMI_EXPORT fmi2Status fmi2GetStringStatus(fmi2Component, int, fmi2String*) { return fmi2Error; }

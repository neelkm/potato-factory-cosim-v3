// Public PhysX particle-buffer API, exposed to Python through a tiny C ABI.
// The application updates only inlet/drain particles, between completed steps.
#include "PxParticleBuffer.h"
extern "C" {
__declspec(dllexport) void* particle_positions(void* buffer) {
    return static_cast<physx::PxParticleBuffer*>(buffer)->getPositionInvMasses();
}
__declspec(dllexport) void* particle_velocities(void* buffer) {
    return static_cast<physx::PxParticleBuffer*>(buffer)->getVelocities();
}
__declspec(dllexport) unsigned particle_count(void* buffer) {
    return static_cast<physx::PxParticleBuffer*>(buffer)->getNbActiveParticles();
}
__declspec(dllexport) void particles_changed(void* buffer) {
    auto p=static_cast<physx::PxParticleBuffer*>(buffer);
    p->raiseFlags(physx::PxParticleBufferFlag::eUPDATE_POSITION);
    p->raiseFlags(physx::PxParticleBufferFlag::eUPDATE_VELOCITY);
}
}

"""Capability-checked entry points for factory and NVIDIA coupling strategies.

Selecting a policy does not imply a backend implements proxy contacts. The
factory adapters qualify whole-assembly transfer. NVIDIA's native adapters
expose richer boundary ports in their separately pinned environments.
"""
from dataclasses import dataclass
import numpy as np
from .nvidia import HandoffPolicy,HandoffZone,ReplicaRouter,SlotPool,CouplingMode

@dataclass(frozen=True)
class Capabilities:
    assembly_transfer:bool=False
    hold_proxy:bool=False
    harvest_proxy_force:bool=False
    apply_wrench:bool=False

FACTORY_CAPABILITIES={'physx':Capabilities(assembly_transfer=True),'newton':Capabilities(assembly_transfer=True)}

def select_policy(*,assembly,contact_across_boundary,capabilities,requested='auto'):
    if requested=='auto':
        requested='assembly_transaction' if assembly else ('nvidia_force' if contact_across_boundary else 'nvidia_teleport')
    if requested=='assembly_transaction':
        if not all(c.assembly_transfer for c in capabilities.values()):raise ValueError('Every participant must support assembly transfer')
        return requested
    if assembly:raise ValueError('Per-body NVIDIA boundary policies cannot split jointed or contained assemblies')
    if requested=='nvidia_teleport':
        if contact_across_boundary:raise ValueError('Teleport requires a contact-free boundary with sufficient supporting halo geometry')
    elif requested=='nvidia_replica':
        if not all(c.hold_proxy for c in capabilities.values()):raise ValueError('Replica contact requires proxy-capable adapters on both sides')
    elif requested=='nvidia_force':
        if not any(c.harvest_proxy_force and c.hold_proxy for c in capabilities.values()) or not any(c.apply_wrench for c in capabilities.values()):
            raise ValueError('Force exchange requires a measured proxy wrench and a receiving wrench port')
    else:raise ValueError('Unknown coupling policy: '+requested)
    return requested

def create_nvidia_zone_policy(*,zones,cells,bodies,start_owners,capabilities):
    for zone in zones:
        select_policy(assembly=False,contact_across_boundary=zone.mode!='teleport',
                      capabilities={name:capabilities[name] for name in zone.cells},requested='nvidia_'+zone.mode)
    return HandoffPolicy(zones=zones,cells=cells,bodies=bodies,start_owners=start_owners,
                         force_capable={n:capabilities[n].harvest_proxy_force for n in cells},
                         proxy_capable={n:capabilities[n].hold_proxy for n in cells})

def connect_boundary(simulation,source,target,mode):
    """Retain the original graph API and its same-tick ordering semantics."""
    return simulation.connect(source,target,CouplingMode(mode))

class TransactionalReplicaRouter:
    """Preserve NVIDIA routing while making overflow a failed preparation.

    Changes commit only after the whole boundary batch fits. This protects
    router bookkeeping; physical commands still require a worker barrier.
    """
    def __init__(self,*args,**kwargs):self.native=ReplicaRouter(*args,**kwargs)
    def route(self,outputs,inputs):
        for rows in outputs:
            if rows.ndim!=2 or rows.shape[1]!=16 or not np.isfinite(rows).all():raise ValueError('Malformed boundary record')
            ids=rows[:,:3]
            if np.any(ids!=np.floor(ids)) or np.any(abs(ids)>=2**24):raise ValueError('Boundary identifiers must be exact float32 integers')
        owners=self.native.owners.copy();transitions=self.native.transitions
        prepared=[np.zeros_like(port) for port in inputs]
        try:counts=self.native.route(outputs,prepared)
        except BaseException:
            self.native.owners[:]=owners;self.native.transitions=transitions;raise
        for target,source,count in zip(inputs,prepared,counts):target[:count]=source[:count]
        return counts

__all__=['Capabilities','FACTORY_CAPABILITIES','select_policy','create_nvidia_zone_policy','connect_boundary',
         'TransactionalReplicaRouter','HandoffPolicy','HandoffZone','ReplicaRouter','SlotPool','CouplingMode']

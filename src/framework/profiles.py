"""Explicit choices: simpler controls and transport share production contracts."""
from dataclasses import dataclass,asdict

@dataclass(frozen=True)
class Profile:
    name:str
    controller:str='ovfmi'
    transport:str='shared_memory'
    contact_policy:str='assembly_transaction'
    description:str='Full factory with native FMI, PhysX and Newton.'
    def validate(self):
        if self.controller not in ('ovfmi','python'):raise ValueError('Unknown controller')
        if self.transport not in ('shared_memory','rpc'):raise ValueError('Unknown transport')
        if self.contact_policy!='assembly_transaction':raise ValueError('Loaded factory assemblies require the qualified assembly policy; use coupling samples for boundary experiments')
        return self

PROFILES={
    'production':Profile('production'),
    'simple_controls':Profile('simple_controls',controller='python',description='Python reference controller; the same native rigid/fluid physics.'),
    'diagnostic_rpc':Profile('diagnostic_rpc',transport='rpc',description='Native FMI and physics, with inspectable RPC snapshot transport.'),
}
def get_profile(name):
    if name not in PROFILES:raise ValueError('Unknown execution profile: '+name)
    return PROFILES[name].validate()

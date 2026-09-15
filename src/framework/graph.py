"""NVIDIA USD topology, graph compiler and exchange plan over isolated workers."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
import json,time
import numpy as np
from .nvidia import load_topology,WavefrontScheduler,SerialExecutor
from fmi_control import INPUTS,OUTPUTS
ROOT=Path(__file__).resolve().parents[2]

class RpcExecutor(SerialExecutor):
    """Parallelize only pure RPC callbacks, never native Warp/engine host calls."""
    def initialize(self,cells,base_rate_hz):
        super().initialize(cells,base_rate_hz)
        for cell in cells.values():
            if cell.engine.implementation!='script' or cell.engine._device!='cpu':raise ValueError('RPC executor accepts only CPU callback adapters')
            if cell.engine.rate_hz!=base_rate_hz:raise ValueError('RPC adapters declare their communication rate; native substeps belong to the worker')
        self.pool=ThreadPoolExecutor(max_workers=len(cells),thread_name_prefix='cosim-rpc')
        self.timings={}
    def _run_remote(self,name,dt):
        started=time.perf_counter();engine=self._cells[name].engine
        engine.apply_inputs();engine.step(dt);engine.publish_outputs()
        return time.perf_counter()-started
    def run_batch(self,names,base_dt,plan):
        # All Warp copies happen here on the coordinator thread. Callbacks see
        # pre-created CPU NumPy views and perform serialized RPC on each worker.
        for name in names:plan.run_inbound(name)
        futures={name:self.pool.submit(self._run_remote,name,base_dt) for name in names}
        errors=[]
        for name,future in futures.items():
            try:
                seconds=future.result();row=self.timings.setdefault(name,{'calls':0,'seconds':0.})
                row['calls']+=1;row['seconds']+=seconds
            except BaseException as exc:errors.append(exc)
        if errors:raise errors[0]
    def close(self):self.pool.shutdown(wait=True)

def validate_contracts(path,base_rate=30):
    """Reject unit/frame/layout/rate mismatches before any graph execution."""
    from pxr import Usd
    stage=Usd.Stage.Open(str(path));ports={};edges=[]
    if stage is None:raise ValueError('Topology cannot be opened')
    for prim in stage.Traverse():
        if prim.GetTypeName()=='OmniSimPort':
            def get(key):return prim.GetAttribute(key).Get()
            key=f'{prim.GetParent().GetName()}/{prim.GetName()}'
            row=dict(frame=get('sim:port:frame'),layout=get('factory:layout'),units=get('factory:units'),rate=get('sim:port:rateHz'))
            if not row['frame'] or not row['layout'] or not row['units']:raise ValueError('Incomplete port contract '+key)
            if row['rate']!=base_rate:raise ValueError('Explicit rate adapter required for '+key)
            ports[key]=row
        if prim.GetTypeName()=='OmniSimCoupling':
            edges.append((prim.GetAttribute('sim:coupling:source').Get(),prim.GetAttribute('sim:coupling:target').Get()))
    for source,target in edges:
        if source not in ports or target not in ports:raise ValueError('Unresolved contract edge')
        if ports[source]!=ports[target]:raise ValueError(f'Port contract mismatch: {source} -> {target}')
    return ports

class FactoryGraph:
    def __init__(self,coordinator,control,profile):
        self.coordinator=coordinator;self.control_worker=control;self.profile=profile
        self.executor=RpcExecutor();self.last_outputs={};self.samples=0
        path=ROOT/'configs/factory_topology.usda';self.contracts=validate_contracts(path)
        self.sim=load_topology(path,base_rate_hz=30,scripts={'sense':self.sense,'control':self.control,'line':self.line,'packing':self.packing},
                               scheduler=WavefrontScheduler(),executor=self.executor)
        self.sim.initialize()
        levels=list(self.sim.scheduler.batches(0))
        if levels!=[['sensors'],['controller'],['line','packing']]:raise RuntimeError('Unexpected factory execution graph: '+str(levels))
    def _check(self,row):
        if row.shape!=(10,) or not np.isfinite(row).all():raise RuntimeError('Malformed control port')
        if row[9]!=self.coordinator.tick or self.coordinator.tick>=2**24:raise RuntimeError('Stale or unrepresentable control tick')
    def sense(self,t,dt,ports):
        inputs=self.coordinator.engines['physx'].call('collect_inputs',dt=dt)
        ports['Inputs'][0]=[*[inputs[k] for k in INPUTS],self.coordinator.tick]
    def control(self,t,dt,ports):
        row=ports['Inputs'][0];self._check(row)
        outputs=self.control_worker.call('control',dt=dt,inputs={k:float(row[i]) for i,k in enumerate(INPUTS)})
        ports['Outputs'][0]=[*[outputs[k] for k in OUTPUTS],self.coordinator.tick]
        self.last_outputs=outputs;self.samples+=1
    def line(self,t,dt,ports):
        row=ports['Outputs'][0];self._check(row)
        engine=self.coordinator.engines['physx']
        engine.call('apply_controls',outputs={k:float(row[i]) for i,k in enumerate(OUTPUTS)})
        engine.call('advance',steps=8,dt=1/240)
    def packing(self,t,dt,ports):
        self._check(ports['Interlocks'][0])
        self.coordinator.engines['newton'].call('advance',steps=8,dt=1/240)
    def step(self):
        with self.coordinator._lock:
            self.coordinator.assert_ready()
            try:
                self.sim.step();expected=self.coordinator.tick+8
                if any(worker.tick!=expected for worker in [*self.coordinator.engines.values(),self.control_worker]):raise RuntimeError('Native clocks differ after graph barrier')
                self.coordinator.tick=expected
            except BaseException as exc:self.coordinator.fail(exc);raise
    def report(self):
        revision=json.loads((ROOT/'vendor/nvidia_cosim_revision.json').read_text())
        return dict(version='3.0.0',upstream=revision,profile=asdict(self.profile),scheduler='NVIDIA WavefrontScheduler',
                    topology='configs/factory_topology.usda',batches=list(self.sim.scheduler.batches(0)),
                    base_rate_hz=30,native_rates_hz={'physx':240,'newton':960,'controller':30},
                    ticks=self.sim.tick,controller_samples=self.samples,cell_timings=self.executor.timings,
                    rpc_timings={name:worker.metrics for name,worker in {**self.coordinator.engines,'fmi':self.control_worker}.items()},
                    port_contracts=self.contracts,failed=self.coordinator.failed)
    def close(self):self.executor.close()

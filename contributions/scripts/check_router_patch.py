"""Generate and exercise a minimal transactional ReplicaRouter candidate."""
from pathlib import Path
import sys,types,difflib,json,importlib.util,subprocess,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'vendor/nvidia_cosim'))
from cosim.core.partition import ReplicaRouter

def check(router_type):
    gate={0:{'workers':(0,1),'plane':(0,0,1,0)}}
    router=router_type(gate,[0,0],.1)
    rows=np.zeros((2,16),np.float32);rows[:,0]=[0,1];rows[:,3]=.2;rows[:,9]=1
    buffers=[np.full((1,16),17,np.float32) for _ in range(2)]
    try:router.route([rows,np.empty((0,16))],buffers)
    except RuntimeError as error:
        if 'overflow' not in str(error):raise
    else:raise AssertionError('Fixture did not overflow')
    atomic=list(router.owners)==[0,0] and router.transitions==0 and all(np.all(a==17) for a in buffers)
    good=router_type(gate,[0,0],.1);buffers=[np.zeros((2,16),np.float32) for _ in range(2)]
    counts=good.route([rows,np.empty((0,16))],buffers)
    assert counts==[2,2] and list(good.owners)==[1,1] and good.transitions==2
    return atomic

def main():
    source=ROOT/'vendor/nvidia_cosim/cosim/core/partition.py';original=source.read_text()
    start=original.index('    def route(self, outputs, inputs):',original.index('class ReplicaRouter:'))
    end=original.index('\n\nclass RigidPartitionWorker:',start)
    route=original[start:end]
    route=route.replace('        counts = [0] * len(inputs)',
                        '        destinations = inputs\n        inputs = [np.empty_like(port) for port in destinations]\n        owners = self.owners.copy()\n        transitions = self.transitions\n        counts = [0] * len(inputs)')
    route=route.replace('self.owners[object_id]','owners[object_id]').replace('self.transitions += 1','transitions += 1')
    route=route.replace('        return counts',
                        '        for destination, prepared, count in zip(destinations, inputs, counts):\n            destination[:count] = prepared[:count]\n        self.owners[:] = owners\n        self.transitions = transitions\n        return counts')
    modified=original[:start]+route+original[end:]
    directory=ROOT/'output/contribution_test';directory.mkdir(exist_ok=True)
    candidate=directory/'partition_candidate.py';candidate.write_text(modified)
    spec=importlib.util.spec_from_file_location('cosim.core.partition_candidate',candidate);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    old=check(ReplicaRouter);new=check(module.ReplicaRouter)
    assert old is False and new is True
    patches=ROOT/'contributions/patches';patches.mkdir(exist_ok=True)
    patch=''.join(difflib.unified_diff(original.splitlines(True),modified.splitlines(True),fromfile='a/cosim/core/partition.py',tofile='b/cosim/core/partition.py'))
    patch_path=patches/'0001-transactional-replica-router.patch';patch_path.write_text(patch,newline='\n')
    subprocess.run(['git','apply','--check','--directory=vendor/nvidia_cosim',str(patch_path)],cwd=ROOT,check=True)
    result=dict(passed=True,original_preserves_state_on_overflow=old,candidate_preserves_state_on_overflow=new,successful_two_object_crossing=True,
                patch_applies_to_pin=True,patch_sha256=hashlib.sha256(patch_path.read_bytes()).hexdigest(),scope='CPU routing transaction; no native contact dynamics')
    (ROOT/'output/router_contribution_validation.json').write_text(json.dumps(result,indent=2));print(result)
if __name__=='__main__':main()

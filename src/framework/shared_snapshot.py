"""Portable shared arrays; the completion receipt fences all writes."""
from multiprocessing.shared_memory import SharedMemory
import numpy as np

class SharedSnapshot:
    def __init__(self,paths=(),water_capacity=0,descriptor=None):
        self.owner=descriptor is None
        self.paths=list(paths if self.owner else descriptor['paths']);self.blocks={};self.arrays={}
        specs={'poses':(len(self.paths),7)}
        if water_capacity:specs['water']=(water_capacity,3)
        if not self.owner:specs={k:tuple(v['shape']) for k,v in descriptor['arrays'].items()}
        try:
            for key,shape in specs.items():
                block=SharedMemory(create=True,size=int(np.prod(shape))*4) if self.owner else SharedMemory(name=descriptor['arrays'][key]['name'])
                self.blocks[key]=block;self.arrays[key]=np.ndarray(shape,dtype=np.float32,buffer=block.buf)
                if self.owner:self.arrays[key].fill(np.nan)
        except BaseException:self.close();raise

    def descriptor(self):return {'paths':self.paths,'arrays':{k:{'name':b.name,'shape':self.arrays[k].shape} for k,b in self.blocks.items()}}

    def write(self,snapshot):
        if list(snapshot['paths'])!=self.paths:raise RuntimeError('Snapshot body ordering changed')
        self.arrays['poses'][:]=snapshot['poses'];count=len(snapshot.get('water',()))
        if count:
            if 'water' not in self.arrays or count>len(self.arrays['water']):raise RuntimeError('Water snapshot capacity exceeded')
            self.arrays['water'][:count]=snapshot['water']
        return {'water_count':count,'status':snapshot.get('status'),'tick':snapshot.get('tick',snapshot.get('status',{}).get('tick'))}

    def read(self,receipt):
        count=receipt['water_count']
        return {'paths':self.paths,'poses':self.arrays['poses'],'water':self.arrays.get('water',np.empty((0,3),np.float32))[:count],
                'status':receipt.get('status'),'tick':receipt['tick']}

    def close(self):
        self.arrays.clear()
        for block in self.blocks.values():
            block.close()
            if self.owner:block.unlink()
        self.blocks.clear()

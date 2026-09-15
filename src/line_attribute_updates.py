"""Write physics attributes only when their exact commanded values change."""
import numpy as np
import ovstage

class ChangedAttributes:
    def __init__(self):
        self.values={};self.dirty=False;self.writes=0
    def write(self,line,paths,name,values):
        key=(tuple(paths),name);array=np.asarray(values,np.float32)
        previous=self.values.get(key)
        if previous is not None and np.array_equal(previous,array):return
        self.values[key]=array.copy()
        tensor=array
        if array.ndim==2:
            tensor=ovstage.make_dltensor(array,dtype=ovstage.DLDataType(ovstage.DLDataTypeCode.kDLFloat,32,array.shape[1]),shape=[len(array)],ndim=1)
        line.stage.write_attribute(line.query(paths),name,line.ordinal,tensor,is_array=False).wait()
        self.dirty=True;self.writes+=1

def optimize_source(source):
    source=source.replace('        self.queries={};', '        from line_attribute_updates import ChangedAttributes\n        self.changed_attributes=ChangedAttributes()\n        self.queries={};')
    start=source.index('    def write(self,path,name,values):')
    end=source.index('    def read(self):',start)
    source=source[:start]+'''    def write(self,path,name,values):
        self.changed_attributes.write(self,[path],name,values)
'''+source[end:]
    source=source.replace('self.ordinal+=1;self.velocity.read(self.vel);','self.ordinal+=1;self.changed_attributes.dirty=False;self.velocity.read(self.vel);')
    source=source.replace("self.stage.write_attribute(self.query(list(self.potatoes)),'physxRigidBody:angularDamping',self.ordinal,damping,is_array=False).wait()", "self.changed_attributes.write(self,list(self.potatoes),'physxRigidBody:angularDamping',damping)")
    source=source.replace("self.stage.write_attribute(self.query(roller_paths),'drive:angular:physics:targetVelocity',self.ordinal,np.full(len(roller_paths),math.degrees(self.motor_speed/ROLL_RADIUS),np.float32),is_array=False).wait()", "self.changed_attributes.write(self,roller_paths,'drive:angular:physics:targetVelocity',np.full(len(roller_paths),math.degrees(self.motor_speed/ROLL_RADIUS),np.float32))")
    source=source.replace('self.stage.advance_write_floor(self.ordinal).wait();self.px.update_from_ovstage(self.ordinal,self.ordinal)', 'self.stage.advance_write_floor(self.ordinal).wait()\n        if self.changed_attributes.dirty:self.px.update_from_ovstage(self.ordinal,self.ordinal)')
    return source

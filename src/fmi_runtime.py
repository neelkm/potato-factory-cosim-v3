"""Independent control worker: native ovfmi or explicit Python reference backend."""
import numpy as np
from config import OUT
from fmi_control import Controller,INPUTS,OUTPUTS

class FmiRuntime:
    def __init__(self,source='factory_fmi.usda',backend='ovfmi'):
        self.tick=0;self.backend=backend;self.stage=None;self.steps=0
        if backend=='ovfmi':
            import ovstage
            self.stage=ovstage.Stage('factory-v3-control')
            ovstage.population.open_usd(self.stage,str(OUT/source),ordinal=1)
            self.stage.advance_write_floor(1).wait()
            self.controller=Controller(self.stage,OUT/source)
        elif backend=='python':
            from simple_control import SimpleController
            self.controller=SimpleController()
        else:raise ValueError('Unknown control backend')
        # ovfmi's FMPy backend initializes from USD start values on its first
        # step, ignoring that call's mapped inputs. Complete this idle startup
        # before tick zero; all live samples then receive a full control step.
        # The FMU epoch is offset by one communication interval from the plant.
        self.startup_offset=1/30
        initial=dict.fromkeys(INPUTS,0.);initial['targetCount']=18.
        self.controller.step(self.startup_offset,**initial)
    def describe(self):
        from importlib.metadata import version
        return dict(engine=self.backend,tick=self.tick,versions={'ovfmi':version('ovfmi')} if self.backend=='ovfmi' else {},rate_hz=30,startup_offset_seconds=self.startup_offset)
    def control(self,dt,inputs):
        if set(inputs)!=set(INPUTS) or not np.isfinite(list(inputs.values())).all():raise ValueError('Incomplete or nonfinite controller inputs')
        if abs(dt-1/30)>1e-12:raise ValueError('Factory controller expects 30 Hz')
        output=self.controller.step(dt,**inputs)
        if not set(OUTPUTS).issubset(output) or not np.isfinite([output[k] for k in OUTPUTS]).all():raise RuntimeError('Incomplete or nonfinite controller output')
        self.tick+=8;self.steps+=1
        return {k:float(output[k]) for k in OUTPUTS}
    def close(self):
        self.controller.close()
        if self.stage:self.stage.destroy()

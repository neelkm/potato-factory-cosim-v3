"""Compare the simpler control option with the actual native ovfmi FMU."""
import json
from config import OUT
from fmi_runtime import FmiRuntime
from fmi_control import INPUTS,OUTPUTS

def main():
    native=FmiRuntime();simple=FmiRuntime(backend='python');peak=0.;rows=0
    try:
        for tick in range(600):
            inputs=dict.fromkeys(INPUTS,0.)
            inputs.update(presence=float(tick%6<4),objectId=tick//6,defectScore=.3 if tick%18<6 else .01,
                          washed=float(tick%24>=6),boxCount=tick%22,boxReady=float(tick%31!=0),
                          armBusy=float(tick%29==0),palletCount=6 if tick>580 else 0,targetCount=15+tick%6)
            a=native.control(1/30,inputs);b=simple.control(1/30,inputs)
            for key in OUTPUTS:
                delta=abs(a[key]-b[key]);peak=max(peak,delta)
                tolerance=2e-6 if key=='valvePressure' else 0.
                if delta>tolerance:raise RuntimeError(f'Controller mismatch at tick {tick}, {key}: {a[key]} != {b[key]}')
            rows+=1
        report=dict(passed=True,samples=rows,compared_values=rows*len(OUTPUTS),max_error=peak,native=native.describe(),reference=simple.describe())
        (OUT/'control_parity_validation.json').write_text(json.dumps(report,indent=2));print(report,flush=True)
    finally:native.close();simple.close()
if __name__=='__main__':main()

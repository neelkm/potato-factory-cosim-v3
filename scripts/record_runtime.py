"""Record package and hardware provenance without credentials or host config."""
from pathlib import Path
import ctypes,json,os,platform,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[1]

class Memory(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in ['total','available','page_total','page_available','virtual_total','virtual_available','extended']]

def main():
    packages={};dependency_checks={}
    for environment in ['coordinator','physx','newton']:
        executable=ROOT/('.venv_'+environment)/'Scripts/python.exe'
        code="import importlib.metadata as m,json,platform;print(json.dumps(dict(python=platform.python_version(),packages={d.metadata['Name']:d.version for d in m.distributions()})))"
        packages[environment]=json.loads(subprocess.check_output([str(executable),'-c',code],text=True))
        dependency_checks[environment]=subprocess.check_output([str(executable),'-m','pip','check'],text=True).strip()
    memory=Memory();memory.length=ctypes.sizeof(memory);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'],text=True).strip()
    source=ROOT/'reference/ovfmi/python';installed=ROOT/'.venv_physx/Lib/site-packages/ovfmi'
    mismatches=[p.name for p in source.glob('*.py') if not (installed/p.name).exists() or p.read_text()!=(installed/p.name).read_text()]
    if mismatches:raise RuntimeError('Installed ovfmi differs from the pinned source: '+str(mismatches))
    report=dict(platform=platform.platform(),logical_cpu_count=os.cpu_count(),ram_gib=memory.total/2**30,gpu=gpu,runtimes=packages,dependency_checks=dependency_checks,
                ovfmi_normalized_source_matches_pin=True,ovfmi_source_commit='da9ce230ccaf464aca6a5246ac3ace1c925c4eeb',
                ovnewton_commit='fe5dcfe9e017e2e462ede0ab7dea73120dd0b46d',cosim_commit='8b45d424641ebc74cbc5660a16aa7bc7eb4efeb3')
    (ROOT/'output/runtime_manifest.json').write_text(json.dumps(report,indent=2));print({k:v for k,v in report.items() if k!='runtimes'})
if __name__=='__main__':main()

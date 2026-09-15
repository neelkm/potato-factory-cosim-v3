"""Qualify fresh pinned environments after bootstrap, without a physics run."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
PROBE=ROOT/'output/clean_install_probe'

def main():
    modules={'coordinator':['numpy','scipy','warp','pxr.Usd'],
             'physx':['ovphysx','ovstage','ovrtx','ovfmi'],
             'newton':['newton','ovnewton','ovstage','warp']}
    results={}
    for environment,names in modules.items():
        executable=PROBE/('.venv_'+environment)/'Scripts/python.exe'
        health=subprocess.check_output([str(executable),'-m','pip','check'],cwd=PROBE,text=True).strip()
        code="import importlib,pathlib,sys; names="+repr(names)+"; modules=[importlib.import_module(n) for n in names]; assert all(pathlib.Path(m.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve()) for m in modules); print('ISOLATED_IMPORTS_OK '+','.join(names))"
        imported=subprocess.check_output([str(executable),'-c',code],cwd=PROBE,text=True)
        marker=next(line for line in imported.splitlines() if line.startswith('ISOLATED_IMPORTS_OK'))
        results[environment]=dict(dependencies=health,imports=marker,isolated_package_paths=True)
    command=[str(PROBE/'.venv_coordinator/Scripts/python.exe'),'-m','pytest','tests',
             'vendor/nvidia_cosim/tests/test_graph.py','vendor/nvidia_cosim/tests/test_scheduler.py','vendor/nvidia_cosim/tests/test_handoff.py','-q']
    test_output=subprocess.check_output(command,cwd=PROBE,text=True,stderr=subprocess.STDOUT)
    (ROOT/'logs/clean_install_tests.log').write_text(test_output)
    if '57 passed' not in test_output:raise RuntimeError('Unexpected fresh-install test result')
    report=dict(passed=True,bootstrap='Pinned upstream sources fetched and all three environments installed in a fresh project folder',
                bootstrap_log_sha256=hashlib.sha256((ROOT/'logs/clean_install_probe.log').read_bytes()).hexdigest(),
                environments=results,cpu_tests=57,test_output=test_output.strip(),
                scope='Fresh package installation, independent import paths, package dependency checks and CPU tests. The full native production batch uses the original qualified environments.')
    (ROOT/'output/clean_install_validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()

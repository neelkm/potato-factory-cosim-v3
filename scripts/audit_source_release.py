"""Check the staged publication surface without printing matched secret values."""
from pathlib import Path
import subprocess,re,json
ROOT=Path(__file__).resolve().parents[1]

def main():
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0');paths=[p for p in paths if p]
    patterns=[re.compile(rb'ghp_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{40,}'),
              re.compile(rb'AKIA[A-Z0-9]{16}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
    problems=[];sizes=0
    for name in paths:
        path=ROOT/name;data=path.read_bytes();sizes+=len(data)
        if any(part in ('.git','.venv_physx','.venv_newton','.venv_coordinator','downloads','logs','dist') for part in path.relative_to(ROOT).parts):problems.append([name,'excluded directory'])
        if len(data)>50*1024**2:problems.append([name,'large artifact belongs in a release'])
        if any(pattern.search(data) for pattern in patterns):problems.append([name,'credential pattern'])
    report=dict(passed=not problems,tracked_files=len(paths),source_bytes=sizes,problems=problems)
    (ROOT/'output/source_publication_validation.json').write_text(json.dumps(report,indent=2));print(report)
    if problems:raise SystemExit(1)
if __name__=='__main__':main()

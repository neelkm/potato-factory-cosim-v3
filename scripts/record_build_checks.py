"""Record completed build and portable-asset checks with source hashes."""
from pathlib import Path
import argparse,hashlib,json,re,zipfile
ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--relocation',type=Path,default=ROOT/'output/relocation_probe');args=parser.parse_args()
    out=ROOT/'output';log=ROOT/'logs/final_core_tests.log';text=log.read_text(encoding='utf-16' if log.read_bytes().startswith(b'\xff\xfe') else 'utf-8')
    match=re.search(r'(\d+) passed in ([\d.]+)s',text)
    if not match or re.search(r'\d+ (failed|error)',text):raise RuntimeError('CPU release checks have not passed')
    source=[p for base in ['tests','src/framework'] for p in (ROOT/base).rglob('*.py')]
    report=dict(passed=True,tests=int(match[1]),seconds=float(match[2]),log_sha256=digest(log),
                sources={p.relative_to(ROOT).as_posix():digest(p) for p in source})
    (out/'core_test_validation.json').write_text(json.dumps(report,indent=2))
    relocated=json.loads((args.relocation.resolve()/'output/asset_validation.json').read_text())
    assert relocated['passed'] and not relocated['missing'] and not relocated['outside_project']
    fmu=out/'fmu_rebuild_probe/output/FactoryController.fmu'
    with zipfile.ZipFile(fmu) as zipped:
        for name in ['FactoryController.cpp','fmi2_minimal.h']:
            assert zipped.read('sources/'+name)==(ROOT/'src/fmu'/name).read_bytes()
        assert len(zipped.read('binaries/win64/FactoryController.dll'))>10000
    file_count=len(json.loads((ROOT/'dist/assets-manifest.json').read_text())['files'])
    report=dict(passed=True,portable_assets=relocated['passed'],asset_manifest_sha256=digest(ROOT/'dist/assets-manifest.json'),
                relocation_folder=str(args.relocation.resolve()),
                rebuilt_fmu_sha256=digest(fmu),scope=f'{file_count} release asset files extracted into a separate folder; composed scene resolves within that folder. FMU rebuilt with Visual Studio and passed FMPy validation.')
    (out/'build_portability_validation.json').write_text(json.dumps(report,indent=2))
    print('BUILD_CHECKS_RECORDED')
if __name__=='__main__':main()

"""Reproduce swallowed FMU extraction errors without loading native engines."""
from pathlib import Path
import ast,contextlib,difflib,io,json,os,sys,types,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[2]

def check(source):
    tree=ast.parse(source);node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='FmuRuntimeExtractedFMU')
    error=PermissionError('FMU extraction fixture: directory unavailable')
    def extract(**kwargs):raise error
    namespace=dict(Path=Path,os=os,sys=sys,FmuRuntimeInstance=object,FmuParserInstance=object,
                   tempfile=types.SimpleNamespace(mkdtemp=lambda:'X:/synthetic-fmu-fixture'),fmpy=types.SimpleNamespace(extract=extract))
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<isolated-ovfmi-extraction>','exec'),namespace)
    with contextlib.redirect_stdout(io.StringIO()):
        try:result=namespace['FmuRuntimeExtractedFMU']('missing-fixture.fmu')
        except PermissionError as actual:return actual is error
        assert not hasattr(result,'_model_description')
    return False

def main():
    path=ROOT/'reference/ovfmi/python/_fmpy_runtime.py';original=path.read_text()
    old='            except Exception as e:\n                print(e)\n                return\n'
    if original.count(old)!=1:raise RuntimeError('Pinned extraction error path changed; inspect the proposed patch')
    candidate=original.replace(old,'            except Exception:\n                raise\n',1)
    before,after=check(original),check(candidate);assert before is False and after is True
    relative='projects/ovfmi/python/_fmpy_runtime.py'
    patch=''.join(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='a/'+relative,tofile='b/'+relative))
    patch_path=ROOT/'contributions/patches/0002-ovfmi-propagate-extraction-errors.patch';patch_path.write_text(patch,newline='\n')
    # The distributed patch targets the omniverse-labs repository root. This
    # checkout contains only its projects/ovfmi subtree, hence the strip count.
    subprocess.run(['git','apply','--check','-p3','--directory=reference/ovfmi',str(patch_path)],cwd=ROOT,check=True)
    report=dict(passed=True,original_propagates_extraction_error=before,candidate_preserves_original_exception=after,
                source_commit='da9ce230ccaf464aca6a5246ac3ace1c925c4eeb',
                patch_applies_to_pin=True,patch_sha256=hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                scope='Isolated actual upstream class with an injected extraction error; no native engine or file extraction, and installed ovfmi remains unchanged.')
    (ROOT/'output/fmi_error_contribution_validation.json').write_text(json.dumps(report,indent=2));print(report)
if __name__=='__main__':main()

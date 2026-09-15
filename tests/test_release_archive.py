from pathlib import Path
import sys,json,zipfile,hashlib
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from unpack_release import unpack,digest

def fixture(tmp_path,name='output/scene.usda'):
    content=b'#usda 1.0\n';archive=tmp_path/'sample.zip'
    with zipfile.ZipFile(archive,'w') as zipped:zipped.writestr(name,content)
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(dict(group='fixture',archive=archive.name,archive_sha256=digest(archive),
        parts=[dict(name=archive.name,bytes=archive.stat().st_size,sha256=digest(archive))],files=[dict(path=name,bytes=len(content),sha256=hashlib.sha256(content).hexdigest())])))
    return manifest

def test_verified_extract_is_repeatable_and_preserves_edits(tmp_path):
    manifest=fixture(tmp_path);destination=tmp_path/'project';unpack(manifest,destination)
    target=destination/'output/scene.usda';assert target.exists();unpack(manifest,destination)
    target.write_text('user edit')
    with pytest.raises(RuntimeError,match='Existing file differs'):unpack(manifest,destination)
    assert target.read_text()=='user edit'

def test_bad_checksum_is_rejected_before_extraction(tmp_path):
    manifest=fixture(tmp_path);archive=tmp_path/'sample.zip';archive.write_bytes(archive.read_bytes()+b'corruption')
    with pytest.raises(RuntimeError,match='checksum'):unpack(manifest,tmp_path/'project')
    assert not (tmp_path/'project').exists()

def test_archive_cannot_escape_project(tmp_path):
    manifest=fixture(tmp_path,'../outside.usda')
    with pytest.raises(ValueError,match='Unsafe'):unpack(manifest,tmp_path/'project')
    assert not (tmp_path/'outside.usda').exists()

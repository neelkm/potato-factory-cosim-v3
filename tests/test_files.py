import json,os
from framework.files import atomic_json

def test_transient_reader_lock_does_not_abort_publication(tmp_path,monkeypatch):
    real=os.replace;attempts=[]
    def replace(source,target):
        attempts.append(1)
        if len(attempts)<3:raise PermissionError('Windows reader has not released the target')
        real(source,target)
    monkeypatch.setattr(os,'replace',replace);target=tmp_path/'progress.json'
    assert atomic_json(target,{'tick':8},timeout=1.)
    assert json.loads(target.read_text())=={'tick':8} and len(attempts)==3

def test_locked_advisory_progress_preserves_previous_sample(tmp_path,monkeypatch):
    target=tmp_path/'progress.json';target.write_text('{"tick": 0}')
    def locked(*args):raise PermissionError('locked')
    monkeypatch.setattr(os,'replace',locked)
    assert atomic_json(target,{'tick':8},timeout=0,required=False) is False
    assert json.loads(target.read_text())=={'tick':0} and len(list(tmp_path.iterdir()))==1

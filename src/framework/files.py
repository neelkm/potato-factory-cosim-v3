"""Publish complete JSON snapshots despite transient Windows reader locks."""
import json,os,time,uuid
from pathlib import Path

def atomic_json(path,value,*,timeout=10.,required=True):
    path=Path(path);temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,allow_nan=False),encoding='utf8')
    deadline=time.monotonic()+timeout;delay=.01
    try:
        while True:
            try:os.replace(temporary,path);return True
            except PermissionError:
                if time.monotonic()>=deadline:
                    if required:raise
                    # UI progress is advisory. A reader lock must not stop an
                    # otherwise healthy native run; the next sample retries.
                    return False
                time.sleep(delay);delay=min(.2,delay*1.5)
    finally:
        try:temporary.unlink(missing_ok=True)
        except PermissionError:pass

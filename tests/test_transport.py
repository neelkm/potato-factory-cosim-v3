import threading
import pytest
from framework.process import EngineProcess,RemoteEngineError,PROTOCOL

class Connection:
    def __init__(self,response=None,ready=True):self.response=response;self.ready=ready;self.sent=[]
    def send(self,request):self.sent.append(request)
    def poll(self,timeout):return self.ready
    def recv(self):return self.response

def process(connection):
    worker=EngineProcess.__new__(EngineProcess);worker._lock=threading.Lock();worker.failed=worker.closed=False
    worker.request_id=0;worker.tick=8;worker.metrics={};worker.timeout=.001;worker.engine='fixture';worker.connection=connection
    return worker

def test_timeout_latches_connection_and_never_accepts_late_reply():
    connection=Connection(ready=False);worker=process(connection)
    with pytest.raises(TimeoutError):worker.call('advance',steps=8)
    connection.ready=True;connection.response=dict(protocol=PROTOCOL,request_id=1,ok=True,tick=16,value={})
    with pytest.raises(RuntimeError,match='failed'):worker.call('export_state')
    assert len(connection.sent)==1 and worker.tick==8

@pytest.mark.parametrize('reply',[
    dict(protocol=PROTOCOL,request_id=0,ok=True,tick=16,value={}),
    dict(protocol=PROTOCOL-1,request_id=1,ok=True,tick=16,value={}),
])
def test_receipt_identity_is_mandatory(reply):
    worker=process(Connection(reply))
    with pytest.raises(RuntimeError,match='receipt'):worker.call('advance',steps=8)
    assert worker.failed and worker.tick==8

def test_known_application_error_preserves_channel_for_rollback():
    worker=process(Connection(dict(protocol=PROTOCOL,request_id=1,ok=False,tick=8,error='invalid import')))
    with pytest.raises(RemoteEngineError):worker.call('import_state',states=[])
    assert not worker.failed and worker.tick==8
    assert worker.connection.sent[0]['expected_tick']==8

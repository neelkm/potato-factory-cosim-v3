"""Sequenced RPC with isolated native interpreters and shared snapshots."""
from pathlib import Path
from multiprocessing.connection import Listener
import os,subprocess,threading,time
from .shared_snapshot import SharedSnapshot
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL=2

class RemoteEngineError(RuntimeError):
    """Received application error: request outcome is known."""

class EngineProcess:
    def __init__(self,engine,timeout=180):
        self.engine=engine;self.timeout=timeout;self.failed=False;self.closed=False
        self.tick=None;self.request_id=0;self.snapshot=None;self._lock=threading.Lock();self.metrics={}
        (ROOT/'logs').mkdir(exist_ok=True)
        key=os.urandom(32);listener=Listener(('127.0.0.1',0),authkey=key)
        listener._listener._socket.settimeout(timeout)
        self.log=(ROOT/'logs'/f'{engine}_worker.log').open('a',encoding='utf8')
        env=os.environ.copy();env['FACTORY_IPC_KEY']=key.hex()
        exe=ROOT/('.venv_newton' if engine=='newton' else '.venv_physx')/'Scripts/python.exe'
        try:
            self.process=subprocess.Popen([str(exe),'-u',str(ROOT/'src/engine_worker.py'),engine,str(listener.address[1])],
                                          stdout=self.log,stderr=subprocess.STDOUT,env=env,cwd=ROOT)
            self.connection=listener.accept()
        except BaseException:
            if hasattr(self,'process'):
                self.process.terminate();self.process.wait(timeout=10)
            self.log.close();raise
        finally:listener.close()
        try:self.call('ping')
        except BaseException:self.close();raise

    def call(self,method,**kwargs):
        with self._lock:
            if self.failed or self.closed:raise RuntimeError(f'{self.engine} connection is failed or closed')
            self.request_id+=1;started=time.perf_counter()
            try:
                self.connection.send(dict(protocol=PROTOCOL,request_id=self.request_id,expected_tick=self.tick,method=method,args=kwargs))
                if not self.connection.poll(self.timeout):raise TimeoutError(f'{self.engine} timed out during {method}; outcome is ambiguous')
                response=self.connection.recv()
                if response.get('protocol')!=PROTOCOL or response.get('request_id')!=self.request_id:raise RuntimeError('Stale or mismatched worker receipt')
                self.tick=response.get('tick')
            except BaseException:self.failed=True;raise
            finally:
                row=self.metrics.setdefault(method,dict(calls=0,seconds=0.));row['calls']+=1;row['seconds']+=time.perf_counter()-started
            if not response['ok']:raise RemoteEngineError(response['error'])
            return response['value']

    def configure_snapshot(self,paths,water_capacity=0):
        self.snapshot=SharedSnapshot(paths,water_capacity);self.call('configure_snapshot',descriptor=self.snapshot.descriptor())

    def capture(self,method):
        if self.snapshot is None:return self.call(method)
        return self.snapshot.read(self.call('snapshot',snapshot_method=method))

    def close(self):
        if self.closed:return
        try:
            if self.process.poll() is None and not self.failed:
                try:self.call('close')
                except BaseException:self.failed=True
            if self.process.poll() is None and self.failed:self.process.terminate()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        finally:
            self.closed=True;self.connection.close();self.log.close()
            if self.snapshot:self.snapshot.close()

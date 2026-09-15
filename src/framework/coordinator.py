"""Fail-closed clocks and complete-assembly ownership transactions."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import threading
import time
import uuid
from state_protocol import Transfer, continuity

class Coordinator:
    def __init__(self, engines, owners):
        self.engines=engines;self.owners=dict(owners);self.events=[];self.tick=0
        self.pending_transfer=None;self.failed=False;self.closed=False;self.failure=None
        self._lock=threading.RLock()
        self.pool=ThreadPoolExecutor(max_workers=len(engines),thread_name_prefix='engine-barrier')

    def assert_ready(self):
        if self.failed or self.closed:raise RuntimeError('Coordinator is failed or closed; start a fresh run')
        if self.pending_transfer is not None:raise RuntimeError('An ownership transaction is still pending')

    def fail(self,error):self.failed=True;self.failure=str(error)

    def advance(self,steps=1,dt=1/240):
        """Reference RPC barrier for small samples and diagnostics."""
        with self._lock:
            self.assert_ready()
            try:
                futures={n:self.pool.submit(e.call,'advance',steps=steps,dt=dt) for n,e in self.engines.items()}
                reports={};errors=[]
                for name,future in futures.items():
                    try:reports[name]=future.result()
                    except Exception as exc:errors.append(exc)
                if errors:raise errors[0]
                expected=self.tick+steps
                if any(r['tick']!=expected for r in reports.values()):raise RuntimeError('Engine clocks diverged')
                self.tick=expected
            except BaseException as exc:self.fail(exc);raise

    def close(self):self.closed=True;self.pool.shutdown(wait=True)

    @staticmethod
    def _assert_inactive(reply,paths,inactive):
        if not isinstance(reply,dict) or 'inactive' not in reply:raise RuntimeError('Missing native activation receipt')
        recorded=set(reply['inactive'])
        if (inactive and not set(paths).issubset(recorded)) or (not inactive and set(paths)&recorded):
            raise RuntimeError('Native activation receipt disagrees with ownership')

    def transfer(self,paths,source,destination,membership=None,joint_states=None):
        with self._lock:
            self.assert_ready()
            if not paths or len(paths)!=len(set(paths)):raise ValueError('Empty or duplicate transfer group')
            if source==destination or source not in self.engines or destination not in self.engines:raise ValueError('Invalid transfer engines')
            if any(self.owners.get(p)!=source for p in paths):raise RuntimeError('Sender does not own the complete transfer group')
            sender,receiver=self.engines[source],self.engines[destination]
            states=sender.call('export_state',paths=paths)
            if {s['path'] for s in states}!=set(paths):raise RuntimeError('Sender exported an incomplete transfer group')
            packet=Transfer(self.tick,source,destination,states,membership or {},joint_states or {}).validate()
            transaction_id=uuid.uuid4().hex
            self.pending_transfer=dict(**asdict(packet),transaction_id=transaction_id,phase='prepare',echoed=None)
            started=time.perf_counter()
            try:
                self._assert_inactive(sender.call('set_active',paths=paths,active=False),paths,True)
                self.pending_transfer['phase']='source_frozen'
                receiver.call('import_state',states=states,joint_states=packet.joint_states)
                self._assert_inactive(receiver.call('set_active',paths=paths,active=True),paths,False)
                echoed=receiver.call('export_state',paths=paths);self.pending_transfer['echoed']=echoed
                error=continuity(states,echoed);self.pending_transfer['phase']='validated'
            except BaseException as exc:
                self.pending_transfer['error']=str(exc);self.fail(exc)
                try:
                    self._assert_inactive(receiver.call('set_active',paths=paths,active=False),paths,True)
                    sender.call('import_state',states=states,joint_states=packet.joint_states)
                    self._assert_inactive(sender.call('set_active',paths=paths,active=True),paths,False)
                    self.pending_transfer['phase']='rolled_back'
                except BaseException as rollback_error:
                    self.pending_transfer['rollback_error']=str(rollback_error);self.pending_transfer['phase']='halted_ambiguous'
                raise
            for path in paths:self.owners[path]=destination
            event=dict(tick=self.tick,source=source,destination=destination,paths=paths,transaction_id=transaction_id,
                       protocol_version=packet.version,digest=packet.digest,continuity=error,states=states,echoed=echoed,
                       membership=packet.membership,joint_states=packet.joint_states,prepared=True,committed=True,
                       seconds=time.perf_counter()-started,policy='assembly_transaction')
            self.events.append(event);self.pending_transfer=None
            return event

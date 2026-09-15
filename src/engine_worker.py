"""One native runtime per worker, with sequenced clock-aware receipts."""
import os,sys,traceback
from multiprocessing.connection import Client
PROTOCOL=2

def main():
    engine,port=sys.argv[1:3]
    connection=Client(('127.0.0.1',int(port)),authkey=bytes.fromhex(os.environ.pop('FACTORY_IPC_KEY')))
    runtime=None;snapshot=None;expected_request=1
    try:
        while True:
            request=connection.recv();method=request.get('method');rid=request.get('request_id')
            response=dict(protocol=PROTOCOL,request_id=rid,ok=False,tick=getattr(runtime,'tick',None))
            try:
                if request.get('protocol')!=PROTOCOL or rid!=expected_request:raise RuntimeError('Invalid RPC sequence')
                expected_request+=1
                if request.get('expected_tick')!=getattr(runtime,'tick',None):raise RuntimeError('RPC clock precondition failed')
                args=request.get('args',{})
                if method=='ping':value=engine
                elif method=='close':
                    if runtime:runtime.close();runtime=None
                    value=None
                elif method=='load':
                    if runtime:raise RuntimeError('Worker runtime is already loaded')
                    if engine=='newton':from newton_engine import NewtonEngine as Runtime
                    elif engine=='fmi':from fmi_runtime import FmiRuntime as Runtime
                    elif args.pop('factory',False):from line_adapter import PhysXLineAdapter as Runtime
                    else:from physx_engine import PhysXEngine as Runtime
                    runtime=Runtime(**args);value=runtime.describe()
                elif method=='configure_snapshot':
                    from framework.shared_snapshot import SharedSnapshot
                    if snapshot:raise RuntimeError('Snapshot buffer already configured')
                    snapshot=SharedSnapshot(descriptor=args['descriptor']);value=True
                elif method=='snapshot':
                    if snapshot is None:raise RuntimeError('No snapshot buffer configured')
                    data=getattr(runtime,args['snapshot_method'])();value=snapshot.write(data)
                else:
                    if runtime is None:raise RuntimeError('Worker not loaded')
                    value=getattr(runtime,method)(**args)
                response.update(ok=True,value=value,tick=getattr(runtime,'tick',None))
            except BaseException:
                response.update(error=traceback.format_exc(),tick=getattr(runtime,'tick',None));print(response['error'],flush=True)
            connection.send(response)
            if method=='close':break
    except EOFError:pass
    finally:
        if runtime:
            try:runtime.close()
            except BaseException:traceback.print_exc()
        if snapshot:snapshot.close()
        connection.close()

if __name__=='__main__':main()

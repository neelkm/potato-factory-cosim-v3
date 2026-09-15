"""Run NVIDIA rendering on a child process's main thread, away from Tk."""
def run_viewport(commands,frames,source='factory_replay.usdc',cache='cache'):
    import queue,time,math
    import numpy as np
    from rtx_replay import Replay,VIEWS,metrics,station_times
    renderer=None
    try:
        renderer=Replay(960,540,24,source=source,cache=cache,tag='desktop');previous=None
        def ready():
            profile=renderer.meta.get('framework',{}).get('profile',{}).get('controller','ovfmi')
            frames.put(('ready',renderer.meta['seconds'],station_times(renderer.meta),'Python control' if profile=='python' else 'FMI control'))
        ready()
        while True:
            cmd=commands.get()
            if cmd[0]=='close':break
            if cmd[0]=='reload':
                renderer.close();renderer=None
                renderer=Replay(960,540,24,source=cmd[1],tag='desktop',cache=cmd[2]);previous=None
                ready();continue
            _,t,view,orbit,zoom=cmd
            eye,target=VIEWS[view];d=np.array(eye)-np.array(target);rad=np.linalg.norm(d)*zoom
            az=math.atan2(d[1],d[0])+orbit[0];el=max(.08,min(1.4,math.asin(d[2]/np.linalg.norm(d))+orbit[1]))
            eye=np.array(target)+rad*np.array([math.cos(el)*math.cos(az),math.cos(el)*math.sin(az),math.sin(el)])
            before=time.monotonic()
            if previous is None or previous!=(view,orbit,zoom):
                for _ in range(2):renderer.render(t,eye,target)
            img=renderer.render(t,eye,target);elapsed=time.monotonic()-before;previous=(view,orbit,zoom)
            try:frames.put((img,t,metrics(renderer.meta,t),elapsed),timeout=.5)
            except queue.Full:pass
    except Exception as e:frames.put(('error',str(e)))
    finally:
        if renderer:renderer.close()

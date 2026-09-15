"""FIELD / FLOW: a small desktop USD factory simulator and RTX replay viewer."""
import sys,threading,queue,time,math,json,subprocess,os
import multiprocessing as mp
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from viewport_worker import run_viewport

class FactoryApp:
    def __init__(self,root):
        self.root=root;root.title('FIELD / FLOW 3.0 — Co-simulation factory');root.geometry('1280x900');root.minsize(1100,840);root.configure(bg='#0c191b')
        self.commands=mp.Queue();self.frames=mp.Queue(maxsize=2);self.t=0.;self.playing=False;self.speed=1.;self.view='Overall';self.duration=90.;self.drag=None;self.orbit=(0,0);self.zoom=1
        self.busy=False;self.closing=False;self.reload=None
        self.shots=json.loads((ROOT/'output/storyboard.json').read_text()) if (ROOT/'output/storyboard.json').exists() else []
        self.station_times={}
        header=tk.Frame(root,bg='#0c191b');header.pack(fill='x',padx=24,pady=(20,15))
        tk.Label(header,text='FIELD / FLOW',fg='#f2eee3',bg='#0c191b',font=('Segoe UI',24,'bold')).pack(side='left')
        tk.Label(header,text='WASH · SORT · PACK · DISPATCH',fg='#82a69e',bg='#0c191b',font=('Segoe UI',10)).pack(side='left',padx=25)
        self.state=tk.Label(header,text='Preparing RTX viewport…',fg='#e9bd6a',bg='#0c191b',font=('Segoe UI',10));self.state.pack(side='right')
        body=tk.Frame(root,bg='#0c191b');body.pack(fill='both',expand=True,padx=24)
        sidebar=tk.Frame(body,bg='#14272a',width=220);sidebar.pack(side='left',fill='y',padx=(0,16));sidebar.pack_propagate(False)
        tk.Label(sidebar,text='STATIONS',fg='#82a69e',bg='#14272a',font=('Segoe UI',10,'bold')).pack(anchor='w',padx=16,pady=(10,6))
        views=['Overall','Truck unloading','Water wash','Quality & rejection','Carton filling','Robot palletizing','Forklift dispatch','Factory hero']
        for i,v in enumerate(views):
            station=self.button(sidebar,f'{i:02d}   {v}',lambda v=v:self.set_view(v));station.configure(pady=3);station.pack(fill='x',padx=12,pady=1)
        tk.Label(sidebar,text='RECORDED RUN',fg='#82a69e',bg='#14272a',font=('Segoe UI',10,'bold')).pack(anchor='w',padx=16,pady=(10,6))
        self.counts=tk.Label(sidebar,text='Loading…',justify='left',anchor='w',fg='#f2eee3',bg='#14272a',font=('Segoe UI',12));self.counts.pack(fill='x',padx=16)
        tk.Label(sidebar,text='Drag to orbit · Scroll to zoom',justify='left',fg='#82a69e',bg='#14272a',font=('Segoe UI',10)).pack(anchor='w',padx=16,pady=8)
        tk.Label(sidebar,text='NEXT SIMULATION',fg='#82a69e',bg='#14272a',font=('Segoe UI',10,'bold')).pack(anchor='w',padx=16,pady=(8,6))
        self.profile_names={'Full simulation':'production','Simple controls':'simple_controls','Diagnostic transport':'diagnostic_rpc'}
        self.profile=tk.StringVar(value='Full simulation')
        self.profile_menu=ttk.Combobox(sidebar,textvariable=self.profile,values=list(self.profile_names),state='readonly',width=23);self.profile_menu.pack(fill='x',padx=12)
        self.profile_note=tk.Label(sidebar,text='',fg='#aec6be',bg='#14272a',font=('Segoe UI',9),wraplength=185,justify='left')
        self.profile_note.pack(fill='x',padx=16,pady=4)
        def describe_profile(*_):
            notes={'Full simulation':'FMI controls the wash, inspection and packing. PhysX and Newton simulate the factory.',
                   'Simple controls':'Use an equivalent Python controller. The same native physics engines still simulate the factory.',
                   'Diagnostic transport':'Use native controls and physics with inspectable message-based snapshots.'}
            self.profile_note.config(text=notes[self.profile.get()])
        self.profile.trace_add('write',describe_profile);describe_profile()
        self.coupling_button=self.button(sidebar,'Coupling options & examples',lambda:os.startfile(str(ROOT/'docs/coupling_options.md')));self.coupling_button.pack(fill='x',padx=12,pady=3)
        right=tk.Frame(body,bg='#0c191b');right.pack(side='left',fill='both',expand=True)
        self.canvas=tk.Label(right,bg='#1b2f31',text='Loading the USD stage and RTX renderer…',fg='#e9e4d6',font=('Segoe UI',15));self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<ButtonPress-1>',self.drag_start);self.canvas.bind('<B1-Motion>',self.drag_move);self.canvas.bind('<MouseWheel>',self.scroll)
        controls=tk.Frame(right,bg='#14272a');controls.pack(fill='x',pady=(12,0))
        self.playbtn=self.button(controls,'▶ Play',self.toggle);self.playbtn.pack(side='left',padx=10,pady=10)
        self.button(controls,'↺ Reset',self.reset).pack(side='left',padx=5)
        speed=tk.StringVar(value='1×')
        menu=ttk.Combobox(controls,textvariable=speed,values=['0.25×','0.5×','1×','2×'],state='readonly',width=5);menu.pack(side='left',padx=5)
        menu.bind('<<ComboboxSelected>>',lambda e:setattr(self,'speed',float(speed.get()[:-1])))
        self.slider=tk.Scale(controls,from_=0,to=45,resolution=.033,orient='horizontal',showvalue=False,bg='#14272a',fg='#dce4de',troughcolor='#305146',highlightthickness=0,command=self.scrub)
        self.slider.pack(side='left',fill='x',expand=True,padx=10)
        self.clock=tk.Label(controls,text='00.0 / 45.0 s',bg='#14272a',fg='#e9e4d6',font=('Segoe UI',10));self.clock.pack(side='right',padx=12)
        footer=tk.Frame(root,bg='#0c191b');footer.pack(fill='x',padx=24,pady=14)
        self.run_button=self.button(footer,'Run simulation',self.resimulate);self.run_button.pack(side='left',padx=(0,10))
        for label,cmd in [('Open Blender scene',self.open_blender),('Play finished video',self.open_video),('Open output folder',lambda:os.startfile(str(ROOT/'output')))]:self.button(footer,label,cmd).pack(side='left',padx=(0,10))
        self.engine_label=tk.Label(footer,text='Version 3.0 · NVIDIA cosim · RTX',bg='#0c191b',fg='#82a69e',font=('Segoe UI',10));self.engine_label.pack(side='right')
        root.protocol('WM_DELETE_WINDOW',self.close);root.bind('<space>',lambda e:self.toggle())
        self.replay_source=sys.argv[sys.argv.index('--source')+1] if '--source' in sys.argv else 'factory_replay.usdc'
        self.replay_cache=sys.argv[sys.argv.index('--cache')+1] if '--cache' in sys.argv else 'cache'
        self.renderer_process=mp.Process(target=run_viewport,args=(self.commands,self.frames,self.replay_source,self.replay_cache),daemon=True)
        self.renderer_process.start();self.request();root.after(60,self.poll)
    def button(self,parent,label,cmd):return tk.Button(parent,text=label,command=cmd,bg='#234039',activebackground='#365e4d',fg='#f2eee3',activeforeground='white',relief='flat',bd=0,font=('Segoe UI',10),padx=12,pady=7,cursor='hand2')
    def request(self):
        control=[]
        while not self.commands.empty():
            try:
                cmd=self.commands.get_nowait()
                if cmd[0]!='render':control.append(cmd)
            except queue.Empty:break
        for cmd in control:self.commands.put(cmd)
        self.commands.put(('render',self.t,self.view,self.orbit,self.zoom))
    def set_view(self,v):
        self.view=v;self.orbit=(0,0);self.zoom=1
        shot=next((s for s in self.shots if s['view']==v),None)
        if v in self.station_times or shot:
            self.t=self.station_times[v] if v in self.station_times else shot['t0'];self.updating=True;self.slider.set(self.t);self.updating=False
        self.request()
    def toggle(self):self.playing=not self.playing;self.playbtn.config(text='❚❚ Pause' if self.playing else '▶ Play');self.last=time.monotonic();self.request()
    def reset(self):self.playing=False;self.t=0;self.slider.set(0);self.playbtn.config(text='▶ Play');self.request()
    def scrub(self,value):
        if not getattr(self,'updating',False):self.t=float(value);self.request()
    def drag_start(self,e):self.drag=(e.x,e.y)
    def drag_move(self,e):
        if self.drag:self.orbit=(self.orbit[0]+(e.x-self.drag[0])*.007,max(-.7,min(.7,self.orbit[1]+(e.y-self.drag[1])*.004)));self.drag=(e.x,e.y);self.request()
    def scroll(self,e):self.zoom=max(.35,min(2.7,self.zoom*(.90 if e.delta>0 else 1.11)));self.request()
    def poll(self):
        if self.reload:
            source,cache=self.reload;self.reload=None;self.t=0
            self.commands.put(('reload',source,cache));self.request()
        try:
            item=self.frames.get_nowait()
            if isinstance(item[0],str) and item[0]=='ready':
                self.duration=item[1];self.slider.config(to=self.duration)
                self.station_times=item[2]
                if len(item)>3:self.engine_label.config(text='3.0 · NVIDIA cosim · '+item[3]+' · RTX')
                if '--smoke-ui' in sys.argv:print('UI_TEST renderer ready',flush=True)
                self.root.after(60,self.poll);return
            if isinstance(item[0],str):self.state.config(text='Renderer needs attention');messagebox.showerror('RTX viewer',item[1]);return
            a,t,m,elapsed=item;self.displayed_time=t;im=Image.fromarray(a);w=max(640,self.canvas.winfo_width());h=max(360,self.canvas.winfo_height());im.thumbnail((w,h),Image.Resampling.LANCZOS)
            self.photo=ImageTk.PhotoImage(im);self.canvas.config(image=self.photo,text='')
            self.state.config(text=f'{self.view}  ·  RTX {elapsed:.2f}s / frame',fg='#94c8a7')
            self.counts.config(text=f"{m['washed']:3d}  Washed\n{m['accepted']:3d}  Accepted\n{m['rejected']:3d}  Rejected\n\n{m['box_count']:2d} / {m['box_target']:2d}  In carton\n{m['pallet']:2d} / 6    On pallet")
            self.slider.config(to=self.duration);self.clock.config(text=f'{t:04.1f} / {self.duration:.1f} s')
            if self.playing:
                now=time.monotonic();self.t=(self.t+(now-self.last)*self.speed)%self.duration;self.last=now
                self.updating=True;self.slider.set(self.t);self.updating=False;self.request()
        except queue.Empty:pass
        if self.busy and hasattr(self,'active_cache'):
            try:
                progress=json.loads((ROOT/'output'/self.active_cache/'progress.json').read_text())
                self.state.config(text=f"Simulating · {progress.get('pallet',0)} / 6 cartons · {progress.get('time',0):.0f}s",fg='#e9bd6a')
            except (OSError,ValueError):pass
        if not self.closing:self.root.after(60,self.poll)
    def open_blender(self):subprocess.Popen([str(ROOT/'tools/blender-4.5.13-windows-x64/blender.exe'),str(ROOT/'output/potato_factory.blend')])
    def open_video(self):
        p=ROOT/'output/potato_factory.mp4'
        if p.exists():os.startfile(str(p))
        else:messagebox.showinfo('Video','Render the film with Render video.cmd first.')
    def resimulate(self):
        if self.busy:return
        selected_profile=self.profile_names[self.profile.get()]
        self.busy=True;self.state.config(text='Co-simulation run in progress…');self.playing=False
        def run():
            try:
                cache='rerun_'+time.strftime('%Y%m%d_%H%M%S');source=cache+'.usdc';self.active_cache=cache
                with open(ROOT/'output/rerun.log','w') as log:
                    subprocess.run([str(ROOT/'.venv_coordinator/Scripts/python.exe'),str(ROOT/'src/simulate_factory.py'),'--seconds',str(max(1200,int(self.duration)+60)),'--cache',cache,'--profile',selected_profile],cwd=ROOT,stdout=log,stderr=log,check=True)
                    subprocess.run([sys.executable,str(ROOT/'src/validate_run.py'),'--cache',cache],cwd=ROOT,stdout=log,stderr=log,check=True)
                    subprocess.run([sys.executable,str(ROOT/'src/bake_replay.py'),'--cache',cache,'--name',source],cwd=ROOT,stdout=log,stderr=log,check=True)
                self.reload=(source,cache)
                self.root.after(0,lambda:self.slider.set(0))
                self.root.after(0,lambda:messagebox.showinfo('Physics complete','The new simulation is loading in the viewport.'))
            except Exception as e:
                if not self.closing:self.root.after(0,lambda:messagebox.showerror('Simulation','The simulation stopped before finishing. Open the output folder to inspect the run report.'))
            finally:self.busy=False
        threading.Thread(target=run,daemon=True).start()
    def close(self):
        self.closing=True;self.playing=False
        if self.busy and hasattr(self,'active_cache'):
            cancel=ROOT/'output'/self.active_cache
            cancel.mkdir(exist_ok=True)
            (cancel/'stop.request').touch()
        self.commands.put(('close',));deadline=time.monotonic()+10
        def finish():
            if self.renderer_process.is_alive():
                if time.monotonic()>deadline:self.renderer_process.terminate()
                self.root.after(100,finish)
            else:self.root.destroy()
        finish()

if __name__=='__main__':
    mp.freeze_support()
    import tkinter as tk
    from tkinter import ttk,messagebox
    from PIL import Image,ImageTk
    root=tk.Tk();app=FactoryApp(root)
    if '--smoke-ui' in sys.argv:
        smoke={'phase':0,'deadline':time.monotonic()+300}
        def capture():
            if time.monotonic()>smoke['deadline']:
                print('UI_SMOKE_FAILED: timeout',flush=True);app.renderer_process.terminate();os._exit(2)
            if hasattr(app,'photo') and smoke['phase']==0:
                smoke['phase']=1;app.set_view('Water wash');app.t=23;app.slider.set(23);app.request()
            elif smoke['phase']==1 and abs(getattr(app,'displayed_time',0)-23)<.05:
                smoke['phase']=2;app.speed=.5;app.toggle()
            elif smoke['phase']==2 and getattr(app,'displayed_time',0)>23.1:
                app.toggle();smoke['phase']=3;app.set_view('Quality & rejection');app.t=29;app.slider.set(29);app.request()
            elif smoke['phase']==3 and abs(getattr(app,'displayed_time',0)-29)<.05:
                smoke['phase']=4;app.reload=(app.replay_source,app.replay_cache)
            elif smoke['phase']==4 and abs(getattr(app,'displayed_time',29))<.05:
                smoke['phase']=5;app.set_view('Quality & rejection')
                shot=next((s for s in app.shots if s['view']=='Quality & rejection'),None)
                smoke['target']=(shot['event_time']+.5) if shot else 29
                app.t=smoke['target'];app.slider.set(smoke['target']);app.orbit=(.03,0);app.zoom=.97;app.request()
            elif smoke['phase']==5 and abs(getattr(app,'displayed_time',0)-smoke['target'])<.05:
                from PIL import ImageGrab
                import ctypes
                sizes=[]
                for size in ['1100x840','1280x900']:
                    root.geometry(size)
                    for profile in app.profile_names:
                        app.profile.set(profile);root.update()
                        for widget in [app.profile_menu,app.coupling_button,app.run_button]:
                            parent=widget.master
                            assert widget.winfo_ismapped() and widget.winfo_height()>=widget.winfo_reqheight(), 'A main control is clipped'
                            assert widget.winfo_x()>=0 and widget.winfo_y()>=0 and widget.winfo_x()+widget.winfo_width()<=parent.winfo_width() and widget.winfo_y()+widget.winfo_height()<=parent.winfo_height(), 'A main control is outside its panel'
                    sizes.append(size)
                app.profile.set('Full simulation');root.update()
                hwnd=ctypes.windll.user32.GetAncestor(root.winfo_id(),2)
                ImageGrab.grab(window=hwnd).save(ROOT/'output/app_screenshot.png')
                import hashlib
                simulation=ROOT/'output'/app.replay_cache/'simulation.json'
                replay=ROOT/'output'/app.replay_source
                receipt=dict(passed=True,cache=app.replay_cache,source=app.replay_source,
                             app_sha256=hashlib.sha256((ROOT/'app.py').read_bytes()).hexdigest(),visible_control_sizes=sizes,visible_control_profiles=list(app.profile_names),
                             simulation_sha256=hashlib.sha256(simulation.read_bytes()).hexdigest(),
                             replay_sha256=hashlib.sha256(replay.read_bytes()).hexdigest(),
                             checks=['RTX viewport','station switching','timeline seek','half-speed playback','orbit','zoom','replay reload','main controls visible at supported window sizes'])
                (ROOT/'output/ui_smoke_validation.json').write_text(json.dumps(receipt,indent=2))
                print('UI_SMOKE_PASS: RTX viewport, station switching, timeline seek, half-speed playback, orbit, zoom and replay reload',flush=True);app.close();return
            root.after(500,capture)
        root.after(2000,capture)
    root.mainloop()

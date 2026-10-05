"""Factory app's interactive debug workspace and deterministic UI demonstration."""
import json, time
import tkinter as tk
from tkinter import ttk,messagebox
from PIL import ImageTk
from physics_debug import DebugData,DebugState,DebugRenderer,ROOT,BG,PANEL,TEXT,MUTED,CYAN

class PhysicsDebugWindow:
    def __init__(self,parent,standalone=False):
        self.window=parent if standalone else tk.Toplevel(parent)
        self.window.title('FIELD / FLOW — Physics debug workspace')
        self.window.geometry('1320x900');self.window.minsize(1180,850);self.window.configure(bg=BG)
        self.data=DebugData();self.state=DebugState();self.renderer=DebugRenderer(self.data)
        self.playing=False;self.speed=.5;self.last=time.monotonic();self.drag=None;self.updating=False;self.closed=False
        header=tk.Frame(self.window,bg=BG);header.pack(fill='x',padx=20,pady=(12,6))
        tk.Label(header,text='FIELD / FLOW',font=('Segoe UI',19,'bold'),bg=BG,fg=TEXT).pack(side='left')
        tk.Label(header,text='PHYSICS DEBUG WORKSPACE',font=('Segoe UI',11),bg=BG,fg=CYAN).pack(side='left',padx=20)
        self.button(header,'Data & scope',self.scope).pack(side='right')
        bar=tk.Frame(self.window,bg=PANEL);bar.pack(fill='x',padx=20,pady=4)
        self.mode=tk.StringVar(value=self.state.mode)
        self.mode_control=ttk.Combobox(bar,textvariable=self.mode,values=['Forklift alignment','Engine handoff'],state='readonly',width=20)
        self.mode_control.pack(side='left',padx=8,pady=8);self.mode_control.bind('<<ComboboxSelected>>',lambda e:self.set_mode(self.mode.get()))
        self.button(bar,'Dock close-up',self.closeup).pack(side='left',padx=4)
        self.button(bar,'Reset camera',self.reset_camera).pack(side='left',padx=4)
        self.toggles={}
        for field,label in [('contacts','Contacts'),('com','COM'),('velocity','Velocity'),('produce','Produce'),('ghost','Export ghost')]:
            var=tk.BooleanVar(value=getattr(self.state,field));self.toggles[field]=var
            tk.Checkbutton(bar,text=label,variable=var,command=lambda f=field,v=var:self.option(f,v.get()),bg=PANEL,fg=TEXT,selectcolor=BG,activebackground=PANEL,activeforeground=TEXT,font=('Segoe UI',10)).pack(side='left',padx=4)
        # A pixel-sized requested size prevents image dimensions from pushing
        # timeline controls and captions outside a fixed-size Tk window.
        self.image_label=tk.Label(self.window,bg=BG,width=1,height=1);self.image_label.pack(fill='both',expand=True,padx=20)
        self.image_label.bind('<ButtonPress-1>',self.down);self.image_label.bind('<B1-Motion>',self.move);self.image_label.bind('<ButtonRelease-1>',self.up)
        self.image_label.bind('<MouseWheel>',self.wheel)
        self.window.bind('<Left>',lambda e:self.step(-1));self.window.bind('<Right>',lambda e:self.step(1));self.window.bind('<space>',lambda e:self.toggle())
        controls=tk.Frame(self.window,bg=PANEL);controls.pack(fill='x',padx=20,pady=4)
        self.play=self.button(controls,'▶ Play',self.toggle);self.play.pack(side='left',padx=6,pady=5)
        self.button(controls,'− Step',lambda:self.step(-1)).pack(side='left',padx=3)
        self.button(controls,'+ Step',lambda:self.step(1)).pack(side='left',padx=3)
        self.slider=tk.Scale(controls,from_=0,to=self.data.steps,orient='horizontal',showvalue=False,bg=PANEL,fg=TEXT,troughcolor='#305146',highlightthickness=0,command=self.seek_command,resolution=1)
        self.slider.pack(side='left',fill='x',expand=True,padx=8)
        self.clock=tk.Label(controls,bg=PANEL,fg=CYAN,font=('Consolas',11),width=16);self.clock.pack(side='left',padx=6)
        speed=tk.StringVar(value='0.5×');speed_control=ttk.Combobox(controls,textvariable=speed,values=['0.1×','0.25×','0.5×','1×'],width=6,state='readonly');speed_control.pack(side='left',padx=8)
        speed_control.bind('<<ComboboxSelected>>',lambda e:setattr(self,'speed',float(speed.get()[:-1])))
        bookmarks=tk.Frame(self.window,bg=BG);bookmarks.pack(fill='x',padx=20,pady=3)
        for label,tick in [('Handoff',0),('First native step',1),('First fork contact',self.data.first_contact or 0),('Lift',14*240)]:
            self.button(bookmarks,label,lambda t=tick:self.seek(t)).pack(side='left',padx=(0,6))
        self.object=tk.StringVar(value='/World/Pallet')
        self.object_control=ttk.Combobox(bookmarks,textvariable=self.object,values=self.data.paths,width=22,state='readonly');self.object_control.pack(side='left',padx=6)
        self.object_control.bind('<<ComboboxSelected>>',lambda e:self.select(self.object.get()))
        self.button(bookmarks,'Body details',self.details).pack(side='left',padx=6)
        self.button(bookmarks,'Contact details',self.contact_details).pack(side='left',padx=6)
        self.caption=tk.Label(self.window,text='Recorded PhysX reproduction from the factory’s Newton return packet. Drag to orbit; click a body to inspect.',font=('Segoe UI',11),bg=BG,fg=MUTED,anchor='w',wraplength=1250,justify='left')
        self.caption.pack(fill='x',padx=24,pady=(6,12))
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.window.after(100,self.refresh);self.window.after(40,self.poll)
        self.image_label.bind('<Configure>',lambda e:self.schedule_refresh())
        self.refresh_job=None
    def button(self,parent,label,command):
        return tk.Button(parent,text=label,command=command,bg='#234039',fg=TEXT,activebackground='#365e4d',activeforeground='white',relief='flat',font=('Segoe UI',10),padx=10,pady=5,cursor='hand2')
    def schedule_refresh(self):
        if self.closed:return
        if self.refresh_job:self.window.after_cancel(self.refresh_job)
        self.refresh_job=self.window.after(60,self.refresh)
    def refresh(self):
        if self.closed:return
        self.refresh_job=None
        w=max(1,self.image_label.winfo_width());h=max(1,self.image_label.winfo_height())
        if w<600 or h<400:return
        im=self.renderer.render(self.state,w,h)
        self.photo=ImageTk.PhotoImage(im);self.image_label.configure(image=self.photo)
        self.updating=True;self.slider.set(self.state.tick);self.updating=False
        self.clock.configure(text=f'{self.state.tick/self.data.hz:6.3f} / {self.data.steps/self.data.hz:g}s')
    def set_mode(self,mode):
        self.state.mode=mode;self.mode.set(mode);self.state.selected='/World/Pallet';self.object.set(self.state.selected)
        self.state.closeup=mode=='Engine handoff';self.state.zoom=1
        self.seek(0 if mode=='Engine handoff' else (self.data.first_contact or 0));self.refresh()
    def option(self,field,value):setattr(self.state,field,value);self.refresh()
    def closeup(self):self.state.closeup=not self.state.closeup;self.state.zoom=1;self.refresh()
    def reset_camera(self):self.state.azimuth=.65;self.state.elevation=.56;self.state.zoom=1;self.refresh()
    def select(self,path):self.state.selected=path;self.object.set(path);self.refresh()
    def seek_command(self,value):
        # Tk may dispatch Scale callbacks after the Python updating guard is
        # cleared. Ignore our own value to avoid a render/playback feedback loop.
        if not self.updating and int(value)!=self.state.tick:self.seek(int(value))
    def seek(self,tick):self.state.tick=max(0,min(self.data.steps,int(tick)));self.last=time.monotonic();self.refresh()
    def step(self,direction):self.playing=False;self.play.configure(text='▶ Play');self.seek(self.state.tick+direction)
    def toggle(self):self.playing=not self.playing;self.last=time.monotonic();self.play.configure(text='❚❚ Pause' if self.playing else '▶ Play')
    def poll(self):
        if self.closed:return
        now=time.monotonic()
        if self.playing:
            steps=int((now-self.last)*self.data.hz*self.speed)
            if steps:
                self.state.tick=min(self.data.steps,self.state.tick+steps);self.last=now;self.refresh()
                if self.state.tick==self.data.steps:self.toggle()
        self.window.after(30,self.poll)
    def down(self,event):self.drag=(event.x,event.y,event.x,event.y)
    def move(self,event):
        if self.drag:
            x,y,ox,oy=self.drag;self.state.azimuth+=(event.x-x)*.007;self.state.elevation=max(.08,min(1.5,self.state.elevation+(event.y-y)*.004));self.drag=(event.x,event.y,ox,oy);self.refresh()
    def up(self,event):
        if self.drag and abs(event.x-self.drag[2])+abs(event.y-self.drag[3])<6:
            path=self.renderer.pick(event.x,event.y)
            if path in self.data.index:self.select(path)
        self.drag=None
    def wheel(self,event):self.state.zoom=max(.4,min(3,self.state.zoom*(1.1 if event.delta>0 else .9)));self.refresh()
    def text_window(self,title,content):
        top=tk.Toplevel(self.window);top.title(title);top.geometry('850x650')
        frame=ttk.Frame(top);frame.pack(fill='both',expand=True);scroll=ttk.Scrollbar(frame);scroll.pack(side='right',fill='y')
        widget=tk.Text(frame,wrap='word',bg=BG,fg=TEXT,font=('Consolas',11),padx=20,pady=20,yscrollcommand=scroll.set)
        widget.pack(fill='both',expand=True);scroll.configure(command=widget.yview);widget.insert('1.0',content);widget.configure(state='disabled')
    def details(self):
        path=self.state.selected;idx=self.data.index[path];packet=self.data.states.get(path)
        content={'path':path,'source':'Native PhysX reproduction','tick':self.state.tick,'pose_world_m_xyzw':self.data.arrays['poses'][self.state.tick,idx].tolist(),
                 'velocity_world_COM_m_s_and_rad_s':self.data.arrays['velocities'][self.state.tick,idx].tolist(),
                 'imported_mass_COM_body_inertia_about_COM':packet,'Newton_export':self.data.exported.get(path)}
        self.text_window('Body state and transfer metadata',json.dumps(content,indent=2))
    def contact_details(self):
        rows=self.data.contacts(self.state.tick)
        if self.state.mode=='Forklift alignment':rows=self.data.fork_contacts(rows)
        records=[dict(sensor=self.data.sensors[int(r[8])],other_actor=self.data.others[int(r[9])],
                      position_world_m=r[:3].tolist(),normal_world=r[3:6].tolist(),separation_m=float(r[6]),
                      normal_impulse_Ns=float(r[7]),timestep_s=1/self.data.hz) for r in rows]
        self.text_window('Native contacts at selected step',json.dumps(dict(tick=self.state.tick,source=self.data.meta['contact_source'],contacts=records),indent=2))
    def scope(self):
        self.text_window('Debug data provenance',
            'This workspace shows an isolated native PhysX reproduction initialized from the saved production Newton return packet. It does not recreate Newton internals or the full factory.\n\n'
            'Collision surfaces: authored USD collision proxies. Convex hulls are triangulated for display, not dumped from cooked PhysX geometry. Produce markers are optional display points.\n\n'
            'Contact samples: ovphysx raw contact tensors, collected every 1/240 s. Sensors cover Pallet and Forks. Forklift mode filters to fork/pallet pairs. The duplicate sensor direction is removed. Other factory contacts are outside this capture.\n\n'
            'Normal impulse is the native timestep-averaged normal force multiplied by dt. The graph shows peak absolute normal impulse per step; it is not total force. Contact arrows have fixed display length. Negative separation indicates overlap.\n\n'
            'Magenta handoff geometry is the frozen Newton export packet. It is not a running Newton simulation. Tick zero shows the actual PhysX activation readback.\n\n'
            'OvdNext 0.2.6 accepted the small compatibility probe but rejected the larger factory OVD with "unknown OVD command". The viewer therefore uses native contact tensors and has no dependency on redistributed preview binaries.\n\n'
            +json.dumps({**{k:self.data.meta[k] for k in ['scope','source_sha256','source_time','continuity','alignment','contact_source']},
                         'historical_transfer':{k:self.data.meta['event'].get(k) for k in ['tick','source','destination','transaction_id','protocol_version','digest','prepared','committed','continuity']}},indent=2))
    def close(self):self.closed=True;self.playing=False;self.window.destroy()

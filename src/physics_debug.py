"""Portable recorded physics diagnostics; no preview viewer runtime is required.

The same renderer powers the app and its demonstration recording. Arrays are
native samples, not interpolated contact events. Simulation and movie clocks
are intentionally separate.
"""
from dataclasses import dataclass
from pathlib import Path
import json, math
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BG='#0c191f';PANEL='#122931';TEXT='#edf3ed';MUTED='#94b2b5';CYAN='#58dfdb';AMBER='#ffcc75';PINK='#d69ce8'

def rotation(q):
    x,y,z,w=np.asarray(q,float)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

def contacts_at(arrays,tick):
    offsets=arrays['contact_offsets']
    return arrays['contacts'][offsets[tick]:offsets[tick+1]]

def unique_contacts(rows,sensors,others):
    """Do not count both sensor directions of a pallet/fork pair twice."""
    return rows[np.array([not (sensors[int(r[8])]=='/World/Pallet' and others[int(r[9])]=='/World/Forks') for r in rows],bool)]

def visible_edges(vertices,faces):
    """Suppress coplanar triangulation diagonals, retaining true shape edges."""
    edge_normals={}
    for face in faces:
        a,b,c=vertices[face[:3]];normal=np.cross(b-a,c-a);normal/=max(1e-12,np.linalg.norm(normal))
        for a,b in zip(face,np.roll(face,-1)):edge_normals.setdefault(tuple(sorted((int(a),int(b)))),[]).append(normal)
    return [edge for edge,n in edge_normals.items() if len(n)!=2 or abs(float(n[0]@n[1]))<.999]

class DebugData:
    def __init__(self,base=None):
        self.base=Path(base or ROOT/'output/physics_debug')
        view=json.loads((self.base/'view.json').read_text());self.directory=self.base/view['capture']
        self.meta=json.loads((self.directory/'capture.json').read_text())
        # Transfer 'seconds' is transaction wall time, never simulation time.
        self.meta['source_time']=self.meta['event']['tick']/self.meta['hz']
        if self.meta['source_sha256']!=view['simulation_sha256']:raise ValueError('Geometry and capture provenance differ')
        with np.load(self.directory/'motion.npz',allow_pickle=False) as z:self.arrays={k:z[k] for k in z.files}
        self.paths=self.meta['paths'];self.index={p:i for i,p in enumerate(self.paths)};self.steps=self.meta['steps'];self.hz=self.meta['hz']
        self.states={s['path']:s for s in self.meta['imported']}
        self.exported={s['path']:s for s in self.meta['event']['states']}
        self.geometry=[]
        for shape in view['geometry']:
            vertices=np.asarray(shape['vertices']);faces=np.asarray(shape['faces'],int)
            self.geometry.append({**shape,'vertices':vertices, 'faces':faces,
                                  'edges':visible_edges(vertices,faces) if 'Potato_' not in shape['path'] else []})
        self.sensors=self.meta['sensor_paths'];self.others=self.meta['contact_actor_paths']
        self.peak=np.zeros((self.steps+1,2));self.count=np.zeros_like(self.peak,int)
        for tick in range(self.steps+1):
            rows=self.contacts(tick)
            for mode in (0,1):
                chosen=rows if mode else self.fork_contacts(rows)
                if len(chosen):self.peak[tick,mode]=abs(chosen[:,7]).max();self.count[tick,mode]=len(chosen)
        active=np.flatnonzero(self.count[:,0]);self.first_contact=int(active[0]) if len(active) else None
    def contacts(self,tick):return unique_contacts(contacts_at(self.arrays,tick),self.sensors,self.others)
    def fork_contacts(self,rows):
        return rows[np.array([self.sensors[int(r[8])]=='/World/Forks' and self.others[int(r[9])]=='/World/Pallet' for r in rows],bool)]
    def world(self,shape,tick,source=False):
        v=shape['vertices'];path=shape['body']
        if path in self.index:
            pose=self.exported[path]['pose'] if source and path in self.exported else self.arrays['poses'][tick,self.index[path]]
            return v@rotation(pose[3:]).T+pose[:3]
        return v

@dataclass
class DebugState:
    mode: str='Forklift alignment'
    tick: int=0
    selected: str='/World/Pallet'
    azimuth: float=.65
    elevation: float=.56
    zoom: float=1.
    closeup: bool=False
    contacts: bool=True
    com: bool=True
    velocity: bool=False
    produce: bool=False
    ghost: bool=True
    caption: str=''

class DebugRenderer:
    def __init__(self,data):self.data=data;self.fonts={};self.pick_points=[]
    def font(self,size,bold=False):
        from PIL import ImageFont
        key=(size,bold)
        if key not in self.fonts:
            path=Path('C:/Windows/Fonts')/('segoeuib.ttf' if bold else 'segoeui.ttf')
            self.fonts[key]=ImageFont.truetype(str(path),size) if path.exists() else ImageFont.load_default()
        return self.fonts[key]
    def render(self,state,width=1280,height=720):
        from PIL import Image,ImageDraw
        d=self.data;tick=max(0,min(d.steps,int(state.tick)));state.tick=tick
        im=Image.new('RGB',(width,height),BG);draw=ImageDraw.Draw(im)
        side=350;vw=width-side;bottom=height-132;handoff=state.mode=='Engine handoff'
        draw.rectangle((vw,0,width,height),fill=PANEL)
        def text(x,y,value,size=16,color=TEXT,bold=False):draw.text((x,y),str(value),font=self.font(size,bold),fill=color)
        text(24,18,'PHYSICS / '+('ENGINE HANDOFF' if handoff else 'FORKLIFT ALIGNMENT'),22,bold=True)
        text(24,52,'PhysX reproduction  •  240 Hz  •  exact sampled steps',14,MUTED)
        target=np.array([8.12,-1.1,.82] if state.closeup or handoff else [8.12,-2.75,.85])
        az=state.azimuth;el=state.elevation
        view=np.array([math.cos(el)*math.cos(az),math.cos(el)*math.sin(az),math.sin(el)])
        right=np.array([-math.sin(az),math.cos(az),0]);up=np.cross(view,right)
        scale=(245 if state.closeup or handoff else 112)*state.zoom*vw/930
        def project(points):
            p=np.atleast_2d(points)-target
            return np.column_stack((vw*.49+p@right*scale,(bottom+60)*.53-p@up*scale)),p@view
        def line3(a,b,color,width=1):
            xy,_=project([a,b]);draw.line([tuple(xy[0]),tuple(xy[1])],fill=color,width=width)
        for x in np.arange(5,12,.5):line3([x,-9,0],[x,1,0],'#1c343b')
        for y in np.arange(-9,1.5,.5):line3([5,y,0],[12,y,0],'#1c343b')
        faces=[];wire_shapes=[];self.pick_points=[];points_by_body={}
        for shape in d.geometry:
            path=shape['body'] or shape['path'];v=d.world(shape,tick);xy,depth=project(v)
            if 'Potato_' in path:
                if state.produce:
                    center=xy.mean(0)
                    if 0<center[0]<vw and 85<center[1]<bottom:draw.ellipse((center[0]-3,center[1]-3,center[0]+3,center[1]+3),fill=AMBER)
                continue
            points_by_body.setdefault(path,[]).append(v.mean(0))
            if xy[:,0].max()<0 or xy[:,0].min()>vw or xy[:,1].max()<85 or xy[:,1].min()>bottom:continue
            if path=='/World/Pallet':color=np.array([128,91,55])
            elif path=='/World/Forks':color=np.array([45,144,163])
            elif path=='/World/Forklift':color=np.array([134,103,40])
            elif path.startswith(('/World/Box','/World/Flap')):color=np.array([109,123,112])
            else:color=np.array([41,65,73])
            if not shape['body'] or path=='/World/Forklift' or (path=='/World/Forks' and np.ptp(v[:,2])>.5):
                wire_shapes.append((xy,shape['edges'],CYAN if path=='/World/Forks' else '#365965'))
                continue
            for face in shape['faces']:
                pts=xy[face]
                if np.any(pts[:,0]<-width) or np.any(pts[:,0]>width*2):continue
                a,b,c=v[face[:3]];normal=np.cross(b-a,c-a);light=.65+.3*abs(float(normal@view))/(np.linalg.norm(normal)+1e-12)
                fill=tuple((color*light).astype(int));outline='#77cbc7' if path==state.selected else None
                faces.append((float(depth[face].mean()),pts,fill,outline))
        # Far faces first, then nearer surfaces. The view shows authored proxy
        # surfaces; contact positions always come from the native solver.
        for xy,edges,color in wire_shapes:
            for a,b in edges:draw.line([tuple(xy[a]),tuple(xy[b])],fill=color,width=1)
        for _,pts,color,outline in sorted(faces,key=lambda x:x[0]):draw.polygon([tuple(p) for p in pts],fill=color,outline=outline)
        for path,centers in points_by_body.items():
            p=np.mean(centers,axis=0);xy,_=project(p);self.pick_points.append((path,xy[0]))
        if handoff and state.ghost:
            for shape in d.geometry:
                if shape['body'] not in d.exported or 'Potato_' in shape['body']:continue
                xy,_=project(d.world(shape,0,source=True))
                for a,b in shape['edges']:draw.line([tuple(xy[a]),tuple(xy[b])],fill=PINK,width=1)
        pose=d.arrays['poses'][tick,d.index['/World/Pallet']]
        if not handoff:
            actual=d.meta['alignment']['measured_pallet_pose'];x=actual[0]
            line3([8.17,-2.25,.72],[8.17,-.2,.72],PINK,2)
            line3([x,-2.25,.74],[x,-.2,.74],CYAN,2)
            if state.closeup:text(24,88,'Magenta: nominal centre   /   Cyan: measured centre',14,MUTED)
        rows=d.contacts(tick);shown=rows if handoff else d.fork_contacts(rows)
        if state.contacts:
            for row in shown:
                p=row[:3];q=p+row[3:6]*.065;xy,_=project([p,q]);radius=3+min(4,abs(float(row[7]))*15)
                color='#ff856e' if row[6]<-.001 else AMBER
                draw.line([tuple(xy[0]),tuple(xy[1])],fill=color,width=2)
                draw.ellipse((xy[0,0]-radius,xy[0,1]-radius,xy[0,0]+radius,xy[0,1]+radius),fill=color)
        selected=d.states.get(state.selected);idx=d.index.get(state.selected)
        if selected and idx is not None:
            pose=d.arrays['poses'][tick,idx];com=pose[:3]+rotation(pose[3:])@selected['com'];xy,_=project(com)
            if state.com:
                x,y=xy[0];draw.ellipse((x-7,y-7,x+7,y+7),outline=CYAN,width=2);draw.line((x-11,y,x+11,y),fill=CYAN,width=2);draw.line((x,y-11,x,y+11),fill=CYAN,width=2)
            if state.velocity:
                line3(com,com+d.arrays['velocities'][tick,idx,:3]*.6,CYAN,4)
        # Cover clipped geometry outside the viewport before painting HUD.
        draw.rectangle((vw,0,width,height),fill=PANEL)
        draw.rectangle((0,bottom,vw,height),fill=BG)
        draw.rectangle((0,0,vw,80),fill=BG)
        text(24,18,'PHYSICS / '+('ENGINE HANDOFF' if handoff else 'FORKLIFT ALIGNMENT'),22,bold=True)
        text(24,52,'PhysX reproduction  •  240 Hz  •  exact sampled steps',14,MUTED)
        x=vw+20
        text(x,20,'INSPECTOR',13,MUTED,True)
        text(x,46,'Newton → PhysX' if handoff else 'Fork carriage → pallet',21,CYAN,True)
        seconds=tick/d.hz;text(x,82,f'Factory reference   {d.meta["source_time"]+seconds:.3f} s',15)
        text(x,106,f'Reproduction step   {tick:04d}  /  {d.steps}',14,MUTED)
        draw.line((x,138,width-20,138),fill='#31505a')
        if handoff:
            text(x,154,'139 bodies · 6 cartons · 108 potatoes',15,bold=True)
            text(x,182,'Historical transfer log + native readback',13,MUTED)
            residual=d.meta['continuity']
            for j,(label,value) in enumerate([
                ('Position residual',f'{residual["position"]*1000:.6f} mm'),
                ('Linear velocity residual',f'{residual.get("linear_velocity_m_s",0):.6f} m/s'),
                ('Assembly mass',f'{sum(s["mass"] for s in d.states.values()):.3f} kg'),
                ('PhysX disabled → enabled',f'{sum(d.meta["disabled_before"])} → {sum(d.meta["disabled_after"])} disabled')]):
                text(x,212+j*27,label,13,MUTED);text(width-20,212+j*27,'',13)
                valuew=draw.textlength(value,font=self.font(13));text(width-20-valuew,212+j*27,value,13,CYAN)
            text(x,327,'Magenta = frozen Newton export',13,PINK)
            text(x,348,'Cyan = selected PhysX body / COM',13,CYAN)
            text(x,369,'Zero boundary error ≠ zero next-step impact',12,AMBER)
        else:
            shift=d.meta['alignment']['side_shift_m']*1000
            text(x,156,'MEASURED DOCK CORRECTION',13,MUTED,True)
            text(x,184,f'{shift:+.2f} mm',38,CYAN,True)
            text(x,237,'Side-shift travel limit: ±150 mm',14,MUTED)
            text(x,268,f'Nominal pallet X       8.17000 m',15)
            text(x,295,f'Measured pallet X     {d.meta["alignment"]["measured_pallet_pose"][0]:.5f} m',15)
            fork=d.arrays['poses'][tick,d.index['/World/Forks']]
            pallet=d.arrays['poses'][tick,d.index['/World/Pallet']]
            text(x,331,f'Current centre ΔX     {(fork[0]-pallet[0])*1000:+.2f} mm',15,CYAN)
            text(x,355,'Calculated from sampled body origins',12,MUTED)
        y=407
        draw.line((x,y-14,width-20,y-14),fill='#31505a')
        text(x,y,'NATIVE CONTACTS',13,MUTED,True)
        text(x,y+25,f'{len(shown)} points  ·  '+('pallet / fork sensors' if handoff else 'fork ↔ pallet'),15,AMBER)
        peak=float(abs(shown[:,7]).max()) if len(shown) else 0
        sep=float(shown[:,6].min())*1000 if len(shown) else None
        text(x,y+52,f'Peak |normal impulse|    {peak:.5f} N·s',14)
        text(x,y+76,'Min. separation                 '+(f'{sep:+.3f} mm' if sep is not None else 'no contact'),14)
        text(x,y+99,'Impulse = tensor normal force × 1/240 s',12,MUTED)
        if height>=680:
            path=state.selected.rsplit('/',1)[-1];text(x,y+135,'SELECTED  /  '+path,13,CYAN,True)
            if selected and idx is not None:
                vel=d.arrays['velocities'][tick,idx]
                text(x,y+160,f'Mass {selected["mass"]:.3f} kg   |v| {np.linalg.norm(vel[:3]):.4f} m/s',13)
                text(x,y+183,f'|ω| {np.linalg.norm(vel[3:]):.4f} rad/s',13)
                text(x,y+206,'Details: pose, COM, inertia and transfer state',12,MUTED)
        gy=bottom+16;gh=52;gx=25;gw=vw-50
        series=d.peak[:,1 if handoff else 0];top=max(.001,float(series.max()))
        text(gx,gy,'CONTACT IMPULSE HISTORY  /  N·s',11,MUTED,True)
        # Envelope reduction preserves peaks when many native steps share a pixel.
        bins=np.linspace(0,len(series),max(2,int(gw)//2)).astype(int)
        points=[]
        for j in range(len(bins)-1):
            val=series[bins[j]:max(bins[j]+1,bins[j+1])].max()
            points.append((gx+gw*j/(len(bins)-2),gy+gh-val/top*(gh-20)))
        draw.line(points,fill=AMBER,width=2)
        cursor=gx+gw*tick/d.steps;draw.line((cursor,gy+18,cursor,gy+gh+4),fill=CYAN,width=2)
        text(gx,gy+gh+8,'0 s',11,MUTED);text(gx+gw-36,gy+gh+8,f'{d.steps/d.hz:g} s',11,MUTED)
        text(gx,gy+gh+30,'USD collision proxies  •  contact arrows: fixed 65 mm display length  •  drag to orbit / scroll to zoom',11,MUTED)
        return im

    def pick(self,x,y):
        choices=[(np.linalg.norm(p-[x,y]),name) for name,p in self.pick_points]
        return min(choices)[1] if choices and min(choices)[0]<85 else None

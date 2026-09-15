"""Editable metric factory, with render meshes separate from contact proxies."""
import bpy,math,random,json,sys
from pathlib import Path
from mathutils import Vector
import numpy as np
sys.path.insert(0,str(Path(__file__).parent))
from config import *
OUT.mkdir(exist_ok=True);rng=random.Random(81)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
manifest={'version':3,'static':[],'rollers':[],'belts':[],'potatoes':[],'bodies':[],'flaps':[]}
# Share the basic mesh primitives from the first editable Blender scene.
old=(ROOT/'legacy_helpers/build_blender.py').read_text()
exec(old[old.index('def mat('):old.index("# A deterministic UV texture")])
exec(old[old.index('def empty('):old.index('# An open industrial hall')])
orange=mat('Robot_enamel',(.8,.18,.018),.35,.29)
card=mat('Kraft_corrugated_cardboard',(.46,.29,.135),0,.88)
tape=mat('Recycled_paper_tape',(.59,.43,.25),0,.57)
wood=mat('Pallet_softwood',(.45,.32,.19),0,.88)
beltmat=mat('Textured_PU_belt',(.065,.14,.13),.03,.63)
skin.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.72
im=bpy.data.images.load(str(OUT/'potato_albedo.png'));n=skin.node_tree.nodes.new('ShaderNodeTexImage');n.image=im
skin.node_tree.links.new(n.outputs['Color'],skin.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
def body(name,loc,mass,shapes,material,kin=False):
    root=empty(name,loc)
    for i,(p,sz) in enumerate(shapes):box(name+'_panel'+str(i),p,sz,material,root,bevel=.003)
    manifest['bodies'].append(dict(name=name,pos=loc,mass=mass,shapes=shapes,kinematic=kin))
    return root
def angled_static(name,a,b,width,height,material=steel):
    a,b=Vector(a),Vector(b);mid=(a+b)*.5;delta=b-a;angle=math.atan2(delta.y,delta.x)
    o=box(name,mid,(delta.length,width,height),material,bevel=.005);o.rotation_euler.z=angle
    manifest['static'].append(dict(name=name,pos=list(mid),size=(delta.length,width,height),rotate_z=math.degrees(angle)))
static('Factory_floor',(1,0,-.13),(34,20,.25),concrete)
for x in np.arange(-15,19,3):box('Expansion_joint',(x,0,.001),(.009,20,.003),dark,bevel=0)
for y in np.arange(-9,11,3):box('Expansion_joint',(1,y,.001),(34,.009,.003),dark,bevel=0)
for y in [-6.3,6.3]:box('Traffic_marking',(1,y,.005),(31,.065,.008),yellow,bevel=0)
for x in [-12,-6,0,6,12,18]:
    box('Steel_I_column',(x,8.8,3.7),(.21,.26,7.4),dark)
    for dx in [-.11,.11]:box('Column_flange',(x+dx,8.8,3.7),(.03,.38,7.4),dark)
    box('Clerestory_frame',(x,8.9,4.8),(.12,.18,2.6),steel)
box('Rear_wall',(1,9,1.4),(34,.2,2.8),white)
box('Rear_wainscot',(1,8.88,.6),(34,.045,1.2),green)
for z in [2.85,6.5]:box('Wall_beam',(1,8.9,z),(34,.21,.2),dark)
text('Factory_brand','FIELD / FLOW',(2,8.77,2.2),.66,green)
text('Factory_subtitle','FROM FIELD TO PALLET',(2,8.76,1.65),.2,dark)
# Ribbed bulk tipper: visual proportions taken from real produce trailers.
exec(old[old.index("box('Truck_chassis'"):old.index("# Continuous driven roller")]) if '# Continuous driven roller' in old else None
# Build the truck portion up to the next section without importing old conveyors.
if 'TruckBed' not in bpy.data.objects:
    start=old.index("box('Truck_chassis'");end=old.index('# Conveyor',start) if '# Conveyor' in old[start:] else old.index('for i,x in enumerate',start)
    exec(old[start:end])
# Correct the original bed pivot and augment rubber, wheel hubs and fittings.
bpy.data.objects['TruckBed'].location=(-4.9,0,1.82)
manifest['bodies'].append(dict(name='TruckBed',pos=(-4.9,0,1.82),mass=1200,kinematic=True,shapes=[((-2,0,0),(4,1.68,.12)),((-2,-.88,.46),(4.13,.12,.98)),((-2,.88,.46),(4.13,.12,.98)),((-4.05,0,.46),(.12,1.88,.98))]))
for x in [-10.25,-7.4,-5.8]:
    for y in [-1.03,1.03]:
        for a in np.linspace(0,2*math.pi,40,endpoint=False):
            o=box('Moulded_tire_tread',(x+.509*math.sin(a),y,.52+.509*math.cos(a)),(.059,.282,.015),tire,bevel=.003);o.rotation_euler.y=a
        for a in np.linspace(0,2*math.pi,8,endpoint=False):cyl('Lug_bolt',(x+.13*math.sin(a),y+math.copysign(.177,y),.52+.13*math.cos(a)),.019,.019,steel,axis='Y',verts=12)
for yy in [-.83,.83]:
    pipe('Windshield_wiper',(-10.95,yy*.25,1.76),(-10.96,yy*.7,2.03),.012,tire)
    box('Front_indicator',(-11.24,yy,1.38),(.06,.12,.12),yellow)
text('Plate','FF  126',(-11.245,0,.97),.072,white,rot=(math.pi/2,0,-math.pi/2))
# Low drop and high guards keep the gravity discharge inside the receiving belt.
for yy in [-.86,.86]:static('Receiving_hopper_wall',(-4.25,yy,1.99),(1.55,.065,1.02),steel)
static('Receiving_backstop',(-5.04,0,1.72),(.06,1.82,.32),steel)
def belt(name,a,b,width,z=DECK_Z,vel=(BELT_SPEED,0,0)):
    root=body(name,((a+b)/2,0,z-.065),8,[((0,0,0),(b-a,width,.13))],beltmat,True)
    manifest['belts'].append(dict(name=name,velocity=vel))
    for xx in [a,b]:cyl('Belt_return_drum',(xx,0,z-.11),.11,width+.025,dark,axis='Y')
    box('Belt_return',( (a+b)/2,0,z-.23),(b-a,width,.035),beltmat)
    for xx in np.arange(a,b,.26):box('Belt_emboss',(xx,0,z+.001),(.007,width-.025,.002),rubber,bevel=0)
    return root
belt('ReceivingBelt',-4.96,-1.72,1.70)
for yy in [-1,1]:angled_static('Receiving_centering_guide',(-2.70,yy*.895,1.63),(-1.80,yy*.69,1.63),.025,.26)
# Catch the full roller width before narrowing the third conveyor section.
belt('OutputTransferBelt',4.70,5.30,1.56)
belt('OutputBelt',5.28,7.76,.56)
for i,x in enumerate(np.arange(-1.7105,4.750,ROLL_PITCH)):
    name=f'Roller_{i:03d}';root=empty(name,(float(x),0,DECK_Z-ROLL_RADIUS))
    cyl('Roller_sleeve',(0,0,0),ROLL_RADIUS,1.56,rubber,root,axis='Y',verts=32)
    for yy in [-.82,.82]:cyl('Shaft',(0,yy,0),.005,.12,steel,root,axis='Y',verts=16)
    manifest['rollers'].append(dict(name=name,pos=list(root.location),radius=ROLL_RADIUS,width=1.56))
for a,b,w in [(-4.96,-1.72,.94),(-1.72,4.76,.89),(4.70,5.30,.86),(5.30,7.60,.35)]:
    for yy in [-w,w]:
        static('Conveyor_frame',((a+b)/2,yy,1.31),(b-a,.10,.19),steel)
        for xx in np.arange(a+.15,b,.95):
            box('Adjustable_leg',(xx,yy,.64),(.065,.065,1.28),steel);cyl('Foot_pad',(xx,yy,.04),.085,.05,dark)
    for yy in [-1,1]:
        # The inspection exit has a controlled side opening for the air ejector.
        if b==4.76:
            static('Guide_wash',(-.35,yy*.80,1.74),(2.75,.045,.45),steel)
            angled_static('Singulation_guide',(1.05,yy*.80,1.60),(3.30,yy*.052,1.60),.025,.20)
            static('QC_guide',(3.48,yy*.052,1.60),(.34,.025,.20),steel)
            if yy>0:static('QC_air_wall',(4.15,.052,1.60),(1.1,.025,.20),steel)
        else:static('Conveyor_guard',((a+b)/2,yy*(w-.065),1.69),(b-a,.035,.34),steel)
for xx in [-3.6,.0,5.8]:
    cyl('Gear_motor',(xx,1.06 if xx<4 else .56,1.22),.14,.34,blue,axis='Y')
    for zz in np.arange(1.10,1.34,.035):box('Motor_fin',(xx,1.07 if xx<4 else .56,zz),(.29,.32,.009),steel,bevel=.001)
exec(old[old.index('# Wash tunnel:'):old.index('# Inspection:')])
# Inspection is in the roller section, immediately after the singulator.
for yy in [-.85,.85]:box('Inspection_post',(3.55,yy,2.0),(.075,.075,1.55),green)
box('Inspection_bridge',(3.55,0,2.7),(.45,1.85,.21),green)
box('Optical_light',(3.55,0,2.56),(.30,.8,.035),white)
box('Machine_vision_camera',(3.55,0,2.44),(.16,.15,.14),dark);cyl('Lens',(3.55,0,2.33),.045,.065,glass)
text('QC_sign','03 / QUALITY',(3.55,-.94,2.65),.13,white)
for xx in [3.91,4.03,4.15]:cyl('Pneumatic_nozzle',(xx,.17,1.62),.019,.12,steel,axis='Y')
body('RejectGate',(4.06,-.052,1.60),1,[((0,0,0),(.68,.018,.20))],yellow,True)
# The full-width receiver and funnel contain the inspection exit.
for yy in [-1,1]:angled_static('Output_funnel',(4.50,yy*.78,1.60),(5.30,yy*.26,1.60),.024,.20)
for yy in [-1,1]:
    angled_static('Packing_singulator',(5.3,yy*.26,1.60),(6.6,yy*.052,1.60),.022,.20)
    # Keep the narrow stream contained through the belt lip. An exposed gap
    # after the gate lets a released queue deflect produce past the carton.
    static('Packing_lane',(7.19,yy*.052,1.60),(1.18,.022,.20),steel)
body('FillGate',(7.61,0,1.28),1,[((0,0,0),(.025,.24,.25))],yellow,True)
# Steep, contained reject chute into a distinct red bin.
o=box('Reject_chute',(4.04,-1.15,1.05),(.86,.72,.035),steel);o.rotation_euler.x=math.radians(40)
manifest['static'].append(dict(name='Reject_chute',pos=(4.04,-1.15,1.05),size=(.86,.72,.035),rotate_x=40))
for xx in [3.58,4.50]:static('Reject_chute_side',(xx,-1.2,1.27),(.035,.64,.5),steel)
def fixed_bin(name,pos,size,ma):
    x,y,z=pos;lx,ly,h=size
    static(name+'_bottom',(x,y,z+.04),(lx,ly,.08),ma)
    for v in [-1,1]:
        static(name+'_X',(x+v*lx/2,y,z+h/2),(.04,ly,h),ma)
        static(name+'_Y',(x,y+v*ly/2,z+h/2),(lx,.04,h),ma)
fixed_bin('Discard',(4.04,-1.9,0),(1.05,1.25,.66),red)
text('Discard_label','VISIBLE DAMAGE',(4.04,-2.54,.34),.11,white)
exec((ROOT/'src/pack_cell_geometry.py').read_text())
# Collision-safe initial packing, smaller russets with measured-volume mass.
for i in range(POTATO_COUNT):
    col=i%9;row=(i//9)%7;layer=i//63
    loc=(-8.50+col*.39,(row-3)*.205,1.98+layer*.16)
    name=f'Potato_{i:03d}';root=empty(name,loc)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,radius=1)
    o=bpy.context.object;o.name='Skin';o.parent=root
    scale=(rng.uniform(.12,.146)*POTATO_SCALE,rng.uniform(.085,.104)*POTATO_SCALE,rng.uniform(.082,.098)*POTATO_SCALE)
    seed=rng.random()*10;damaged=i%7==6
    for v in o.data.vertices:
        co=v.co;w=1+.035*math.sin(co.x*6+seed)*math.sin(co.y*7+seed)+.025*math.sin(co.z*9+seed)
        co.x*=scale[0]*w;co.y*=scale[1]*w;co.z*=scale[2]*w
    o.data.materials.append(skin);o.data.materials.append(soil);damaged_faces=0
    for p in o.data.polygons:
        p.use_smooth=True;c=sum((o.data.vertices[j].co for j in p.vertices),Vector())/len(p.vertices)
        if damaged and ((c.z>scale[2]*.42 and c.x>-.018) or (c.y<-scale[1]*.65 and c.x<.025)):
            p.material_index=1;damaged_faces+=1
    manifest['potatoes'].append(dict(name=name,initial=loc,scale=scale,mass=4/3*math.pi*math.prod(scale)*1070,damaged=damaged,defect_fraction=damaged_faces/len(o.data.polygons)))
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1;scene.render.engine='CYCLES';scene.cycles.samples=64
scene.render.resolution_x=1920;scene.render.resolution_y=1080
bpy.ops.object.camera_add(location=(20,-27,17));cam=bpy.context.object;cam.name='BlenderOverview';cam.rotation_euler=(Vector((1,-.4,1))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.lens=39;scene.camera=cam
for name,loc,power,size,color in [('Key',(0,-5,10),5500,9,(1,.91,.8)),('Fill',(-7,5,8),3500,7,(.78,.88,1)),('Packing',(10,-1,8),4500,6,(1,.95,.85))]:
    bpy.ops.object.light_add(type='AREA',location=loc);l=bpy.context.object;l.name=name;l.data.energy=power;l.data.shape='DISK';l.data.size=size;l.data.color=color;l.rotation_euler=(Vector((loc[0],0,1))-l.location).to_track_quat('-Z','Y').to_euler()
scene.world.color=(.2,.2,.2)
if (OUT/'hangar_interior_4k.hdr').exists():
    scene.world.use_nodes=True;nodes=scene.world.node_tree.nodes;env=nodes.new('ShaderNodeTexEnvironment');env.image=bpy.data.images.load(str(OUT/'hangar_interior_4k.hdr'));scene.world.node_tree.links.new(env.outputs['Color'],nodes.get('Background').inputs['Color']);nodes.get('Background').inputs['Strength'].default_value=.8
from guide_geometry import convert_guides
convert_guides(manifest)
from polish_scene import polish
polish()
exec((ROOT/'src/import_asset_geometry.py').read_text())
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'potato_factory.blend'))
bpy.ops.wm.usd_export(filepath=str(OUT/'factory_geometry.usdc'),selected_objects_only=False,export_animation=False,export_materials=True,export_textures=True,relative_paths=True,root_prim_path='/World',use_instancing=False)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2));print('V3_GEOMETRY_COMPLETE',len(manifest['potatoes']),len(manifest['bodies']),flush=True)

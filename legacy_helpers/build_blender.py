"""Create the editable factory artwork in Blender and export its USD geometry."""
import bpy, math, random, json, sys
from pathlib import Path
from mathutils import Vector
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
rng=random.Random(17)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
manifest={'rollers':[], 'potatoes':[], 'static':[], 'version':1}

def mat(name,color,metal=0,rough=.4):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal; p.inputs['Roughness'].default_value=rough
    return m
steel=mat('Brushed_stainless',(.43,.52,.55),.85,.26)
dark=mat('Graphite_powdercoat',(.022,.042,.052),.5,.33)
green=mat('Forest_green_enamel',(.028,.19,.105),.4,.28)
rubber=mat('Food_grade_roller',(.016,.077,.048),.05,.48)
yellow=mat('Safety_saffron',(.94,.55,.045),.35,.29)
red=mat('Reject_red',(.55,.035,.025),.3,.32)
white=mat('Warm_white',(.78,.82,.78),.3,.35)
blue=mat('Pump_blue',(.025,.15,.27),.55,.27)
glass=mat('Cab_glass',(.026,.08,.11),.75,.13)
tire=mat('Tire_rubber',(.012,.016,.018),0,.8)
concrete=mat('Concrete',(.24,.3,.32),.05,.78)
soil=mat('Dark_damage',(.044,.014,.006),0,.88)
eye=mat('Potato_eyes',(.12,.054,.018),0,.8)
skin=mat('Potato_skin',(.55,.30,.105),0,.65)
# A deterministic UV texture survives USD export and gives close-ups real detail.
sz=512; texrng=np.random.default_rng(25)
a=texrng.random((64,64)).astype(np.float32); a=np.repeat(np.repeat(a,8,0),8,1)
for _ in range(14): a=(a+np.roll(a,1,0)+np.roll(a,-1,0)+np.roll(a,1,1)+np.roll(a,-1,1))/5
fine=texrng.random((sz,sz)); freckles=texrng.random((sz,sz))>.988
colors=np.zeros((sz,sz,4),np.float32); colors[:,:,:3]=np.array([.43,.30,.16])[None,None,:]*(.88+a[:,:,None]*.24+fine[:,:,None]*.04)
colors[freckles,:3]*=.65; colors[:,:,3]=1
im=bpy.data.images.new('Russet_mottled_skin',sz,sz); im.pixels.foreach_set(colors.reshape(-1)); im.filepath_raw=str(OUT/'potato_skin.png'); im.file_format='PNG'; im.save()
node=skin.node_tree.nodes.new('ShaderNodeTexImage'); node.image=im
skin.node_tree.links.new(node.outputs['Color'],skin.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])

def empty(name,loc=(0,0,0)):
    o=bpy.data.objects.new(name,None); bpy.context.collection.objects.link(o); o.location=loc; return o

def finish(o,name,material,parent=None,bevel=0):
    o.name=name
    if material: o.data.materials.append(material)
    if parent: o.parent=parent
    if bevel:
        mod=o.modifiers.new('Machined_edges','BEVEL'); mod.width=bevel; mod.segments=3
        bpy.context.view_layer.objects.active=o; bpy.ops.object.modifier_apply(modifier=mod.name)
    return o

def box(name,loc,size,material,parent=None,bevel=.025):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.scale=size
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return finish(o,name,material,parent,bevel)

def cyl(name,loc,r,depth,material,parent=None,axis='Z',verts=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=r,depth=depth,location=loc)
    o=bpy.context.object
    if axis=='Y': o.rotation_euler[0]=math.pi/2
    if axis=='X': o.rotation_euler[1]=math.pi/2
    o=finish(o,name,material,parent,.008)
    for p in o.data.polygons:p.use_smooth=True
    return o

def pipe(name,a,b,r,material,parent=None):
    mid=(Vector(a)+Vector(b))/2; d=Vector(b)-Vector(a)
    o=cyl(name,mid,r,d.length,material,parent); o.rotation_euler=d.to_track_quat('Z','Y').to_euler(); return o

def text(name,body,loc,size,material=white,rot=(math.pi/2,0,0),parent=None):
    c=bpy.data.curves.new(name,'FONT'); c.body=body; c.size=size; c.extrude=.001; c.align_x='CENTER'
    o=bpy.data.objects.new(name,c); bpy.context.collection.objects.link(o); o.location=loc; o.rotation_euler=rot
    if parent:o.parent=parent
    o.data.materials.append(material)
    bpy.context.view_layer.objects.active=o; o.select_set(True); bpy.ops.object.convert(target='MESH'); o.select_set(False)
    return o

def static(name,pos,size,material=steel,bevel=.02):
    box(name,pos,size,material,bevel=bevel); manifest['static'].append({'name':name,'pos':pos,'size':size})

# An open industrial hall keeps every operation visible to the camera.
static('Factory_floor',(-1,0,-.13),(27,14,.25),concrete)
for x in np.arange(-14,13,3):
    box('Floor_joint',(x,0,.001),(.014,14,.005),dark,bevel=0)
for y in [-6,-3,3,6]:box('Floor_joint',(-1,y,.001),(27,.014,.005),dark,bevel=0)
for y in [-2.9,2.9]:box('Safety_lane',(-.5,y,.008),(22,.065,.007),yellow,bevel=0)
for x in [-11,-6,-1,4,9]:
    box('Rear_column',(x,5.6,3.1),(.18,.22,6.2),dark)
    box('Roof_beam',(x,1.4,6.1),(.16,8.6,.22),dark)
    box('Overhead_light',(x,0,5.94),(.1,3,.08),white)
box('Rear_wall',(-1,5.8,1.15),(27,.18,2.3),white)
box('Rear_green_band',(-1,5.69,1.8),(27,.03,.32),green)
text('Factory_brand','FIELD / FLOW',(-1,5.57,2.75),.75,green)
text('Factory_subtitle','POTATO WASHING & QUALITY LINE',(-1,5.56,2.3),.19,dark)

# Truck: cab, chassis, tandem rear axle, a physical tipping bed.
box('Truck_chassis',(-7.4,0,.72),(6.5,1.5,.24),dark)
box('Truck_cab',(-10,0,1.65),(1.8,1.85,2.05),green,bevel=.17)
box('Truck_hood',(-10.98,0,1.27),(.38,1.78,.5),green,bevel=.12)
box('Front_grille',(-11.2,0,1.13),(.06,1.15,.35),dark)
for y in [-.57,.57]:box('Headlamp',(-11.24,y,1.38),(.055,.32,.18),white,bevel=.035)
box('Front_windshield',(-10.915,0,2.03),(.045,1.57,.63),glass,bevel=.04)
for y in [-.934,.934]:
    box('Side_window',(-9.95,y,2.02),(1.36,.035,.65),glass,bevel=.04)
    box('Door_handle',(-9.56,y*1.02,1.51),(.2,.04,.045),steel)
    box('Step',(-9.88,y*1.13,.6),(1.3,.35,.12),steel)
    pipe('Mirror_stalk',(-10.6,y,2.1),(-10.7,y*1.32,2.05),.025,dark)
    box('Mirror',(-10.7,y*1.32,2.05),(.17,.075,.26),dark)
    text('Truck_mark','FIELD / FLOW',(-9.9,y*1.025,1.38),.14,white,rot=(math.pi/2 if y<0 else -math.pi/2,0,0))
for x in [-10.25,-7.4,-5.8]:
    pipe('Axle',(x,-1.05,.52),(x,1.05,.52),.11,dark)
    for y in [-1.03,1.03]:
        cyl('Truck_tire',(x,y,.52),.51,.27,tire,axis='Y',verts=48)
        cyl('Wheel_rim',(x,y*1.14,.52),.28,.03,steel,axis='Y')
        for ang in np.linspace(0,2*math.pi,8,endpoint=False):
            cyl('Wheel_lug',(x+.17*math.cos(ang),y*1.165,.52+.17*math.sin(ang)),.024,.03,dark,axis='Y',verts=8)
bed=empty('TruckBed',(-4.7,0,1.82))
box('Bed_floor',(-2,0,0),(4,1.68,.12),steel,bed)
for y in [-.88,.88]:
    box('Bed_side',(-2,y,.46),(4.13,.12,.98),green,bed)
    for x in [-3.8,-3,-2.2,-1.4,-.6]:box('Bed_rib',(x,y*1.08,.44),(.065,.04,.92),steel,bed)
box('Bed_front',(-4.05,0,.46),(.12,1.88,.98),green,bed)
pipe('Hydraulic_base',(-7.25,0,.85),(-6.8,0,1.64),.085,dark)
pipe('Hydraulic_ram',(-6.8,0,1.64),(-6.55,0,2.4),.05,steel)
for y in [-1.01,1.01]:cyl('Tipper_pivot',(-4.7,y,1.82),.13,.18,steel,axis='Y')

# Contact-driven roller conveyor. Each Roller is an independently driven PhysX body.
start=-4.65; end=6.75; pitch=.16; radius=.077
for i,x in enumerate(np.arange(start+radius,end,pitch)):
    name=f'Roller_{i:03d}'; o=empty(name,(float(x),0,1.43))
    wash=-1.65<x<1.65
    cyl('Roll', (0,0,0),radius,1.45,steel if wash else rubber,o,axis='Y',verts=24)
    cyl('Drive_hub',(0,.7,0),.044,.18,steel,o,axis='Y',verts=16)
    box('Rotation_mark',(0,-.735,0),(.017,.009,.12),yellow,o,bevel=.002)
    manifest['rollers'].append({'name':name,'pos':[float(x),0,1.43],'radius':radius,'width':1.45})
for y in [-.77,.77]:
    static('Conveyor_frame',(.95,y/.77*.85,1.31),(11.8,.14,.28),steel)
    # Front rail opens at the reject station.
    if y<0:
        static('Rail_intake',(-.65,y,1.64),(8.0,.06,.17),steel)
        static('Rail_clean',(5.75,y,1.64),(2,.06,.17),steel)
    else:static('Rail_far',(.95,y,1.64),(11.8,.06,.17),steel)
    static('Intake_upper_guide',(-3.2,y,1.75),(2.9,.065,.48),steel)
for x in [-4.3,-2.5,-.7,1.2,3,4.9,6.5]:
    for y in [-.74,.74]:
        box('Leg',(x,y,.64),(.09,.09,1.25),steel)
        box('Foot',(x,y,.035),(.3,.28,.07),dark)
        pipe('Diagonal_brace',(x,y,.18),(x+.45,y,1.15),.022,steel)
for x in [-3,0,5.7]:
    cyl('Conveyor_motor',(x,1.03,1.21),.18,.4,blue,axis='Y')
    box('Motor_gearbox',(x,.83,1.29),(.29,.22,.36),dark)
    for z in np.arange(1.09,1.36,.045):box('Motor_cooling_fin',(x,1.04,z),(.39,.38,.014),steel,bevel=.003)
# Delivery chute from truck to the rollers.
static('Intake_chute',(-4.63,0,1.63),(.42,1.7,.08),steel)
for y in [-.89,.89]:static('Intake_cheek',(-4.3,y,1.82),(1,.08,.5),steel)

# Wash tunnel: open portals, perforated drainage tray, nozzles and pipework.
for x in [-1.5,0,1.5]:
    for y in [-.98,.98]:box('Wash_post',(x,y,2.0),(.07,.07,1.72),steel)
    box('Wash_crossbar',(x,0,2.87),(.085,2.05,.09),steel)
    pipe('Spray_manifold',(x,-.62,2.57),(x,.62,2.57),.034,steel)
    for y in [-.4,0,.4]:
        cyl('Spray_nozzle',(x,y,2.5),.047,.12,blue)
        cyl('Nozzle_tip',(x,y,2.431),.026,.025,steel)
pipe('Water_supply',(-1.5,.96,2.64),(1.5,.96,2.64),.065,blue)
for x in [-1.5,0,1.5]:pipe('Manifold_feed',(x,.96,2.64),(x,.55,2.57),.028,steel)
for y in [-1.04,1.04]:static('Wash_splash_sill',(0,y,1.21),(3.6,.09,.52),steel)
static('Drain_pan',(0,0,.85),(3.6,2.14,.1),steel)
pipe('Drain_return',(0,1.08,.82),(0,2.25,.5),.09,steel)
cyl('Water_filter',(0,2.22,.7),.33,1.35,steel)
cyl('Pump_body',(-.8,2.05,.3),.24,.68,blue,axis='X')
box('Pump_plinth',(-.7,2.1,.08),(1.55,1,.16),dark)
pipe('Riser',(0,2.22,1.36),(0,2.22,2.64),.065,blue)
pipe('Top_return',(0,2.22,2.64),(0,.96,2.64),.065,blue)
for y in [-.96,.96]:box('Wash_upper_trim',(0,y,2.82),(3.5,.13,.27),green)
text('Wash_label','02 / WASH',(0,-1.04,2.77),.17,white)

# Inspection: light bar, camera, local operator panel and physical reject paddle.
for y in [-.93,.93]:box('Inspection_post',(3.35,y,2.0),(.1,.1,1.56),green)
box('Inspection_bridge',(3.35,0,2.76),(.48,2.0,.22),green)
box('Optical_light',(3.35,0,2.60),(.24,1.2,.045),white)
box('Quality_camera',(3.38,0,2.45),(.15,.17,.14),dark)
cyl('Quality_lens',(3.38,0,2.35),.05,.07,glass)
text('Inspection_label','03 / INSPECT',(3.35,-1.065,2.70),.135,white)
box('Reject_actuator',(4.3,1.02,1.76),(.45,.58,.3),blue)
for x in [4.13,4.3,4.47]:cyl('Air_jet_nozzle',(x,.64,1.71),.023,.12,steel,axis='Y')
pad=empty('RejectPaddle',(4.3,.68,1.73))
box('Paddle_face',(0,0,0),(.55,.065,.35),yellow,pad)
pipe('Paddle_rod',(0,0,0),(0,.8,0),.04,steel,pad)
box('Control_console',(2.5,-1.55,1.1),(.75,.28,.56),dark)
box('Console_screen',(2.5,-1.708,1.19),(.55,.013,.25),glass)
text('Console_readout','SORT / AUTO',(2.5,-1.72,1.2),.055,white)
for x,ma in [(2.29,red),(2.50,green),(2.71,yellow)]:cyl('Control_button',(x,-1.72,.96),.035,.025,ma,axis='Y')
box('Console_stand',(2.5,-1.55,.48),(.12,.12,.96),steel)
for z,ma in [(2.4,green),(2.54,yellow),(2.68,red)]:cyl('Stack_light',(4.63,1.01,z),.06,.12,ma)
pipe('Stack_light_pole',(4.63,1.01,1.8),(4.63,1.01,2.35),.022,steel)

def bin(name,pos,size,material):
    x,y,z=pos; sx,sy,sz=size
    static(name+'_floor',(x,y,.13),(sx,sy,.16),material)
    for a in [-1,1]:
        static(name+'_end',(x+a*sx/2,y,sz/2),(.07,sy,sz),material)
        static(name+'_side',(x,y+a*sy/2,sz/2),(sx,.07,sz),material)
        box(name+'_rim',(x,y+a*sy/2,sz+.025),(sx+.13,.12,.09),steel)
    for px in [x-sx*.35,x+sx*.35]:
        for py in [y-sy*.35,y+sy*.35]:box(name+'_foot',(px,py,.06),(.2,.2,.12),dark)
bin('CleanBin',(7.95,0,0),(2.65,2.5,1.04),green)
text('Clean_bin_label','CLEAN / ACCEPTED',(7.95,-1.30,.65),.20,white)
text('Clean_bin_subtitle','WASHED POTATOES',(7.95,-1.30,.36),.10,white)
bin('DiscardBin',(4.3,-2.02,0),(1.4,1.45,.79),red)
text('Reject_bin_label','REJECT',(4.3,-2.785,.49),.18,white)
text('Reject_bin_subtitle','VISIBLE DAMAGE',(4.3,-2.785,.28),.075,white)
static('Reject_chute',(4.3,-1.03,1.18),(.76,.57,.065),steel)
static('QC_guide_lip',(4.05,-.77,1.60),(1.4,.06,.14),steel)
bpy.data.objects['Reject_chute'].rotation_euler.x=math.radians(40);manifest['static'][-2]['rotate_x']=40
for x in [3.92,4.68]:static('Reject_chute_cheek',(x,-1.07,1.35),(.045,.64,.32),steel)

# Potatoes are mesh-based rigid bodies. Damaged surface patches stay attached.
for i in range(144):
    col=i%12; row=(i//12)%4; layer=i//48
    loc=(-8.38+col*.295,-.56+row*.36,2.06+layer*.22)
    name=f'Potato_{i:03d}'; root=empty(name,loc)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=1)
    o=bpy.context.object; o.name='Skin'; o.parent=root
    scale=(rng.uniform(.12,.146),rng.uniform(.085,.104),rng.uniform(.082,.098))
    seed=rng.uniform(0,10); damaged=(i%7==2 or i%19==4)
    for v in o.data.vertices:
        co=v.co; wobble=1+.045*math.sin(co.x*7+seed)*math.sin(co.y*6+seed)+.035*math.sin(co.z*9)
        co.x*=scale[0]*wobble; co.y*=scale[1]*wobble; co.z*=scale[2]*wobble
    o.data.materials.append(skin); o.data.materials.append(soil); o.data.materials.append(eye)
    damaged_faces=0
    for p in o.data.polygons:
        p.use_smooth=True
        center=sum((o.data.vertices[j].co for j in p.vertices),Vector())/len(p.vertices)
        if damaged and ((center.z>scale[2]*.44 and center.x>-.03) or (center.y<-.055 and center.x<.04)):
            p.material_index=1; damaged_faces+=1
        elif rng.random()<.011:p.material_index=2
    manifest['potatoes'].append({'name':name,'initial':loc,'scale':scale,'damaged':damaged,'defect_fraction':damaged_faces/len(o.data.polygons)})

# Simple contextual storage: pallets and sacks away from the active line.
for x in [-5,-3,4,6]:
    for y in [3.7]:
        box('Pallet',(x,y,.14),(1.4,1.15,.2),dark)
        for sx in [-.5,0,.5]:box('Pallet_plank',(x+sx,y,.26),(.42,1.2,.06),steel)
        box('Storage_crate',(x,y,.6),(1.2,1,.65),green)
        for z in [.4,.55,.7,.85]:box('Crate_rib',(x,y-.51,z),(1.2,.04,.024),dark)

scene=bpy.context.scene; scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
scene.render.engine='CYCLES'; scene.cycles.samples=32; scene.render.resolution_x=1280; scene.render.resolution_y=720
bpy.ops.object.camera_add(location=(14,-20,13)); cam=bpy.context.object; cam.name='BlenderOverview'
cam.rotation_euler=(Vector((-1,0,1.2))-cam.location).to_track_quat('-Z','Y').to_euler(); cam.data.lens=37; scene.camera=cam
for name,loc,power,size,color in [('Key',(0,-4,9),3500,8,(1,.86,.7)),('Fill',(-6,3,7),2500,7,(.7,.85,1)),('Rim',(8,3,7),2800,5,(1,1,1))]:
    bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.name=name; l.data.energy=power; l.data.shape='DISK'; l.data.size=size; l.data.color=color
    l.rotation_euler=(Vector((0,0,1))-l.location).to_track_quat('-Z','Y').to_euler()
scene.world.color=(.25,.25,.25)
for a in bpy.context.screen.areas:
    if a.type=='VIEW_3D':a.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'potato_factory.blend'))
bpy.ops.wm.usd_export(filepath=str(OUT/'factory_geometry.usdc'),selected_objects_only=False,export_animation=False,export_materials=True,export_textures=True,relative_paths=True,root_prim_path='/World',use_instancing=False)
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('FACTORY BUILT',len(manifest['rollers']),'rollers',len(manifest['potatoes']),'potatoes',flush=True)

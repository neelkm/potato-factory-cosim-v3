"""Keep a full editable Blender variant and polish the additive visual layer."""
from pathlib import Path
import bpy,math
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
bpy.ops.wm.open_mainfile(filepath=str(OUT/'potato_factory.blend'))
before=set(bpy.data.objects)
bpy.ops.wm.usd_import(filepath=str(OUT/'scrub_visuals.usda'))
added=set(bpy.data.objects)-before
for obj in list(added):
    if obj.name=='World' and obj.type=='EMPTY':
        for child in list(obj.children):
            matrix=child.matrix_world.copy();child.parent=None;child.matrix_world=matrix
        added.remove(obj);bpy.data.objects.remove(obj,do_unlink=True)
for obj in added:
    if obj.type=='MESH' and any(k in obj.name for k in ['Skirt','Rim','Leg','DriveCover','ControlCabinet','Bearing']):
        bevel=obj.modifiers.new('Folded stainless edges','BEVEL');bevel.width=.003;bevel.segments=3
        normal=obj.modifiers.new('Weighted sheet normals','WEIGHTED_NORMAL')
labelmat=bpy.data.materials.new('Scrub_label_ink');labelmat.diffuse_color=(.90,.94,.91,1);labelmat.use_nodes=True
labelmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.90,.94,.91,1)
for name,words,pos,size in [
    ('ScrubStationName','POST-WASH / BRUSH POLISH',(2.34,-.923,1.27),.059),
    ('ScrubStationSpec','6 SOFT BRUSHES  /  CONTROLLED FEED',(2.34,-.924,1.17),.034),
    ('ScrubDrainLabel','SOIL COLLECTION TRAY',(2.34,-.924,1.08),.031)]:
    curve=bpy.data.curves.new(name,'FONT');curve.body=words;curve.align_x='CENTER';curve.size=size;curve.extrude=.0004
    obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj);obj.location=pos;obj.rotation_euler=(math.pi/2,0,0);curve.materials.append(labelmat);added.add(obj)
bpy.ops.object.select_all(action='DESELECT')
for obj in added:obj.select_set(True)
bpy.ops.wm.usd_export(filepath=str(OUT/'scrub_visuals_polished.usdc'),selected_objects_only=True,export_animation=False,export_materials=True,export_textures=False,relative_paths=True,root_prim_path='/World',use_instancing=False)
bpy.ops.object.select_all(action='DESELECT')
for obj in added:
    if obj.type=='FONT':obj.select_set(True)
bpy.ops.wm.usd_export(filepath=str(OUT/'scrub_labels.usdc'),selected_objects_only=True,export_animation=False,export_materials=True,export_textures=False,relative_paths=True,root_prim_path='/World',use_instancing=False)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'potato_factory_scrub.blend'))
print('SCRUB_BLENDER_READY',len(added),flush=True)

"""Photographic surface materials and unobstructed station views."""
import bpy,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from config import OUT

def presentation_background():
    """Keep photographic illumination while using a plain camera backdrop."""
    world=bpy.context.scene.world;world.use_nodes=True;nodes=world.node_tree.nodes;links=world.node_tree.links
    if nodes.get('Camera_Background'):return
    solid=nodes.new('ShaderNodeBackground');solid.name='Camera_Background';solid.inputs['Color'].default_value=(.18,.22,.22,1)
    rays=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader')
    links.new(rays.outputs['Is Camera Ray'],mix.inputs[0]);links.new(nodes.get('Background').outputs[0],mix.inputs[1]);links.new(solid.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],nodes.get('World Output').inputs['Surface'])

def polish():
    floor=bpy.data.objects['Factory_floor'];floor.dimensions=(100,100,.25);bpy.context.view_layer.update()
    bpy.data.objects['Rear_wall'].dimensions=(80,.2,6.8);bpy.data.objects['Rear_wall'].location.z=3.4
    bpy.data.objects['Rear_wainscot'].dimensions.x=80
    concrete=bpy.data.materials['Concrete'];nodes=concrete.node_tree.nodes;links=concrete.node_tree.links;bs=nodes.get('Principled BSDF')
    for name,slot in [('diff','Base Color'),('rough','Roughness')]:
        tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(OUT/'textures'/f'concrete_floor_02_{name}_2k.jpg'),check_existing=True)
        if name!='diff':tex.image.colorspace_settings.name='Non-Color'
        links.new(tex.outputs['Color'],bs.inputs[slot])
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(OUT/'textures/concrete_floor_02_nor_gl_2k.jpg'),check_existing=True);tex.image.colorspace_settings.name='Non-Color';normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=.25;links.new(tex.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],bs.inputs['Normal'])
    uv=floor.data.uv_layers.active or floor.data.uv_layers.new()
    for loop in floor.data.loops:
        co=floor.matrix_world@floor.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=(co.x/2,co.y/2)
    for o in bpy.data.objects:
        if o.name.startswith(('Wash_upper_trim','Wash_label','Wash_crossbar')):o.location.z+=.38
        if o.name.startswith('Wash_post'):o.dimensions.z+=.38;o.location.z+=.19
    bpy.data.objects['Shipping_sign'].location.y=-7.95
    markings=[o for o in bpy.data.objects if o.name.startswith('Pallet_bay')]
    for o,yy in zip(markings,[-8.05,-5.75]):o.location.y=yy
    # Add fine, regular pressed ribs to the bulk tipper, as on the reference.
    bed=bpy.data.objects['TruckBed'];steel=bpy.data.materials['Brushed_stainless']
    for yy in [-.945,.945]:
        for i in range(18):
            x=-3.87+i*.22
            bpy.ops.mesh.primitive_cube_add(size=1);o=bpy.context.object;o.name='Tipper_pressed_rib';o.parent=bed;o.location=(x,yy,.46);o.dimensions=(.018,.014,.82);o.data.materials.append(steel)
            bevel=o.modifiers.new('Pressed edge','BEVEL');bevel.width=.003;bevel.segments=2
    for matname in ['Forest_green_enamel','Robot_enamel']:
        n=bpy.data.materials[matname].node_tree.nodes.get('Principled BSDF');n.inputs['Roughness'].default_value=.34
    presentation_background()

if __name__=='__main__':
    bpy.ops.wm.open_mainfile(filepath=str(OUT/'potato_factory.blend'));polish()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'potato_factory.blend'))
    bpy.ops.wm.usd_export(filepath=str(OUT/'factory_geometry.usdc'),selected_objects_only=False,export_animation=False,export_materials=True,export_textures=True,relative_paths=True,root_prim_path='/World',use_instancing=False)
    print('SURFACE_POLISH_COMPLETE',flush=True)

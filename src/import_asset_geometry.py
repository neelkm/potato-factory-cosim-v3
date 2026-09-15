"""Import robot/forklift artwork into the editable Blender factory."""
# Executed in build_scene.py's Blender namespace after the factory is authored.
before=set(bpy.data.objects)
bpy.ops.wm.usd_import(filepath=str(OUT/'franka_cell.usda'),import_cameras=False,import_lights=False)
created=set(bpy.data.objects)-before
for obj in list(created):
    if obj.parent is None and obj.type=='EMPTY' and obj.name.startswith('World'):
        for child in list(obj.children):
            world=child.matrix_world.copy();child.parent=None;child.matrix_world=world
        bpy.data.objects.remove(obj,do_unlink=True)
# Robot collision proxies stay in the physics partition; hide them in artwork.
for obj in list(created):
    try:
        if obj.name.lower().startswith('collisions'):
            obj.hide_render=True
            for child in obj.children_recursive:child.hide_render=True
    except ReferenceError:pass
before=set(bpy.data.objects)
bpy.ops.wm.usd_import(filepath=str(ROOT/'assets/forklift_blue_c01/presentation.usdc'),import_cameras=False,import_lights=False)
created=set(bpy.data.objects)-before
for name in ['Forklift','Forks']:
    imported=next(o for o in created if o.name.startswith(name) and o.name!=name and o.type=='EMPTY')
    target=bpy.data.objects[name]
    imported.parent=target;imported.location=(0,0,0);imported.rotation_euler=(0,0,math.pi)
    # Use a stable child name so the simulation root remains /World/Forklift.
    imported.name=name+'_SimReady'
for obj in list(created):
    if obj.parent is None and obj.type=='EMPTY' and obj.name.startswith('Assets'):bpy.data.objects.remove(obj,do_unlink=True)
def udim_image(stem):
    directory=ROOT/'assets/forklift_blue_c01/Textures';first=directory/(stem+'.1001.png')
    if not first.exists():return None
    im=bpy.data.images.load(str(first),check_existing=True);im.source='TILED';im.filepath=str(directory/(stem+'.<UDIM>.png'))
    existing={t.number for t in im.tiles}
    for tile in range(1002,1009):
        if (directory/(stem+f'.{tile}.png')).exists() and tile not in existing:im.tiles.new(tile)
    return im
for ma in bpy.data.materials:
    if 'forklift' not in ma.name.lower():continue
    ma.use_nodes=True;nodes=ma.node_tree.nodes;links=ma.node_tree.links;bs=next((n for n in nodes if n.type=='BSDF_PRINCIPLED'),None)
    if bs is None:continue
    decals='decal' in ma.name.lower();prefix='T_Forklift_C01_Decals_' if decals else 'T_Forklift_C01_'
    albedo=udim_image(prefix+'Albedo')
    if albedo:
        tex=nodes.new('ShaderNodeTexImage');tex.image=albedo;links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        if decals:links.new(tex.outputs['Alpha'],bs.inputs['Alpha'])
    rough=udim_image('T_Forklift_C01_Rough')
    if rough:
        rough.colorspace_settings.name='Non-Color';tex=nodes.new('ShaderNodeTexImage');tex.image=rough;links.new(tex.outputs['Color'],bs.inputs['Roughness'])
    normal=udim_image(prefix+'Normal')
    if normal:
        normal.colorspace_settings.name='Non-Color';tex=nodes.new('ShaderNodeTexImage');tex.image=normal;n=nodes.new('ShaderNodeNormalMap');n.inputs['Strength'].default_value=.6;links.new(tex.outputs['Color'],n.inputs['Color']);links.new(n.outputs['Normal'],bs.inputs['Normal'])
    bs.inputs['Metallic'].default_value=.65 if 'metal' in ma.name.lower() else 0.
    if 'blue' in ma.name.lower():
        for link in list(bs.inputs['Base Color'].links):links.remove(link)
        bs.inputs['Base Color'].default_value=(.00913365,.005605195,.5394796,1)
    if 'glass' in ma.name.lower():bs.inputs['Transmission Weight'].default_value=.85;bs.inputs['IOR'].default_value=1.45;bs.inputs['Roughness'].default_value=.10
print('FRANKA_AND_SIMREADY_ARTWORK_IMPORTED',flush=True)

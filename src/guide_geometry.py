import bpy,math
from mathutils import Vector
NAMES={'Singulation_guide','QC_guide','QC_air_wall','Output_funnel','Packing_singulator','Packing_lane'}
def convert_guides(manifest):
    moving=[o for o in manifest['static'] if o['name'] in NAMES and o['pos'][1]>0]
    for spec in moving:
        obj=next(o for o in bpy.data.objects if o.name.split('.')[0]==spec['name'] and (o.location-Vector(spec['pos'])).length<.001)
        root=bpy.data.objects.new('Vibrating_'+spec['name'],None);bpy.context.collection.objects.link(root);root.location=obj.location.copy();root.rotation_euler=obj.rotation_euler.copy();obj.parent=root;obj.location=(0,0,0);obj.rotation_euler=(0,0,0)
        manifest['bodies'].append(dict(name=root.name,pos=spec['pos'],mass=3,kinematic=True,vibrating=True,rotate_z=spec.get('rotate_z',0),shapes=[((0,0,0),spec['size'])]))
    manifest['static']=[o for o in manifest['static'] if o not in moving]

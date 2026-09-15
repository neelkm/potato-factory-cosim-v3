"""Stamp the editable release scene without changing its qualified geometry."""
import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
bpy.context.preferences.filepaths.save_version=0
scene=bpy.context.scene
scene['factory_release']='3.0.0'
scene['simulation_topology']='../configs/factory_topology.usda'
scene['physics']='ovphysx production line; ovnewton Franka packing; ovfmi controller'
scene['scheduler']='NVIDIA cosim WavefrontScheduler'
scene['contact_policy']='Complete-assembly ownership transaction at a paused clock barrier'
text=bpy.data.texts.get('READ ME - FIELD FLOW 3.0') or bpy.data.texts.new('READ ME - FIELD FLOW 3.0')
text.clear();text.write('FIELD / FLOW 3.0\n\nEditable Blender geometry, materials, lights and cameras.\nRun the native co-simulation through Launch Factory.cmd or Run simulation.cmd.\nUSD source: output/factory.usda. Graph: configs/factory_topology.usda.\nPhysics is computed by PhysX and Newton with FMI controls, then recorded in USD value clips.\nThe Blender scene does not substitute Blender rigid-body physics for these engines.\n')
for image in bpy.data.images:
    if image.source=='FILE' and image.packed_file:
        image.filepath='//textures/'+Path(image.filepath).name
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'output/potato_factory.blend'))
report=dict(passed=True,release=scene['factory_release'],objects=len(bpy.data.objects),images=len(bpy.data.images),packed_images=sum(bool(i.packed_file) for i in bpy.data.images))
(ROOT/'output/blender_validation.json').write_text(json.dumps(report,indent=2));print('BLENDER_V3_READY',report)

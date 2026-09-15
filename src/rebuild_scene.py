"""Rebuild editable assets, FMU and physics stages from the local sources."""
import subprocess,sys
from config import ROOT
def main():
    for script in ['prepare_franka.py','plan_cell.py','author_robot_cell.py','prepare_forklift_visual.py','build_fmu.py']:
        subprocess.run([sys.executable,str(ROOT/'src'/script)],cwd=ROOT,check=True)
    subprocess.run([str(ROOT/'tools/blender-4.5.13-windows-x64/blender.exe'),'-b','--python-exit-code','1','--python',str(ROOT/'src/build_scene.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'src/assemble_stage.py')],cwd=ROOT,check=True)
    subprocess.run([sys.executable,str(ROOT/'src/author_topology.py')],cwd=ROOT,check=True)
    subprocess.run([str(ROOT/'tools/blender-4.5.13-windows-x64/blender.exe'),'-b',str(ROOT/'output/potato_factory.blend'),'--python-exit-code','1','--python',str(ROOT/'scripts/stamp_blender.py')],cwd=ROOT,check=True)
    print('Editable Blender project and co-simulation stages rebuilt.')
if __name__=='__main__':main()

"""Fetch the public PhysX header dependency closure for the fluid inlet bridge."""
import re,urllib.request,sys
from pathlib import Path
root=Path(__file__).resolve().parent/'physx_include'
todo=sys.argv[1:] or ['PxParticleBuffer.h'];seen=set()
while todo:
    name=todo.pop()
    if '/switch/' in name or '/unix/' in name:continue
    if name in seen:continue
    seen.add(name);p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
    content=p.read_bytes() if p.exists() else urllib.request.urlopen('https://raw.githubusercontent.com/NVIDIA-Omniverse/PhysX/main/physx/include/'+name).read()
    p.write_bytes(content)
    for dep in re.findall(r'#\s*include\s*"([^"]+)"',content.decode()):
        if not dep.startswith(('foundation/','common/','extensions/','geometry/','task/','gpu/','cooking/','pvd/','cudamanager/','Px')):dep=(Path(name).parent/dep).as_posix()
        if dep not in seen:todo.append(dep)
    print(name,flush=True)

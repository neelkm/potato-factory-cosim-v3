"""Record a captioned 26-second demonstration of the actual Tk debug workspace.

The UI is driven deterministically; every movie frame is captured from its
window, including the live controls, inspector and captions. No desktop or
other applications are recorded.
"""
import ctypes,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import tkinter as tk
import numpy as np
import imageio.v2 as imageio
from PIL import ImageGrab,Image
from physics_debug_ui import PhysicsDebugWindow
from physics_debug import ROOT

def main():
    root=tk.Tk();ui=PhysicsDebugWindow(root,standalone=True);root.geometry('1440x1040+20+20');root.update()
    ui.caption.configure(font=('Segoe UI',14,'bold'),fg='#ffcc75',height=2)
    hwnd=ctypes.windll.user32.GetAncestor(root.winfo_id(),2)
    base=ROOT/'output/physics_debug';fps=24;frames=26*fps
    if '--preview' in sys.argv:
        ui.state.tick=13*240;ui.state.closeup=True;ui.caption.configure(text='Contact markers show the native PhysX response as the forks lift the pallet.');ui.refresh();root.update()
        ImageGrab.grab(window=hwnd).save(base/'ui_preview.png');ui.close();return
    movie=base/'physics_debug_demo.mp4'
    writer=imageio.get_writer(movie,fps=fps,codec='libx264',quality=None,macro_block_size=1,
                             ffmpeg_params=['-crf','17','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart'])
    chapters=[];phase_before=None
    try:
        for frame in range(frames):
            t=frame/fps;state=ui.state
            if t<4:
                phase=0;mode='Forklift alignment';state.closeup=False;state.tick=round((7+t*.6)*240)
                caption='1 / ALIGNMENT   •   The measured pallet position requires a 52.51 mm side shift.'
            elif t<8:
                phase=1;mode='Forklift alignment';state.closeup=True;state.tick=ui.data.first_contact+round((t-4)*.20*240)
                caption='Zoom into insertion. Gold dots and arrows show native fork–pallet contacts and their normals.'
            elif t<12:
                phase=2;mode='Forklift alignment';state.closeup=True;state.tick=round((12+(t-8)*.6)*240)
                caption='Watch the lift: contact impulses rise as the forks support the loaded pallet. The graph retains every step.'
            elif t<17:
                phase=3;mode='Engine handoff';state.closeup=True;state.tick=0
                caption='2 / HANDOFF   •   139 bodies return from Newton. Magenta is the frozen export; PhysX readback verifies the import.'
            elif t<22:
                phase=4;mode='Engine handoff';state.closeup=True;state.tick=1+round((t-17)*.04*240)
                caption='Advance through the first PhysX steps. Matching transfer states can still produce restart contact impulses.'
            else:
                phase=5;mode='Engine handoff';state.closeup=True;state.tick=round((.2+(t-22)*.10)*240)
                caption='Select a body to inspect its motion, mass and centre of mass. This is a recorded PhysX reproduction.'
            state.mode=mode;ui.mode.set(mode);state.selected='/World/Box_0' if phase==5 else '/World/Pallet';ui.object.set(state.selected)
            state.azimuth=.65+(t-22)*.08 if phase==5 else .65
            ui.caption.configure(text=caption);ui.refresh();root.update()
            image=ImageGrab.grab(window=hwnd).convert('RGB')
            # Crop only a possible odd last pixel for H.264 chroma alignment.
            image=image.crop((0,0,image.width//2*2,image.height//2*2))
            writer.append_data(np.asarray(image))
            if phase!=phase_before:
                chapters.append(dict(time=t,caption=caption));phase_before=phase
            if frame in [72,144,240,348,456,576]:image.save(base/f'demo_{frame:04d}.png')
            if frame%120==0:print('DEBUG_VIDEO',frame,'/',frames,flush=True)
        result=dict(seconds=26,fps=fps,frames=frames,width=image.width,height=image.height,
                    capture='Actual Tk application window, automatically driven controls; no desktop capture.',chapters=chapters)
        (base/'video_manifest.json').write_text(json.dumps(result,indent=2))
    finally:
        writer.close();ui.close()
    print('DEBUG_VIDEO_COMPLETE',movie,flush=True)

if __name__=='__main__':main()

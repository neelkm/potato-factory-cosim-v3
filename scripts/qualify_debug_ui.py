"""Exercise real debug controls and ensure controls stay inside the window."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import tkinter as tk
from physics_debug_ui import PhysicsDebugWindow
from physics_debug import ROOT

def main():
    import faulthandler
    faulthandler.dump_traceback_later(30,exit=True)
    root=tk.Tk();ui=PhysicsDebugWindow(root,standalone=True);root.update();checks=[]
    print('UI created',flush=True)
    try:
        for size in ['1180x850','1320x900','1440x1040']:
            root.geometry(size);root.update();ui.refresh();root.update()
            for widget in [ui.slider,ui.caption,ui.object_control,ui.mode_control,ui.play]:
                assert widget.winfo_ismapped()
                y=widget.winfo_rooty()-root.winfo_rooty()
                x=widget.winfo_rootx()-root.winfo_rootx()
                assert 0<=y and y+widget.winfo_height()<=root.winfo_height(),(size,widget,y)
                assert 0<=x and x+widget.winfo_width()<=root.winfo_width(),(size,widget,x)
            checks.append('All main controls visible at '+size)
            print('UI size',size,flush=True)
        ui.set_mode('Engine handoff');ui.step(1);assert ui.state.tick==1
        assert len(ui.data.contacts(1))>0
        ui.set_mode('Forklift alignment');assert ui.state.tick==ui.data.first_contact
        ui.slider.set(3120);root.update();assert ui.state.tick==3120
        print('UI slider',flush=True)
        ui.select('/World/Box_0');assert ui.state.selected=='/World/Box_0'
        for field in ui.toggles:
            before=getattr(ui.state,field);ui.option(field,not before);assert getattr(ui.state,field)!=before;ui.option(field,before)
        ui.details();ui.contact_details();ui.scope();root.update()
        print('UI dialogs',flush=True)
        for child in root.winfo_children():
            if isinstance(child,tk.Toplevel):child.destroy()
        ui.seek(0);ui.toggle()
        print('UI playback',flush=True)
        until=time.monotonic()+.8
        while time.monotonic()<until:root.update();time.sleep(.01)
        ui.toggle();assert ui.state.tick>0
        checks+=['mode switching','exact native step','contact data at first step','timeline seek','body selection','overlay toggles','body/contact/provenance dialogs','playback']
        (ROOT/'output/physics_debug/ui_validation.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2))
        print('DEBUG_UI_PASS',checks,flush=True)
    finally:faulthandler.cancel_dump_traceback_later();ui.close()

if __name__=='__main__':main()

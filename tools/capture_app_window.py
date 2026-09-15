import ctypes,sys
from PIL import ImageGrab
from pathlib import Path
pid=int(sys.argv[1]);user=ctypes.windll.user32
@ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
def each(hwnd,unused):
    got=ctypes.c_ulong();user.GetWindowThreadProcessId(hwnd,ctypes.byref(got))
    if got.value==pid and user.IsWindowVisible(hwnd):
        title=ctypes.create_unicode_buffer(256);user.GetWindowTextW(hwnd,title,256)
        print('OWN_APP_WINDOW',int(hwnd),title.value,flush=True)
        if 'FIELD / FLOW' in title.value:
            ImageGrab.grab(window=int(hwnd)).save(Path(__file__).resolve().parents[1]/'output/app_live_check.png')
    return True
user.EnumWindows(each,0)

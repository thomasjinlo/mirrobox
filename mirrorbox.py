"""mirrorbox.py

Simple input mirroring helper for Windows with extended diagnostics.

NOTES & WARNINGS
- Captures global mouse/keyboard events and broadcasts them to other windows.
- Use only on machines/windows you own or have explicit consent to control.
- Games or UAC prompts may block synthetic input.

Dependencies: `pynput`, `pywin32`, `psutil` (install with `pip install pynput pywin32 psutil`).
"""

from pynput import mouse, keyboard
import ctypes
import win32gui
import win32gui_struct
import win32api
import win32con
import win32process
import sys
import time
import argparse
import re
import threading
from collections import deque
import psutil

# Thread-local storage for recursion prevention
_injection_lock = threading.local()

# Input queue
_input_queue = deque()
_queue_lock = threading.Lock()

# Debounce delays
_last_input_time = time.time()
_capture_debounce_delay = 1  # 500ms silence

# CONFIGURATION
SOURCE_TITLE = r"rg1"
TARGET_TITLES = [
    r"rg2",
    r"rg3",
    r"4 - tl",
    r"ms",
    r"rl",
    r"sp",
]
TARGET_PATTERNS = []
SOURCE_RE = None

def compile_target_patterns():
    global TARGET_PATTERNS
    TARGET_PATTERNS = []
    for p in TARGET_TITLES:
        try:
            TARGET_PATTERNS.append(re.compile(p, re.IGNORECASE))
        except re.error:
            print(f"Invalid target regex pattern: {p}")

def compile_source_pattern():
    global SOURCE_RE
    try:
        SOURCE_RE = re.compile(SOURCE_TITLE, re.IGNORECASE)
    except re.error:
        print(f"Invalid source regex pattern: {SOURCE_TITLE}")
        SOURCE_RE = None

# ===========================================================
# Window discovery
# ===========================================================
target_windows = []

def enum_win(hwnd, ctx):
    try:
        if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd):
            return
    except Exception:
        return
    for pat in TARGET_PATTERNS:
        try:
            if pat.search(win32gui.GetWindowText(hwnd)):
                target_windows.append(hwnd)
                return
        except Exception:
            continue

def refresh_target_windows():
    target_windows.clear()
    win32gui.EnumWindows(enum_win, None)

def list_all_windows():
    results = []
    def _collect(hwnd, ctx):
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and title.strip():
                    results.append((hwnd, title))
        except Exception:
            pass
    win32gui.EnumWindows(_collect, None)
    return results

# ===========================================================
# Input handling
# ===========================================================
SPECIAL_KEY_MAP = {
    keyboard.Key.enter: win32con.VK_RETURN,
    keyboard.Key.space: win32con.VK_SPACE,
    keyboard.Key.backspace: win32con.VK_BACK,
    keyboard.Key.tab: win32con.VK_TAB,
    keyboard.Key.esc: win32con.VK_ESCAPE,
    keyboard.Key.left: win32con.VK_LEFT,
    keyboard.Key.up: win32con.VK_UP,
    keyboard.Key.right: win32con.VK_RIGHT,
    keyboard.Key.down: win32con.VK_DOWN,
    keyboard.Key.shift: win32con.VK_SHIFT,
    keyboard.Key.shift_r: win32con.VK_RSHIFT if hasattr(win32con,'VK_RSHIFT') else win32con.VK_SHIFT,
    keyboard.Key.ctrl: win32con.VK_CONTROL,
    keyboard.Key.ctrl_l: win32con.VK_LCONTROL if hasattr(win32con,'VK_LCONTROL') else win32con.VK_CONTROL,
    keyboard.Key.alt: win32con.VK_MENU,
}

def vk_from_key(key):
    try:
        if hasattr(key, 'char') and key.char:
            return win32api.VkKeyScan(key.char) & 0xFF
    except Exception:
        pass
    return SPECIAL_KEY_MAP.get(key)

def is_source_active():
    fg = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(fg) or ""
    if SOURCE_RE is None:
        return SOURCE_TITLE.lower() in title.lower()
    try:
        return bool(SOURCE_RE.search(title))
    except Exception:
        return False

def send_mouse_event(x, y, event_flag):
    for hwnd in list(target_windows):
        try:
            client_pt = win32gui.ScreenToClient(hwnd, (int(x), int(y)))
            lparam = win32api.MAKELONG(client_pt[0]&0xFFFF, client_pt[1]&0xFFFF)
            win32gui.PostMessage(hwnd, event_flag, 0, lparam)
        except Exception as e:
            print(f"send_mouse_event failed for hwnd={hwnd}: {e}")

def send_key_event(event_flag, vk_code):
    for hwnd in list(target_windows):
        try:
            source_hwnd = win32gui.GetForegroundWindow()
            source_thread = win32process.GetWindowThreadProcessId(source_hwnd)[0]
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
            attached = False
            try:
                if source_thread != target_thread:
                    ctypes.windll.user32.AttachThreadInput(source_thread, target_thread, True)
                    attached = True
            except Exception:
                pass
            scan = win32api.MapVirtualKey(vk_code, 0)
            if event_flag == win32con.WM_KEYDOWN:
                win32api.keybd_event(vk_code, scan, 0, 0)
            else:
                win32api.keybd_event(vk_code, scan, 0x0002, 0)
            if attached:
                try:
                    ctypes.windll.user32.AttachThreadInput(source_thread, target_thread, False)
                except Exception:
                    pass
        except Exception as e:
            print(f"send_key_event failed for hwnd={hwnd}: {e}")

# ===========================================================
# Input listeners
# ===========================================================
def on_move(x, y):
    if not is_source_active(): 
        return

    try:
        # get source window hwnd and client rect
        source_hwnd = win32gui.GetForegroundWindow()
        src_rect = win32gui.GetWindowRect(source_hwnd)  # (left, top, right, bottom)
        src_client_rect = win32gui.GetClientRect(source_hwnd)  # (0,0,w,h)

        # convert screen coordinates x,y -> source client coordinates
        rel_x = x - src_rect[0]
        rel_y = y - src_rect[1]

        # for each target window
        refresh_target_windows()
        for hwnd in target_windows:
            tgt_client_rect = win32gui.GetClientRect(hwnd)
            # scale coordinates proportionally
            tgt_x = int(rel_x * tgt_client_rect[2] / src_client_rect[2])
            tgt_y = int(rel_y * tgt_client_rect[3] / src_client_rect[3])
            send_mouse_event(tgt_x, tgt_y, win32con.WM_MOUSEMOVE)

    except Exception as e:
        print(f"on_move error: {e}")

def on_click(x, y, button, pressed):
    if not is_source_active():
        return

    try:
        # get source window hwnd and rect
        source_hwnd = win32gui.GetForegroundWindow()
        src_rect = win32gui.GetWindowRect(source_hwnd)  # (left, top, right, bottom)

        # convert screen coordinates x,y -> source relative coordinates
        rel_x = x - src_rect[0]
        rel_y = y - src_rect[1]

        print(f"source x={x}, y={y} -> rel_x={rel_x}, rel_y={rel_y} source_rect={src_rect}")

        # determine click message
        if button == mouse.Button.left:
            msg = win32con.WM_LBUTTONDOWN if pressed else win32con.WM_LBUTTONUP
        elif button == mouse.Button.right:
            msg = win32con.WM_RBUTTONDOWN if pressed else win32con.WM_RBUTTONUP
        else:
            return

        # send to each target
        refresh_target_windows()
        for hwnd in target_windows:
            tgt_rect = win32gui.GetWindowRect(hwnd)
            src_width = src_rect[2] - src_rect[0]
            src_height = src_rect[3] - src_rect[1]
            tgt_width = tgt_rect[2] - tgt_rect[0]
            tgt_height = tgt_rect[3] - tgt_rect[1]

            # scale coordinates proportionally
            tgt_x = int(tgt_rect[0] + rel_x * tgt_width / src_width)
            tgt_y = int(tgt_rect[1] + rel_y * tgt_height / src_height)

            print(f"tgt_x={tgt_x}, tgt_y={tgt_y} target_rect={tgt_rect}")
            send_mouse_event(tgt_x, tgt_y, msg)

    except Exception as e:
        print(f"on_click error: {e}")

def on_press(key):
    if not is_source_active(): return
    vk = vk_from_key(key)
    if vk:
        global _last_input_time
        _last_input_time = time.time()
        with _queue_lock:
            _input_queue.append(('keydown', vk))

def on_release(key):
    if not is_source_active(): return
    vk = vk_from_key(key)
    if vk:
        global _last_input_time
        _last_input_time = time.time()
        with _queue_lock:
            _input_queue.append(('keyup', vk))

def _process_input_queue():
    while True:
        time.sleep(0.01)
        with _queue_lock:
            if not _input_queue: continue
            elapsed = time.time() - _last_input_time
            if elapsed < _capture_debounce_delay: continue
            batch = list(_input_queue)
            _input_queue.clear()
        try:
            source_hwnd = win32gui.GetForegroundWindow()
            source_title = win32gui.GetWindowText(source_hwnd)
            if SOURCE_RE and not SOURCE_RE.search(source_title): continue
        except Exception:
            continue
        refresh_target_windows()
        for target_hwnd in list(target_windows):
            try:
                ctypes.windll.user32.SwitchToThisWindow(target_hwnd, True)
                time.sleep(0.5)
                for event_type, vk_code in batch:
                    try:
                        source_thread = win32process.GetWindowThreadProcessId(source_hwnd)[0]
                        target_thread = win32process.GetWindowThreadProcessId(target_hwnd)[0]
                        attached = False
                        try:
                            if source_thread != target_thread:
                                ctypes.windll.user32.AttachThreadInput(source_thread, target_thread, True)
                                attached = True
                        except Exception:
                            pass
                        scan = win32api.MapVirtualKey(vk_code, 0)
                        if event_type == 'keydown':
                            win32api.keybd_event(vk_code, scan, 0, 0)
                        else:
                            win32api.keybd_event(vk_code, scan, 0x0002, 0)
                        if attached:
                            ctypes.windll.user32.AttachThreadInput(source_thread, target_thread, False)
                    except Exception as e:
                        print(f"  -> Failed to send input: {e}")
            except Exception as e:
                print(f"Failed to process target {target_hwnd}: {e}")
        try:
            ctypes.windll.user32.SwitchToThisWindow(source_hwnd, True)
        except Exception:
            pass

# ===========================================================
# Diagnostics helpers
# ===========================================================
def diagnose_window_input(hwnd):
    """Extended diagnostics for why a window may ignore input."""
    print(f"\n--- Diagnosing input for HWND={hwnd} ---")
    try:
        tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        fg = win32gui.GetForegroundWindow()
        print(f"Foreground window HWND: {fg}")
        print(f"Target thread ID: {tid}, process ID: {pid}")
        try:
            hDesk = ctypes.windll.user32.GetThreadDesktop(tid)
            print(f"Input desktop handle: {hex(hDesk)}")
        except Exception as e:
            print(f"GetThreadDesktop failed: {e}")
        # Test AttachThreadInput
        source_tid = win32process.GetWindowThreadProcessId(fg)[0]
        attached = ctypes.windll.user32.AttachThreadInput(source_tid, tid, True)
        print(f"AttachThreadInput: {attached}")
        if attached: ctypes.windll.user32.AttachThreadInput(source_tid, tid, False)
        # Test SendInput (harmless F12)
        vk_test = win32con.VK_F12
        scan = win32api.MapVirtualKey(vk_test, 0)
        win32api.keybd_event(vk_test, scan, 0, 0)
        win32api.keybd_event(vk_test, scan, 0x0002, 0)
        print("SendInput test F12 sent")
    except Exception as e:
        print(f"Diagnosis failed: {e}")
    print("--- End of diagnosis ---\n")

def find_focused_child(hwnd):
    focused = win32gui.GetFocus()
    if focused:
        parent = win32gui.GetParent(focused)
        print(f"Focused child HWND={focused}, parent HWND={parent}")
    else:
        print(f"No focused window in thread of HWND={hwnd}")

def check_fullscreen(hwnd):
    rect = win32gui.GetWindowRect(hwnd)
    screen_width = win32api.GetSystemMetrics(0)
    screen_height = win32api.GetSystemMetrics(1)
    if rect == (0,0,screen_width,screen_height):
        print(f"Window HWND={hwnd} appears fullscreen (may use exclusive DirectInput)")
    else:
        print(f"Window HWND={hwnd} is windowed")

# ===========================================================
# CLI & main
# ===========================================================
def print_source_summary():
    compile_source_pattern()
    try:
        all_windows = list_all_windows()
        matching_source = None
        for hwnd, title in all_windows:
            if SOURCE_RE and SOURCE_RE.search(title):
                matching_source = (hwnd, title)
                break
        if matching_source:
            print(f"Source window: {matching_source[1]} (hwnd={matching_source[0]})")
        else:
            print(f"No window matching SOURCE_TITLE '{SOURCE_TITLE}' found.")
    except Exception as e:
        print(f"Error getting source window: {e}")

def print_target_summary():
    refresh_target_windows()
    if not target_windows:
        print("No target windows matched TARGET_TITLES.")
    else:
        print("Mirroring to windows:")
        for hwnd in target_windows:
            try:
                print(" -", win32gui.GetWindowText(hwnd), "(hwnd=", hwnd, ")")
            except Exception:
                pass

def main():
    print("Starting listeners. Press Ctrl+C to stop.")
    mouse_listener = mouse.Listener(on_click=on_click)
    mouse_listener.start()
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    keyboard_listener.start()
    processor_thread = threading.Thread(target=_process_input_queue, daemon=True)
    processor_thread.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping...")
        mouse_listener.stop()
        keyboard_listener.stop()

def _cli():
    parser = argparse.ArgumentParser(description='Mirror input from SOURCE to TARGET windows')
    parser.add_argument('--list-targets', action='store_true')
    parser.add_argument('--show-target-summary', action='store_true')
    parser.add_argument('--window-details', type=int)
    parser.add_argument('--diagnose', action='store_true', help='Run extended diagnostics for all target windows')
    parser.add_argument('--source', type=str)
    args = parser.parse_args()

    global SOURCE_TITLE
    if args.source:
        SOURCE_TITLE = args.source
    compile_target_patterns()
    compile_source_pattern()

    if args.window_details:
        print_window_full_tree(args.window_details)
        return

    if args.list_targets:
        all_w = list_all_windows()
        print("Visible windows (hwnd, title):")
        for hwnd,title in all_w:
            matches = [pat.pattern for pat in TARGET_PATTERNS if pat.search(title)]
            mark = "MATCH" if matches else ""
            print(f"{hwnd}\t{mark}\t{title}")
        return

    if args.show_target_summary:
        print_source_summary()
        print_target_summary()
        return

    if args.diagnose:
        refresh_target_windows()
        for hwnd in target_windows:
            diagnose_window_input(hwnd)
            find_focused_child(hwnd)
            check_fullscreen(hwnd)
        return

    print_source_summary()
    print_target_summary()
    main()

if __name__ == '__main__':
    _cli()

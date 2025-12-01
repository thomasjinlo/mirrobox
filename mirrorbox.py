"""mirrorbox.py

Simple input mirroring helper for Windows.

NOTES & WARNINGS
- This captures global mouse/keyboard events and broadcasts them to other
  windows. Use only on machines and windows you own or have explicit consent
  to control. Input capture/broadcast can be abused and may be blocked by
  elevated/secure apps (e.g., games or UAC prompts).

Dependencies: `pynput`, `pywin32` (install with `pip install pynput pywin32`).
"""

from pynput import mouse, keyboard
import win32gui
import win32api
import win32con
import sys
import time
import argparse

# ===========================================================
# CONFIGURATION — set the source window title and the targets
# ===========================================================
# Only when the foreground window contains SOURCE_TITLE (case-insensitive)
# will the input be mirrored to the TARGET_TITLES windows.
SOURCE_TITLE = "Source Window"

TARGET_TITLES = [
    "Window 1",
    "Window 2",
    "Window 3",
]


# ===========================================================
# Helper: find windows by title substrings
# ===========================================================
target_windows = []

def enum_win(hwnd, ctx):
    title = win32gui.GetWindowText(hwnd)
    # skip invisible or empty titles
    try:
        if not title or not win32gui.IsWindowVisible(hwnd):
            return
    except Exception:
        return

    if any(t.lower() in title.lower() for t in TARGET_TITLES):
        target_windows.append(hwnd)


def refresh_target_windows():
    target_windows.clear()
    win32gui.EnumWindows(enum_win, None)


def list_all_windows():
    """Return list of (hwnd, title) for visible non-empty windows."""
    results = []

    def _collect(hwnd, ctx):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            title = win32gui.GetWindowText(hwnd)
            if title and title.strip():
                results.append((hwnd, title))
        except Exception:
            pass

    win32gui.EnumWindows(_collect, None)
    return results


def print_target_summary():
    # refresh and print targets and matches
    refresh_target_windows()
    if not target_windows:
        print("No target windows matched TARGET_TITLES. Use --list-targets to see available windows.")
    else:
        print("Mirroring to windows:")
        for hwnd in target_windows:
            try:
                print(" -", win32gui.GetWindowText(hwnd), "(hwnd=", hwnd, ")")
            except Exception:
                pass


# ===========================================================
# Utilities for sending events
# ===========================================================
def is_source_active():
    fg = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(fg) or ""
    return SOURCE_TITLE.lower() in title.lower()


def send_mouse_event(x, y, event_flag):
    """Send a mouse message (PostMessage) to each target window.
    Converts screen coords to client coords using ScreenToClient.
    """
    for hwnd in list(target_windows):
        try:
            # Convert global/screen coords to client coords for this window
            client_pt = win32gui.ScreenToClient(hwnd, (int(x), int(y)))
            local_x, local_y = client_pt
            lparam = win32api.MAKELONG(local_x & 0xFFFF, local_y & 0xFFFF)
            win32gui.PostMessage(hwnd, event_flag, 0, lparam)
        except Exception as e:
            print(f"send_mouse_event failed for hwnd={hwnd}: {e}")


def send_key_event(event_flag, vk_code):
    for hwnd in list(target_windows):
        try:
            win32gui.PostMessage(hwnd, event_flag, int(vk_code), 0)
        except Exception as e:
            print(f"send_key_event failed for hwnd={hwnd}: {e}")


# Simple mapping for some special keys from pynput Key to VK
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
    keyboard.Key.shift_r: win32con.VK_RSHIFT if hasattr(win32con, 'VK_RSHIFT') else win32con.VK_SHIFT,
    keyboard.Key.ctrl: win32con.VK_CONTROL,
    keyboard.Key.ctrl_l: win32con.VK_LCONTROL if hasattr(win32con, 'VK_LCONTROL') else win32con.VK_CONTROL,
    keyboard.Key.alt: win32con.VK_MENU,
}


def vk_from_key(key):
    # printable char
    try:
        if hasattr(key, 'char') and key.char is not None:
            # VkKeyScan returns a short with VK code in low byte
            vk = win32api.VkKeyScan(key.char) & 0xFF
            return vk
    except Exception:
        pass

    # special keys
    return SPECIAL_KEY_MAP.get(key)


# ===========================================================
# Listeners (only mirror when SOURCE window is active)
# ===========================================================
def on_move(x, y):
    if not is_source_active():
        return
    send_mouse_event(x, y, win32con.WM_MOUSEMOVE)


def on_click(x, y, button, pressed):
    if not is_source_active():
        return
    if button == mouse.Button.left:
        msg = win32con.WM_LBUTTONDOWN if pressed else win32con.WM_LBUTTONUP
    elif button == mouse.Button.right:
        msg = win32con.WM_RBUTTONDOWN if pressed else win32con.WM_RBUTTONUP
    else:
        return

    send_mouse_event(x, y, msg)


def on_press(key):
    if not is_source_active():
        return
    vk = vk_from_key(key)
    if vk:
        send_key_event(win32con.WM_KEYDOWN, vk)


def on_release(key):
    if not is_source_active():
        return
    vk = vk_from_key(key)
    if vk:
        send_key_event(win32con.WM_KEYUP, vk)


def main():
    print("Starting listeners. Press Ctrl+C to stop.")

    mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
    keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)

    mouse_listener.start()
    keyboard_listener.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping...")
        mouse_listener.stop()
        keyboard_listener.stop()


def _cli():
    parser = argparse.ArgumentParser(description='Mirror mouse/keyboard from SOURCE to TARGET windows')
    parser.add_argument('--list-targets', action='store_true', help='List all visible windows and show which match TARGET_TITLES')
    parser.add_argument('--show-target-summary', action='store_true', help='Print the current matched target windows and exit')
    parser.add_argument('--source', type=str, help='Override SOURCE_TITLE for this run')

    args = parser.parse_args()

    if args.source:
        global SOURCE_TITLE
        SOURCE_TITLE = args.source

    if args.list_targets or args.list_targets if False else False:
        # this branch kept for safe refactor; real flag handled below
        pass

    if args.list_targets:
        all_w = list_all_windows()
        print("Visible windows (hwnd, title):")
        for hwnd, title in all_w:
            matches = [t for t in TARGET_TITLES if t.lower() in title.lower()]
            mark = "MATCH" if matches else ""
            print(f"{hwnd}\t{mark}\t{title}")
        return

    if args.show_target_summary:
        print_target_summary()
        return

    # default: run mirroring
    print_target_summary()
    main()


if __name__ == '__main__':
    _cli()
def on_move(x, y):
    send_mouse_event(x, y, win32con.WM_MOUSEMOVE)

def on_click(x, y, button, pressed):
    msg = win32con.WM_LBUTTONDOWN if pressed else win32con.WM_LBUTTONUP
    if button == mouse.Button.right:
        msg = win32con.WM_RBUTTONDOWN if pressed else win32con.WM_RBUTTONUP

    send_mouse_event(x, y, msg)


# ===========================================================
# STEP 5 — KEYBOARD LISTENER
# ===========================================================
def on_press(key):
    try:
        vk = win32api.VkKeyScan(str(key.char))
        send_key_event(win32con.WM_KEYDOWN, vk)
    except AttributeError:
        pass  # special keys handled separately

def on_release(key):
    try:
        vk = win32api.VkKeyScan(str(key.char))
        send_key_event(win32con.WM_KEYUP, vk)
    except AttributeError:
        pass


# ===========================================================
# START LISTENERS
# ===========================================================
mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)

mouse_listener.start()
keyboard_listener.start()

mouse_listener.join()
keyboard_listener.join()

keyboard_listener.start()

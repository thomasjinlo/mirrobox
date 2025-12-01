# MirrorBox

Simple Windows helper to mirror mouse and keyboard input from a source window to other target windows.

WARNING: This tool captures and replays input. Use only on machines and windows you own or have explicit permission to control. Some applications (games, elevated processes, UAC dialogs) may ignore synthesized messages.

## Requirements
- Windows
- Python 3.8+
- PowerShell (examples below use PowerShell)

## Install Python (Windows)

If you don't already have Python installed, follow one of the options below.

- Quick check (PowerShell):

```powershell
python --version
py --version
```

- Install via the Microsoft Store (easy, adds to PATH):

1. Open Microsoft Store, search `Python 3.x` and install the official package.

- Install via the official installer (recommended for full control):

1. Visit https://www.python.org/downloads/windows/
2. Download the latest recommended stable installer (x86-64 executable installer).
3. Run the installer and check "Add Python to PATH" before installing.

- Install via winget (command-line):

```powershell
winget install --id=Python.Python.3 -e --source winget
```

After install, verify:

```powershell
python --version
pip --version
```

## Install Python dependencies

Install the required packages for this project:

```powershell
pip install --user pynput pywin32
```

If you use a virtualenv, activate it first and run `pip install pynput pywin32`.

## Quick usage
1. Open the windows you intend to mirror to (targets), and open the source window you will operate from.
2. Edit `mirrorbox.py` and set `SOURCE_TITLE` to a substring of the source window's title (case-insensitive). Example: `SOURCE_TITLE = "Notepad"`.
3. Edit `TARGET_TITLES` with substrings for the windows you want to mirror to. Example: `TARGET_TITLES = ["Untitled - Notepad"]`.

### List visible windows and verify titles
You can list visible windows and see which ones match your configured `TARGET_TITLES`:

```powershell
python c:\Users\function\code\mirrorbox.py --list-targets
```

This prints `hwnd`, an optional `MATCH` marker if any configured target substrings match the window title, and the full title.

### Print currently matched target windows
Refreshes and prints the windows that matched `TARGET_TITLES` as currently configured in the file:

```powershell
python c:\Users\function\code\mirrorbox.py --show-target-summary
```

### Run the mirroring
Make the `SOURCE_TITLE` window the active/foreground window, then run:

```powershell
python c:\Users\function\code\mirrorbox.py
```

While the source window is foreground, mouse moves, clicks and basic keystrokes will be posted to each matched target window.

## Notes & limitations
- `PostMessage` is used to post messages to target windows. Some applications ignore posted messages or require the window to be focused; `SendInput` is more reliable for system-level input but sends to the focused window and not directly to a specific window handle.
- Modifier keys and complex input combinations may require additional handling. This tool implements a basic mapping for common keys and printable characters.
- DPI scaling and some international keyboards may affect coordinate mapping and VK codes.

## Safety and ethics
Do not use this to control windows or machines without explicit permission. Capturing and broadcasting input can interfere with other users and may violate policies or laws.

## Next improvements (ideas)
- Use `SendInput` to synthesize system-level input for better compatibility with games.
- Add a GUI to pick source and target windows interactively.
- Track and replay modifier states more accurately.

If you want one of these, tell me which and I can implement it next.

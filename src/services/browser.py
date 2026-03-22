import os
import sys

IS_WINDOWS = sys.platform == "win32"


def _registry_path(browser_name: str):
    if not IS_WINDOWS:
        return None

    try:
        import winreg
    except Exception:
        return None

    app_names = {
        "Google Chrome": "chrome.exe",
        "Microsoft Edge": "msedge.exe",
        "Brave": "brave.exe",
        "Opera GX": "opera.exe",
        "Firefox": "firefox.exe",
        "Vivaldi": "vivaldi.exe",
    }
    exe = app_names.get(browser_name)
    if not exe:
        return None

    keys = [
        rf"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}",
        rf"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}",
    ]

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key in keys:
            try:
                with winreg.OpenKey(root, key) as k:
                    val, _ = winreg.QueryValueEx(k, "")
                    if val and os.path.exists(val):
                        return val
            except Exception:
                continue

    return None


def browser_paths():
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    return {
        "Opera GX": [
            os.path.join(local, "Programs", "Opera GX", "opera.exe"),
            os.path.join(appdata, "Local", "Programs", "Opera GX", "opera.exe"),
        ],
        "Google Chrome": [
            os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        ],
        "Microsoft Edge": [
            os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(program_files, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(local, "Microsoft", "Edge", "Application", "msedge.exe"),
        ],
        "Brave": [
            os.path.join(program_files, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(program_files_x86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(local, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
        ],
        "Firefox": [
            os.path.join(program_files, "Mozilla Firefox", "firefox.exe"),
            os.path.join(program_files_x86, "Mozilla Firefox", "firefox.exe"),
        ],
        "Vivaldi": [os.path.join(local, "Vivaldi", "Application", "vivaldi.exe")],
        "System Default": ["default"],
    }


def detect_browser(name: str):
    for path in browser_paths().get(name, []):
        if path == "default":
            return "default"
        if path and os.path.exists(path):
            return path

    reg = _registry_path(name)
    if reg:
        return reg

    return None


def auto_detect():
    detected = {}
    for name in browser_paths().keys():
        path = detect_browser(name)
        if path is not None:
            detected[name] = path
    return detected

"""
Elvar v8.0 - app by Ash
Requires: pip install customtkinter pillow pystray keyboard pyperclip requests
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess, os, time, threading, json, re, sys, queue, ctypes
import zipfile, random, shutil, urllib.request, urllib.error, webbrowser
from datetime import datetime
import pyperclip
from api.ext_server import start_ext_server
from security.crypto import CRYPTO_OK, read_file_content, write_file_content
from security.auth import (
    ensure_auth_settings,
    hash_password,
    verify_password_from_settings,
    has_password,
    make_protected_key,
)
from services.browser import detect_browser, auto_detect, browser_paths
from services.logger import get_logger
from services.workflow_pipeline import prepare_pairs
from storage.json_store import load_json, save_json
from storage.backup import safe_extract_zip, UnsafeArchiveError
from ui.pages.workflows_page import build_workflows
from ui.pages.settings_page import build_settings
from ui.pages.launcher_page import build_launcher
from ui.pages.sessions_page import build_sessions
from ui.pages.history_page import build_history
from ui.pages.analytics_page import build_analytics
from ui.pages.protected_page import build_protected

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    import io
    GDRIVE_OK = True
except ImportError:
    GDRIVE_OK = False

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import pystray
    TRAY_OK = True
except ImportError:
    TRAY_OK = False

try:
    import keyboard as kb
    KB_OK = True
except ImportError:
    KB_OK = False

try:
    import winsound as _ws
    SOUND_OK = True
except ImportError:
    SOUND_OK = False

IS_WINDOWS = sys.platform == "win32"

APP_DIR        = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ElvarByAsh")
WORKFLOWS_FILE = os.path.join(APP_DIR, "workflows.json")
SESSIONS_FILE  = os.path.join(APP_DIR, "sessions.json")
SETTINGS_FILE  = os.path.join(APP_DIR, "settings.json")
HISTORY_FILE   = os.path.join(APP_DIR, "history.json")
BACKUP_FILE    = os.path.join(APP_DIR, "workflows_auto_backup.json")
SETTINGS_SCHEMA_VERSION = 2
os.makedirs(APP_DIR, exist_ok=True)
LOGGER = get_logger(APP_DIR)

ctk.set_default_color_theme("blue")


def _resource_path(*parts):
    bases = []
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        bases.append(sys._MEIPASS)
    bases.append(os.path.dirname(os.path.abspath(__file__)))
    bases.append(os.getcwd())

    for base in bases:
        candidate = os.path.join(base, *parts)
        if os.path.exists(candidate):
            return candidate

    return os.path.join(bases[0], *parts)



def _load(path, default):
    return load_json(path, default, LOGGER)


def _save(path, data):
    return save_json(path, data, LOGGER)


def _auto_backup(wf):
    try:
        _save(BACKUP_FILE, wf)
    except Exception as exc:
        LOGGER.exception("Auto-backup failed: %s", exc)


BROWSER_PATHS = browser_paths()
def normalize_url(raw):
    url = raw.strip()
    if not url or url.startswith("#"): return None
    if "{clipboard}" in url:
        try:
            url = url.replace("{clipboard}", pyperclip.paste().strip())
        except Exception as exc:
            LOGGER.debug("Clipboard placeholder expansion failed: %s", exc)
    if re.match(r'^https?://', url): return url
    if "." in url:
        for prefix in ("http:","https:","ftp:"):
            if url.lower().startswith(prefix): url = url[len(prefix):]
        url = url.lstrip("/")
        if url.lower().startswith("www."): url = url[4:]
        return "https://www." + url
    return None

def strip_tracking(url):
    keys = {"utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid"}
    if "?" not in url: return url
    base, qs = url.split("?", 1)
    params = [p for p in qs.split("&") if p.split("=")[0].lower() not in keys]
    return base + ("?" + "&".join(params) if params else "")

def check_link_alive(url, timeout=5):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":"Elvar/8.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, r.status, "OK"
    except urllib.error.HTTPError as e:
        return (e.code < 400), e.code, str(e.reason)
    except Exception as e:
        return False, None, str(e)[:40]

def open_subprocess(args):
    kw = {"stdout":subprocess.DEVNULL,"stderr":subprocess.DEVNULL}
    subprocess.Popen(args, **kw)

def open_folder(path):
    if IS_WINDOWS: subprocess.Popen(["explorer", path], creationflags=subprocess.CREATE_NO_WINDOW)
    elif sys.platform == "darwin": subprocess.Popen(["open", path])
    else: subprocess.Popen(["xdg-open", path])

def play_sound():
    if not SOUND_OK: return
    try:
        _ws.MessageBeep(_ws.MB_ICONASTERISK)
    except Exception as exc:
        LOGGER.debug("Sound playback failed: %s", exc)

def make_tray_icon():
    if not PIL_OK: return None
    from PIL import Image, ImageDraw
    
    icon_path = _resource_path("elvar_icon.ico")
        
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception as exc:
            LOGGER.debug("Tray icon file load failed: %s", exc)
            
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 60, 60], radius=14, fill=(0, 122, 255, 255))
    d.polygon([(22, 18), (46, 32), (22, 46)], fill=(255, 255, 255, 255))
    
    ico_out = _resource_path("elvar_icon.ico")
    if not os.path.exists(ico_out):
        try:
            img.save(ico_out, format="ICO", sizes=[(64, 64)])
        except Exception as exc:
            LOGGER.exception("Non-critical operation failed: %s", exc)
        
    return img

def set_icon(window):
    icon_path = _resource_path("elvar_icon.ico")
        
    if os.path.exists(icon_path):
        try:
            window.iconbitmap(icon_path)
        except Exception as exc:
            LOGGER.debug("Window icon set failed: %s", exc)

def _set_windows_app_id():
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Ash.Elvar.App")
    except Exception as exc:
        LOGGER.debug("Failed to set AppUserModelID: %s", exc)
class CTkTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text: return
        x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2)
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        
        label = tk.Label(tw, text=self.text, background="#1C1C1E", foreground="#FFFFFF", 
                         relief="solid", borderwidth=1, font=("Helvetica", 10), padx=6, pady=3)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class Toast(ctk.CTkToplevel):
    def __init__(self, parent, message, color="green", duration=2200):
        super().__init__(parent)
        set_icon(self)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)
        
        frame = ctk.CTkFrame(self, fg_color=color, corner_radius=8)
        frame.pack(fill="both", expand=True)
        lbl = ctk.CTkLabel(frame, text=message, text_color="#FFFFFF", font=("Helvetica", 13, "bold"))
        lbl.pack(padx=20, pady=12)
        
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{sw - w - 24}+{sh - h - 60}")
        
        self._fade_in(0)
        self.after(duration, self._fade_out)

    def _fade_in(self, step):
        if step <= 10:
            self.attributes("-alpha", step / 10)
            self.after(15, lambda: self._fade_in(step + 1))

    def _fade_out(self, step=10):
        if step >= 0:
            self.attributes("-alpha", step / 10)
            self.after(20, lambda: self._fade_out(step - 1))
        else:
            self.destroy()

class CommandPalette(ctk.CTkToplevel):
    def __init__(self, parent, workflows, run_cb, nav_cb=None, last_workflow=None):
        super().__init__(parent)
        set_icon(self)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self._run_cb = run_cb
        self._nav_cb = nav_cb
        
        W, H = 600, 450
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//3}")
        self.grab_set()
        
        self.attributes("-alpha", 0.0)
        self._fade_in(0)
        
        self.frame = ctk.CTkFrame(self, corner_radius=12, border_width=1, border_color=("#D1D1D6", "#38383A"))
        self.frame.pack(fill="both", expand=True)
        
        search_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(search_frame, text="\u2315", font=("Helvetica", 20)).pack(side="left", padx=(0, 10))
        self.entry = ctk.CTkEntry(search_frame, font=("Helvetica", 16), border_width=0, fg_color="transparent")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.focus()
        
        self.entry.bind("<KeyRelease>", self._on_type)
        self.entry.bind("<Escape>", lambda e: self.destroy())
        self.entry.bind("<Return>", self._execute_selected)
        self.entry.bind("<Up>", lambda e: self._move(-1))
        self.entry.bind("<Down>", lambda e: self._move(1))
        
        ctk.CTkFrame(self.frame, height=1, fg_color=("#D1D1D6", "#38383A")).pack(fill="x")
        
        self.scroll = ctk.CTkScrollableFrame(self.frame, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.frame, text="\u2191\u2193 navigate  |  Enter run  |  Esc close", font=("Helvetica", 10), text_color=("#8E8E93", "#98989D")).pack(pady=5)
        
        self._commands = {}
        if last_workflow: self._commands[f"\u25B6  Run last: {last_workflow}"] = ("run", last_workflow)
        for name in workflows: self._commands[f"\u25B6  {name}"] = ("run", name)
        for key, lbl in [("workflows", "Workflows"), ("launcher", "Launcher"), ("sessions", "Sessions"),
                         ("history", "History"), ("settings", "Settings")]:
            self._commands[f"\u2192  Go to {lbl}"] = ("nav", key)
            
        self._all = list(self._commands.keys())
        self._items = []
        self._sel_idx = 0
        self._widgets = []
        self._filter("")

    def _fade_in(self, step):
        if step <= 10:
            self.attributes("-alpha", step / 10)
            self.after(10, lambda: self._fade_in(step + 1))

    def _on_type(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"): return
        self._filter(self.entry.get())

    def _filter(self, query):
        q = query.strip().lower()
        for w in self._widgets: w.destroy()
        self._widgets.clear()
        
        self._items = [c for c in self._all if not q or q in c.lower()]
        self._sel_idx = 0
        
        for i, text in enumerate(self._items):
            btn = ctk.CTkButton(self.scroll, text=text, font=("Helvetica", 14), anchor="w",
                                fg_color="transparent", text_color=("#000000", "#FFFFFF"),
                                hover_color=("#E5E5EA", "#3A3A3C"), corner_radius=6,
                                command=lambda t=text: self._execute(t))
            btn.pack(fill="x", pady=2)
            self._widgets.append(btn)
            
        self._highlight()

    def _move(self, delta):
        if not self._items: return "break"
        self._sel_idx = max(0, min(len(self._items)-1, self._sel_idx + delta))
        self._highlight()
        # Scroll to view
        if self._widgets:
            self.scroll._parent_canvas.yview_moveto(self._sel_idx / max(1, len(self._items)))
        return "break"

    def _highlight(self):
        for i, btn in enumerate(self._widgets):
            if i == self._sel_idx:
                btn.configure(fg_color=("#E5E5EA", "#3A3A3C"))
            else:
                btn.configure(fg_color="transparent")

    def _execute_selected(self, event=None):
        if self._items: self._execute(self._items[self._sel_idx])

    def _execute(self, text):
        cmd = self._commands.get(text)
        self.destroy()
        if not cmd: return
        kind, val = cmd
        if kind == "run": self._run_cb(val)
        elif kind == "nav" and self._nav_cb: self._nav_cb(val)
class LinkEditorDialog(ctk.CTkToplevel):
    def __init__(self, parent, name, data, on_save, password=None):
        super().__init__(parent)
        set_icon(self)
        self.title(f"Edit    {name}")
        self._data = data
        self._fp = data.get("path", "")
        self._on_save = on_save
        self._password = password
        
        W, H = 800, 550
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True)
        
        left_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        left_frame.pack(side="left", fill="both", expand=True)
        
        right_frame = ctk.CTkFrame(main_frame, width=250, fg_color=("#FFFFFF", "#1C1C1E"))
        right_frame.pack(side="right", fill="y", padx=20, pady=20)
        right_frame.pack_propagate(False)
        
        hdr = ctk.CTkFrame(left_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(hdr, text=f"\u270E  {name}", font=("Helvetica", 20, "bold")).pack(side="left")
        ctk.CTkLabel(hdr, text="One URL per line", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="right")
        
        tb = ctk.CTkFrame(left_frame, fg_color="transparent")
        tb.pack(fill="x", padx=20, pady=(0, 10))
        
        for txt, cmd, col in [("Dedup", self._dedup, "blue"), ("Rm Blank", self._rm_blank, "orange"),
                             ("Sort", self._sort, "teal"), ("Shuffle", self._shuffle, "brown"),
                             ("Validate", self._validate, "green"), ("Strip UTM", self._strip_utm, "purple"),
                             ("Extract", self._extract_urls, "magenta"), ("Import .txt", self._import_txt, "gray50"),
                             ("Ping URLs", self._ping_urls, "red")]:
            ctk.CTkButton(tb, text=txt, command=cmd, fg_color="transparent", border_width=1,
                          border_color=col, text_color=col, width=80, height=28).pack(side="left", padx=(0, 5))
                          
        self._count_lbl = ctk.CTkLabel(tb, text="", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D"))
        self._count_lbl.pack(side="right")
        
        foot = ctk.CTkFrame(left_frame, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=20, pady=15)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="left")
        ctk.CTkButton(foot, text="Save Changes", command=self._save, fg_color="#34C759", hover_color="#28A745").pack(side="right")
        
        self._txt = ctk.CTkTextbox(left_frame, font=("Courier New", 14), wrap="none")
        self._txt.pack(fill="both", expand=True, padx=20, pady=10)
        
        try:
            content = read_file_content(self._fp, self._data.get("is_protected", False), self._password)
            self._txt.insert("1.0", content)
        except Exception as exc:
            LOGGER.exception("Non-critical operation failed: %s", exc)
        
        self._txt.bind("<KeyRelease>", lambda e: self._update_count())
        self._update_count()
        
        ctk.CTkLabel(right_frame, text="Properties", font=("Helvetica", 16, "bold")).pack(pady=(20, 15))
        
        self._vars = {}
        flags = [
            ("is_queue", "Queue Mode (Pop URLs)"),
            ("is_task_list", "Task List (Checkboxes)"),
            ("hide_from_history", "Hide from History"),
            ("is_protected", "Password Protected"),
            ("is_hidden", "Hide from Main List")
        ]
        
        for key, label in flags:
            var = ctk.BooleanVar(value=self._data.get(key, False))
            self._vars[key] = var
            cb = ctk.CTkCheckBox(right_frame, text=label, variable=var, font=("Helvetica", 13))
            cb.pack(anchor="w", padx=20, pady=8)

    def _update_count(self):
        lines = [l for l in self._txt.get("1.0", "end").splitlines() if l.strip() and not l.strip().startswith("#")]
        self._count_lbl.configure(text=f"{len(lines)} URLs")

    def _dedup(self):
        lines = self._txt.get("1.0", "end").splitlines()
        seen, out = set(), []
        for l in lines:
            k = l.strip()
            if k not in seen: seen.add(k); out.append(l)
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", "\n".join(out))
        self._update_count()

    def _rm_blank(self):
        lines = [l for l in self._txt.get("1.0", "end").splitlines() if l.strip()]
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", "\n".join(lines))
        self._update_count()

    def _sort(self):
        lines = sorted(self._txt.get("1.0", "end").splitlines(), key=str.strip)
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", "\n".join(lines))

    def _shuffle(self):
        lines = self._txt.get("1.0", "end").splitlines()
        random.shuffle(lines)
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", "\n".join(lines))

    def _extract_urls(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Extract URLs from Text/HTML")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()
        
        ctk.CTkLabel(dialog, text="Paste raw text or HTML below:", font=("Helvetica", 14, "bold")).pack(pady=10)
        txt = ctk.CTkTextbox(dialog, font=("Courier New", 12))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        
        def do_extract():
            content = txt.get("1.0", "end")
            found = re.findall(r"""https?://[^\s<>"']+|www\.[^\s<>"']+""", content)
            if found:
                self._txt.insert("end", "\n" + "\n".join(found))
                self._update_count()
                messagebox.showinfo("Extracted", f"Found and added {len(found)} URLs.")
                dialog.destroy()
            else:
                messagebox.showwarning("No URLs", "No URLs found in the provided text.")
                
        ctk.CTkButton(dialog, text="Extract & Add", command=do_extract, fg_color="magenta", hover_color="#8E33B7").pack(pady=10)

    def _validate(self):
        lines = self._txt.get("1.0", "end").splitlines()
        fixed, count = [], 0
        for l in lines:
            u = normalize_url(l)
            if l.strip() and u and u != l.strip(): fixed.append(u); count += 1
            else: fixed.append(l)
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", "\n".join(fixed))
        messagebox.showinfo("Validate", f"Fixed {count} URL(s).")
        self._update_count()

    def _strip_utm(self):
        lines = self._txt.get("1.0", "end").splitlines()
        cleaned, count = [], 0
        for l in lines:
            u = normalize_url(l)
            if u:
                new = strip_tracking(u)
                cleaned.append(new)
                if new != u: count += 1
            else: cleaned.append(l)
        self._txt.delete("1.0", "end")
        self._txt.insert("1.0", "\n".join(cleaned))
        messagebox.showinfo("Strip UTM", f"Cleaned tracking params from {count} URL(s).")

    def _import_txt(self):
        fp = filedialog.askopenfilename(filetypes=[("Text", "*.txt")])
        if fp:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    self._txt.insert("end", "\n" + f.read())
                self._update_count()
            except Exception as e: messagebox.showerror("Error", str(e))

    def _ping_urls(self):
        lines = self._txt.get("1.0", "end").splitlines()
        urls = [l for l in lines if normalize_url(l)]
        if not urls: return
        
        orig_title = self.title()
        self.title(f"{orig_title} (Pinging {len(urls)} URLs...)")
        
        def worker():
            dead = []
            for u in urls:
                alive, code, msg = check_link_alive(u)
                if not alive: dead.append(f"{u} ({msg})")
            
            self.after(0, lambda: self.title(orig_title))
            if dead:
                self.after(0, lambda: messagebox.showwarning("Dead Links Found", f"Found {len(dead)} dead links:\n" + "\n".join(dead[:10]) + ("\n..." if len(dead) > 10 else "")))
            else:
                self.after(0, lambda: messagebox.showinfo("Ping Complete", "All links appear to be alive!"))
                
        threading.Thread(target=worker, daemon=True).start()

    def _save(self):
        content = self._txt.get("1.0", "end").strip()
        try:
            write_file_content(self._fp, content + "\n", self._data.get("is_protected", False), self._password)
            for key, var in self._vars.items():
                self._data[key] = var.get()
            self._on_save()
            self.destroy()
        except Exception as e: messagebox.showerror("Error", str(e))

class NewWorkflowDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_create, existing_names):
        super().__init__(parent)
        set_icon(self)
        self.attributes("-alpha", 0.0)
        self.title("New Workflow")
        self._on_create = on_create
        self._existing = existing_names
        
        W, H = 650, 550
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        ctk.CTkLabel(self, text="+ New Workflow", font=("Helvetica", 20, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="left")
        ctk.CTkButton(foot, text="Create Workflow", command=self._create, fg_color="#007AFF").pack(side="right")
        
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)
        
        ctk.CTkLabel(body, text="WORKFLOW NAME", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        self._name_ent = ctk.CTkEntry(body, font=("Helvetica", 14), height=35)
        self._name_ent.insert(0, f"Workflow {len(existing_names)+1}")
        self._name_ent.pack(fill="x", pady=(5, 15))
        self._name_ent.focus()
        
        ctk.CTkLabel(body, text="NOTES (optional)", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        self._notes_ent = ctk.CTkEntry(body, font=("Helvetica", 14), height=35)
        self._notes_ent.pack(fill="x", pady=(5, 15))
        
        ctk.CTkLabel(body, text="TAGS (comma separated)", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        self._tags_ent = ctk.CTkEntry(body, font=("Helvetica", 14), height=35)
        self._tags_ent.pack(fill="x", pady=(5, 15))
        
        flags_frame = ctk.CTkFrame(body, fg_color="transparent")
        flags_frame.pack(fill="x", pady=(0, 15))
        
        self._vars = {}
        flags = [
            ("is_queue", "Queue Mode"),
            ("is_task_list", "Task List"),
            ("hide_from_history", "Hide History"),
            ("is_protected", "Protected"),
            ("is_hidden", "Hidden")
        ]
        
        for i, (key, label) in enumerate(flags):
            var = ctk.BooleanVar(value=False)
            self._vars[key] = var
            cb = ctk.CTkCheckBox(flags_frame, text=label, variable=var, font=("Helvetica", 12))
            cb.grid(row=i//3, column=i%3, padx=(0, 15), pady=5, sticky="w")
        
        ctk.CTkLabel(body, text="URLS (one per line)", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        self._txt = ctk.CTkTextbox(body, font=("Courier New", 14))
        self._txt.pack(fill="both", expand=True, pady=(5, 15))
        self._txt.insert("1.0", "# Paste your URLs here\n\n")
        
        self.after(50, lambda: self.attributes("-alpha", 1.0))

    def _create(self):
        name = self._name_ent.get().strip()
        if not name: messagebox.showwarning("Name Required", "Enter a workflow name."); return
        if name in self._existing: messagebox.showwarning("Already Exists", f"'{name}' already exists."); return
        
        urls = []
        for line in self._txt.get("1.0", "end").splitlines():
            if not line.strip() or line.strip().startswith("#"): continue
            u = normalize_url(line)
            if u: urls.append(u)
            
        if not urls: messagebox.showwarning("No URLs", "Add at least one valid URL."); return
        if not messagebox.askyesno("Confirm", f"Create workflow '{name}' with {len(urls)} URLs?"): return
        
        safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        fp = os.path.join(APP_DIR, f"{safe}.txt")
        
        flags_data = {k: v.get() for k, v in self._vars.items()}
        
        write_file_content(fp, "\n".join(urls) + "\n", flags_data.get("is_protected", False), self.master._protected_secret() if hasattr(self.master, "_protected_secret") else None)
        
        tags_raw = self._tags_ent.get().strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        
        self._on_create(name, fp, None, self._notes_ent.get().strip(), tags, flags_data)
        self.destroy()

class AddToWorkflowDialog(ctk.CTkToplevel):
    def __init__(self, parent, url, title, workflows, on_add):
        super().__init__(parent)
        set_icon(self)
        self.title("Add to Workflow")
        self.geometry("400x250")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        self._url = url
        self._on_add = on_add
        
        ctk.CTkLabel(self, text="Add Link to Workflow", font=("Helvetica", 18, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(self, text=f"Link: {title[:40]}...", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack()
        
        self._wf_var = ctk.StringVar(value=workflows[0] if workflows else "")
        cb = ctk.CTkComboBox(self, values=workflows, variable=self._wf_var, font=("Helvetica", 14), state="readonly")
        cb.pack(fill="x", padx=40, pady=20)
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=40, pady=20)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), width=100).pack(side="left")
        ctk.CTkButton(foot, text="Add Link", command=self._add, fg_color="#007AFF", width=100).pack(side="right")
        
    def _add(self):
        wf = self._wf_var.get()
        if wf:
            self._on_add(wf, self._url)
        self.destroy()

class WorkflowSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, name, data, on_save):
        super().__init__(parent)
        set_icon(self)
        self.attributes("-alpha", 0.0)
        self.title(f"Settings: {name}")
        self._on_save = on_save
        self._name = name
        self._data = data
        
        W, H = 500, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        ctk.CTkLabel(self, text=f"Settings: {name}", font=("Helvetica", 20, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="left")
        ctk.CTkButton(foot, text="Save Settings", command=self._save, fg_color="#007AFF").pack(side="right")
        
        sf = ctk.CTkScrollableFrame(self, fg_color="transparent")
        sf.pack(fill="both", expand=True, padx=20, pady=10)
        
        settings = data.get("settings", {})
        
        # Delay
        d_row = ctk.CTkFrame(sf, fg_color="transparent")
        d_row.pack(fill="x", pady=5)
        ctk.CTkLabel(d_row, text="Delay (s):", width=100, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
        self.delay_var = ctk.DoubleVar(value=settings.get("delay", parent.delay_var.get()))
        self.d_val_lbl = ctk.CTkLabel(d_row, text=f"{self.delay_var.get():.1f}s", width=40)
        self.d_val_lbl.pack(side="right")
        def update_d_lbl(val):
            self.d_val_lbl.configure(text=f"{float(val):.1f}s")
            self.delay_var.set(float(val))
        ctk.CTkSlider(d_row, from_=0, to=10, variable=self.delay_var, number_of_steps=100, command=update_d_lbl).pack(side="left", fill="x", expand=True, padx=10)
        
        # Mode & Range
        m_row = ctk.CTkFrame(sf, fg_color="transparent")
        m_row.pack(fill="x", pady=5)
        ctk.CTkLabel(m_row, text="Mode:", width=100, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
        self.run_mode = ctk.StringVar(value=settings.get("run_mode", parent.run_mode.get()))
        ctk.CTkComboBox(m_row, values=["sequential", "reverse", "shuffle", "batch"], variable=self.run_mode, width=120).pack(side="left", padx=(10, 20))
        
        r_row = ctk.CTkFrame(sf, fg_color="transparent")
        r_row.pack(fill="x", pady=5)
        ctk.CTkLabel(r_row, text="Start:", width=100, anchor="w", font=("Helvetica", 14)).pack(side="left")
        self.range_start = ctk.IntVar(value=settings.get("range_start", parent.range_start.get()))
        ctk.CTkEntry(r_row, textvariable=self.range_start, width=60).pack(side="left", padx=5)
        ctk.CTkLabel(r_row, text="End:", font=("Helvetica", 14)).pack(side="left")
        self.range_end = ctk.IntVar(value=settings.get("range_end", parent.range_end.get()))
        ctk.CTkEntry(r_row, textvariable=self.range_end, width=60).pack(side="left", padx=5)
        
        # Max Tabs & Batch Size
        mt_row = ctk.CTkFrame(sf, fg_color="transparent")
        mt_row.pack(fill="x", pady=5)
        ctk.CTkLabel(mt_row, text="Max Tabs:", width=100, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
        self.max_tabs = ctk.IntVar(value=settings.get("max_tabs", parent.max_tabs.get()))
        ctk.CTkEntry(mt_row, textvariable=self.max_tabs, width=60).pack(side="left", padx=10)
        
        b_row = ctk.CTkFrame(sf, fg_color="transparent")
        b_row.pack(fill="x", pady=5)
        ctk.CTkLabel(b_row, text="Batch Size:", width=100, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
        self.batch_size = ctk.IntVar(value=settings.get("batch_size", parent.batch_size.get()))
        ctk.CTkEntry(b_row, textvariable=self.batch_size, width=60).pack(side="left", padx=10)
        
        # Incognito & New Window
        cb_row = ctk.CTkFrame(sf, fg_color="transparent")
        cb_row.pack(fill="x", pady=15)
        self.incognito = ctk.BooleanVar(value=settings.get("incognito", parent.incognito.get()))
        ctk.CTkSwitch(cb_row, text="Incognito Mode", variable=self.incognito, font=("Helvetica", 14)).pack(side="left", padx=(0, 20))
        self.new_window = ctk.BooleanVar(value=settings.get("new_window", parent.new_window.get()))
        ctk.CTkSwitch(cb_row, text="Force New Window", variable=self.new_window, font=("Helvetica", 14)).pack(side="left")
        
        self.after(50, lambda: self.attributes("-alpha", 1.0))
        
    def _save(self):
        new_settings = {
            "delay": self.delay_var.get(),
            "run_mode": self.run_mode.get(),
            "range_start": self.range_start.get(),
            "range_end": self.range_end.get(),
            "max_tabs": self.max_tabs.get(),
            "batch_size": self.batch_size.get(),
            "incognito": self.incognito.get(),
            "new_window": self.new_window.get()
        }
        self._on_save(self._name, new_settings)
        self.destroy()
class SaveSessionDialog(ctk.CTkToplevel):
    def __init__(self, parent, detected_browsers, on_save):
        super().__init__(parent)
        set_icon(self)
        self.title("Save Browser Session")
        self._on_save = on_save
        self._detected = detected_browsers
        
        W, H = 600, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        ctk.CTkLabel(self, text=" Save Browser Session", font=("Helvetica", 20, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
        
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=10)
        
        installed = [n for n, p in detected_browsers.items() if p != "default"]
        self._browser_var = ctk.StringVar(value=installed[0] if installed else "")
        self._method_var = ctk.StringVar(value="paste")
        
        ctk.CTkLabel(body, text="WHICH BROWSER?", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        bf = ctk.CTkFrame(body, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=8)
        bf.pack(fill="x", pady=(5, 15))
        for name in installed:
            ctk.CTkRadioButton(bf, text=name, variable=self._browser_var, value=name, font=("Helvetica", 13)).pack(anchor="w", padx=15, pady=8)
            
        ctk.CTkLabel(body, text="SAVE METHOD", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        mf = ctk.CTkFrame(body, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=8)
        mf.pack(fill="x", pady=(5, 15))
        for val, label in [("paste", "Paste URLs manually (most reliable)"),
                          ("history", "Read from browser history (Chromium browsers)"),
                          ("debug", "Auto-read via debug port (requires --remote-debugging-port)")]:
            ctk.CTkRadioButton(mf, text=label, variable=self._method_var, value=val, font=("Helvetica", 13)).pack(anchor="w", padx=15, pady=8)
            
        ctk.CTkButton(mf, text=" Pull from Browser Extension", fg_color="#007AFF", hover_color="#005bb5", font=("Helvetica", 13, "bold"), command=self._pull_ext).pack(anchor="w", padx=15, pady=(0, 10))
            
        ctk.CTkLabel(body, text="SESSION NAME (auto-generated if blank)", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        self._name_ent = ctk.CTkEntry(body, font=("Helvetica", 14), height=35)
        self._name_ent.pack(fill="x", pady=(5, 15))
        
        ctk.CTkLabel(body, text="PASTE URLS (one per line)", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w")
        self._txt = ctk.CTkTextbox(body, font=("Courier New", 14))
        self._txt.pack(fill="both", expand=True, pady=(5, 15))
        
        try:
            clip = self.clipboard_get()
            urls = [l.strip() for l in clip.splitlines() if l.strip().startswith("http")]
            if urls: self._txt.insert("1.0", "\n".join(urls))
        except Exception as exc:
            LOGGER.exception("Non-critical operation failed: %s", exc)
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(side="bottom", fill="x", padx=20, pady=20)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="left")
        ctk.CTkButton(foot, text="Save Session", command=self._save, fg_color="#AF52DE", hover_color="#8E33B7").pack(side="right")

    def _save(self):
        browser = self._browser_var.get()
        method = self._method_var.get()
        name = self._name_ent.get().strip()
        urls = []
        
        if method == "paste": urls = self._urls_from_text()
        elif method == "history": urls = self._read_history(browser) or self._urls_from_text()
        elif method == "debug": urls = self._read_debug(browser) or self._urls_from_text()
        
        if not urls: messagebox.showwarning("No URLs", "No valid URLs found. If using History/Debug, ensure the browser is closed or configured correctly."); return
        
        if not name:
            now = datetime.now()
            day_key = now.strftime("%Y%m%d")
            sessions = _load(SESSIONS_FILE, {})
            count = sum(1 for k in sessions if k.startswith(day_key))
            ords = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th"]
            name = f"{now.strftime('%d %b %Y')}    {ords[min(count, 9)]} session"
            
        if not messagebox.askyesno("Confirm", f"Save session '{name}' with {len(urls)} tabs?"): return
        
        self._on_save(name, browser, urls)
        self.destroy()

    def _urls_from_text(self):
        return [u for l in self._txt.get("1.0", "end").splitlines() if (u := normalize_url(l))]

    def _pull_ext(self):
        messagebox.showinfo("Extension", "Please click the 'Elvar Companion' extension icon in your browser and click 'Send to Elvar'. The tabs will appear here automatically.")

    def add_urls_from_ext(self, urls):
        if urls:
            curr = self._txt.get("1.0", "end").strip()
            self._txt.insert("end", ("\n" if curr else "") + "\n".join(urls))
            self._method_var.set("paste")
            self.lift()
            self.focus_force()

class RestoreSessionDialog(ctk.CTkToplevel):
    def __init__(self, parent, name, data, on_restore):
        super().__init__(parent)
        set_icon(self)
        self.attributes("-alpha", 0.0)
        self.title(f"Restore Session    {name}")
        self._name = name
        self._data = data
        self._on_restore = on_restore
        
        W, H = 600, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(hdr, text=f"  Restore: {name}", font=("Helvetica", 20, "bold")).pack(side="left")
        
        self._all_selected = True
        self._toggle_btn = ctk.CTkButton(hdr, text="Deselect All", width=100, command=self._toggle_all, fg_color="#8E8E93", hover_color="#636366")
        self._toggle_btn.pack(side="right")
        
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=15)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="left")
        
        self._run_btn = ctk.CTkButton(foot, text="Restore Selected", command=self._restore_selected, fg_color="#34C759", hover_color="#28A745")
        self._run_btn.pack(side="right")
        
        self._vars = []
        self._load_urls()
        
        self.after(50, lambda: self.attributes("-alpha", 1.0))
        
    def _toggle_all(self):
        self._all_selected = not self._all_selected
        for _, var in self._vars:
            var.set(self._all_selected)
        self._toggle_btn.configure(text="Deselect All" if self._all_selected else "Select All")
        
    def _load_urls(self):
        for w in self._scroll.winfo_children(): w.destroy()
        self._vars.clear()
        
        urls = self._data.get("urls", [])
        for url in urls:
            row = ctk.CTkFrame(self._scroll, fg_color=("#F2F2F7", "#2C2C2E"), corner_radius=8)
            row.pack(fill="x", pady=4)
            
            var = ctk.BooleanVar(value=True)
            self._vars.append((url, var))
            
            cb = ctk.CTkCheckBox(row, text="", variable=var, width=24, height=24)
            cb.pack(side="left", padx=10, pady=10)
            
            ctk.CTkLabel(row, text=url, font=("Helvetica", 14), anchor="w").pack(side="left", fill="x", expand=True, padx=5)
            
    def _restore_selected(self):
        selected_urls = [url for url, var in self._vars if var.get()]
        if not selected_urls:
            messagebox.showwarning("No Selection", "Please select at least one URL to restore.")
            return
            
        self._on_restore(self._name, selected_urls, self._data.get("browser", "System Default"))
        self.destroy()

    def _read_debug(self, browser):
        port = CHROME_DEBUG_PORTS.get(browser, 9222)
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2)
            tabs = json.loads(r.read())
            return [t["url"] for t in tabs if t.get("type") == "page" and t.get("url", "").startswith("http")]
        except Exception: return []

    def _read_history(self, browser):
        hp = BROWSER_HISTORY_PATHS.get(browser)
        if not hp or not os.path.exists(hp): return []
        import tempfile, sqlite3
        tmp = os.path.join(tempfile.gettempdir(), "flux_hist.db")
        try:
            shutil.copy2(hp, tmp)
            conn = sqlite3.connect(tmp)
            cur = conn.cursor()
            cur.execute("SELECT url FROM urls ORDER BY last_visit_time DESC LIMIT 50")
            rows = cur.fetchall()
            conn.close()
            return [r[0] for r in rows if r[0].startswith("http")]
        except Exception: return []

class WorkflowCard(ctk.CTkFrame):
    def __init__(self, parent, name, data, callbacks, is_protected_view=False, password=None, batch_var=None, **kw):
        super().__init__(parent, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10, **kw)
        self._name = name
        self._data = data
        self._callbacks = callbacks
        self._is_protected_view = is_protected_view
        self._password = password
        
        fp = data.get("path", "")
        self._links = []
        try:
            content = read_file_content(fp, data.get("is_protected", False), password)
            for line in content.splitlines():
                u = normalize_url(line)
                if u: self._links.append(u)
        except Exception as exc:
            LOGGER.exception("Non-critical operation failed: %s", exc)
        
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=15, pady=12)
        
        if batch_var is not None:
            ctk.CTkCheckBox(top, text="", variable=batch_var, width=24, height=24).pack(side="left", padx=(0, 10))
            
        pinned = data.get("pinned", False)
        if pinned and not is_protected_view:
            ctk.CTkLabel(top, text="\U0001F4CC", font=("Helvetica", 16), text_color="#FF9500").pack(side="left", padx=(0, 8))
            
        if is_protected_view:
            ctk.CTkLabel(top, text="\U0001F512", font=("Helvetica", 16), text_color="#FFCC00").pack(side="left", padx=(0, 8))
            
        ctk.CTkLabel(top, text=name, font=("Helvetica", 16, "bold")).pack(side="left")
        
        ctk.CTkLabel(top, text=f"{len(self._links)} links", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D"),
                     fg_color=("#F2F2F7", "#2C2C2E"), corner_radius=6).pack(side="left", padx=10, ipadx=6, ipady=2)
                     
        runs = data.get("runs", 0)
        if runs:
            ctk.CTkLabel(top, text=f" {runs}", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=5)
            
        if data.get("is_hidden"):
            ctk.CTkLabel(top, text="Hidden", font=("Helvetica", 12, "bold"), text_color=("#FF3B30", "#FF453A"), fg_color=("#FFD8D6", "#3F1D1D"), corner_radius=6).pack(side="left", padx=5, ipadx=6, ipady=2)
            
        if data.get("is_queue"):
            ctk.CTkLabel(top, text="Queue", font=("Helvetica", 12, "bold"), text_color=("#AF52DE", "#BF5AF2"), fg_color=("#E8D1FF", "#2D1B4E"), corner_radius=6).pack(side="left", padx=5, ipadx=6, ipady=2)
            
        if data.get("is_task_list"):
            ctk.CTkLabel(top, text="Task List", font=("Helvetica", 12, "bold"), text_color=("#34C759", "#30D158"), fg_color=("#D4F5E4", "#143628"), corner_radius=6).pack(side="left", padx=5, ipadx=6, ipady=2)
            
        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.pack(side="right")
        
        pin_sym = "\U0001F4CD" if pinned else "\U0001F4CC"
        
        if is_protected_view:
            buttons = [
                ("\u23F5", "run", "green", "Run Workflow"),
                ("\u2611", "run_selected", "blue", "Run Selected"),
                (pin_sym, "pin", "orange", "Pin / Unpin"),
                ("\u2398", "duplicate", "teal", "Duplicate"),
                ("\U0001F441", "toggle_hidden", "#3B82F6", "Toggle Hidden"),
                ("\U0001F517", "ping", "#F43F5E", "Check Links"),
                ("\U0001F513", "unprotect", "#EAB308", "Remove Protection"),
                ("\u270E", "edit", "#007AFF", "Edit URLs"),
                ("\u2699", "settings", "#8E8E93", "Settings"),
                ("\u25A4", "rename", "purple", "Rename"),
                ("\u2B73", "export", "gray50", "Export"),
                ("\U0001F5D1", "delete", "red", "Delete")
            ]
        else:
            buttons = [
                ("\u23F5", "run", "green", "Run Workflow"),
                ("\u2611", "run_selected", "blue", "Run Selected"),
                (pin_sym, "pin", "orange", "Pin / Unpin"),
                ("\u2398", "duplicate", "teal", "Duplicate"),
                ("\U0001F517", "ping", "#F43F5E", "Check Links"),
                ("\u270E", "edit", "#007AFF", "Edit URLs"),
                ("\u2699", "settings", "#8E8E93", "Settings"),
                ("\U0001F512", "protect", "#EAB308", "Protect"),
                ("\u25A4", "rename", "purple", "Rename"),
                ("\u2B73", "export", "gray50", "Export"),
                ("\U0001F5D1", "delete", "red", "Delete")
            ]
            
        if data.get("is_task_list"):
            buttons.insert(1, ("\U0001F4CB", "run", "#10B981", "Open Task List"))
        if data.get("is_queue"):
            buttons.insert(1, ("\u2632", "run", "#8B5CF6", "Run Queue"))
        
        for sym, key, clr, tip in buttons:
            if key in callbacks:
                b = ctk.CTkButton(btn_row, text=sym, width=30, height=28, fg_color="transparent",
                                  text_color=clr, hover_color=("#E5E5EA", "#3A3A3C"), font=("Helvetica", 18),
                                  command=lambda k=key, n=name: callbacks[k](n))
                b.pack(side="left", padx=2)
                CTkTooltip(b, tip)
            
        sub = ctk.CTkFrame(self, fg_color="transparent")
        sub.pack(fill="x", padx=15, pady=(0, 12))
        
        tags = data.get("tags", [])
        if tags:
            tag_frame = ctk.CTkFrame(sub, fg_color="transparent")
            tag_frame.pack(side="left", padx=(0, 10))
            for t in tags:
                ctk.CTkLabel(tag_frame, text=f"#{t}", font=("Helvetica", 10), text_color="#32ADE6", fg_color=("#E5E5EA", "#3A3A3C"), corner_radius=4).pack(side="left", padx=2, ipadx=4)
        
        fname = os.path.basename(fp) if fp else "no file"
        last = data.get("last_run", "never")
        notes = data.get("notes", "")
        sub_txt = f"{fname} - last: {last}"
        if notes: sub_txt += f" - {notes[:40]}"
        
        ctk.CTkLabel(sub, text=sub_txt, font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left")
        
        self._prog = ctk.CTkProgressBar(self, height=4, fg_color=("#F2F2F7", "#2C2C2E"), progress_color="#007AFF")
        self._prog.pack(fill="x", side="bottom")
        self._prog.set(0)

    def set_progress(self, frac):
        try: self._prog.set(frac)
        except Exception as exc:
            LOGGER.exception("Non-critical operation failed: %s", exc)

class RunQueueDialog(ctk.CTkToplevel):
    def __init__(self, parent, name, data, on_run, password=None):
        super().__init__(parent)
        set_icon(self)
        self.attributes("-alpha", 0.0)
        is_queue = data.get("is_queue", False)
        title_prefix = "Run Queue" if is_queue else "Run Selected"
        self.title(f"{title_prefix}    {name}")
        self._name = name
        self._data = data
        self._fp = data.get("path", "")
        self._on_run = on_run
        self._password = password
        
        W, H = 600, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(hdr, text=f"  {title_prefix}: {name}", font=("Helvetica", 20, "bold")).pack(side="left")
        
        self._all_selected = True
        self._toggle_btn = ctk.CTkButton(hdr, text="Deselect All", width=100, command=self._toggle_all, fg_color="#8E8E93", hover_color="#636366")
        self._toggle_btn.pack(side="right")
        
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=15)
        ctk.CTkButton(foot, text="Cancel", command=self.destroy, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="left")
        
        self._delete_var = ctk.BooleanVar(value=is_queue)
        ctk.CTkCheckBox(foot, text="Delete after opening", variable=self._delete_var, font=("Helvetica", 12)).pack(side="left", padx=20)
        
        self._run_btn = ctk.CTkButton(foot, text="Run Selected", command=self._run_selected, fg_color="#34C759", hover_color="#28A745")
        self._run_btn.pack(side="right")
        
        self._vars = []
        self._load_tasks()
        
        self.after(50, lambda: self.attributes("-alpha", 1.0))
        
    def _toggle_all(self):
        self._all_selected = not self._all_selected
        for _, var in self._vars:
            var.set(self._all_selected)
        self._toggle_btn.configure(text="Deselect All" if self._all_selected else "Select All")
        
    def _load_tasks(self):
        for w in self._scroll.winfo_children(): w.destroy()
        self._vars.clear()
        
        try:
            content = read_file_content(self._fp, self._data.get("is_protected", False), self._password)
            lines = content.splitlines()
            
            for i, line in enumerate(lines):
                url = normalize_url(line)
                if not url: continue
                
                row = ctk.CTkFrame(self._scroll, fg_color=("#F2F2F7", "#2C2C2E"), corner_radius=8)
                row.pack(fill="x", pady=4)
                
                var = ctk.BooleanVar(value=True)
                self._vars.append((url, var))
                
                cb = ctk.CTkCheckBox(row, text="", variable=var, width=24, height=24)
                cb.pack(side="left", padx=10, pady=10)
                
                ctk.CTkLabel(row, text=url, font=("Helvetica", 14), anchor="w").pack(side="left", fill="x", expand=True, padx=5)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
            
    def _run_selected(self):
        selected_urls = [url for url, var in self._vars if var.get()]
        if not selected_urls:
            messagebox.showwarning("No Selection", "Please select at least one URL to run.")
            return
            
        self._on_run(self._name, selected_urls, self._delete_var.get())
        self.destroy()
class TaskListDialog(ctk.CTkToplevel):
    def __init__(self, parent, name, data, on_close, password=None):
        super().__init__(parent)
        set_icon(self)
        self.attributes("-alpha", 0.0)
        self.title(f"Task List    {name}")
        self._name = name
        self._data = data
        self._fp = data.get("path", "")
        self._on_close = on_close
        self._password = password
        
        W, H = 600, 500
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")
        self.transient(parent)
        self.grab_set()
        self.focus_force()
        
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(hdr, text=f"\u270E  {name}", font=("Helvetica", 20, "bold")).pack(side="left")
        
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        self._load_tasks()
        
        self.after(50, lambda: self.attributes("-alpha", 1.0))
        
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=20, pady=15)
        ctk.CTkButton(foot, text="Close", command=self._close, fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF")).pack(side="right")
                      
    def _load_tasks(self):
        for w in self._scroll.winfo_children(): w.destroy()
        
        try:
            content = read_file_content(self._fp, self._data.get("is_protected", False), self._password)
            self._lines = content.splitlines(True)
        except Exception as exc:
            LOGGER.exception("Task list load failed: %s", exc)
            self._lines = []
            
        self._urls = [l for l in self._lines if normalize_url(l)]
        
        if not self._urls:
            ctk.CTkLabel(self._scroll, text="No tasks remaining! ", font=("Helvetica", 16), text_color="#34C759").pack(pady=40)
            return
            
        for i, url in enumerate(self._urls):
            row = ctk.CTkFrame(self._scroll, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=8)
            row.pack(fill="x", pady=4)
            
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(row, text="", variable=var, width=20, command=lambda u=url, v=var, r=row: self._on_check(u, v, r))
            cb.pack(side="left", padx=(15, 5), pady=10)
            
            ctk.CTkLabel(row, text=url, font=("Helvetica", 14), anchor="w").pack(side="left", fill="x", expand=True, padx=5)
            
            ctk.CTkButton(row, text="Open", width=60, height=28, fg_color="#007AFF", 
                          command=lambda u=url: self._open_url(u)).pack(side="right", padx=15)
                          
    def _open_url(self, url):
        import webbrowser
        webbrowser.open(url)
        
    def _on_check(self, url, var, row_frame):
        if var.get():
            # Strike-through animation
            for child in row_frame.winfo_children():
                if isinstance(child, ctk.CTkLabel) and child.cget("text") == url:
                    # We can't easily do strikethrough in ctk, but we can change color
                    child.configure(text_color="#8E8E93")
            
            def finish_delete():
                try:
                    content = read_file_content(self._fp, self._data.get("is_protected", False), self._password)
                    lines = content.splitlines(True)
                    
                    new_lines = []
                    removed = False
                    for l in lines:
                        if not removed and normalize_url(l) == url:
                            removed = True
                            continue
                        new_lines.append(l)
                        
                    write_file_content(self._fp, "".join(new_lines), self._data.get("is_protected", False), self._password)
                        
                    self._load_tasks()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
                    var.set(False)
            
            self.after(400, finish_delete)
                
    def _close(self):
        self._on_close()
        self.destroy()
def _read_workflow_urls_for_extension(workflows_file):
    wf_list = []
    wfs = _load(workflows_file, {})
    for name, data in wfs.items():
        if isinstance(data, str):
            data = {"path": data}
        is_protected = data.get("is_protected", False)
        urls = []
        if not is_protected and os.path.exists(data.get("path", "")):
            try:
                with open(data["path"], "r", encoding="utf-8") as f:
                    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except Exception as exc:
                LOGGER.exception("Failed reading workflow URLs for extension (%s): %s", name, exc)
        wf_list.append({"name": name, "is_protected": is_protected, "urls": urls})
    return wf_list


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Elvar - by Ash")
        self.minsize(1100, 750)
        self.configure(fg_color=("#F5F5F7", "#121214"))
        
        make_tray_icon()
        set_icon(self)
        
        self.sel_file = ctk.StringVar(value="no file selected")
        self.sel_browser = ctk.StringVar(value="Opera GX")
        self.incognito = ctk.BooleanVar(value=True)
        self.new_window = ctk.BooleanVar(value=False)
        self.delay_var = ctk.DoubleVar(value=0.2)
        self.custom_exe = ctk.StringVar()
        
        self._running = False
        self._stop_flag = False
        self._pause_flag = False
        self._total_tabs = 0
        self._msg_queue = queue.Queue()
        self._last_run_wf = None
        
        self._workflows = _load(WORKFLOWS_FILE, {})
        self._sessions = _load(SESSIONS_FILE, {})
        self._settings = _load(SETTINGS_FILE, {})
        self._history = _load(HISTORY_FILE, [])
        self._detected = auto_detect()
        self._app_dir = APP_DIR
        self._gdrive_ok = GDRIVE_OK

        migrated = ensure_auth_settings(self._settings, LOGGER)
        current_schema = int(self._settings.get("schema_version", 1))
        if current_schema < SETTINGS_SCHEMA_VERSION:
            self._settings["schema_version"] = SETTINGS_SCHEMA_VERSION
            migrated = True
        if not self._settings.get("api_token"):
            self._settings["api_token"] = make_protected_key()
            migrated = True
        if migrated:
            _save(SETTINGS_FILE, self._settings)

        s = self._settings

        self.run_mode = ctk.StringVar(value="sequential")
        self.batch_size = ctk.IntVar(value=5)
        self.skip_every_n = ctk.IntVar(value=2)
        self.dry_run = ctk.BooleanVar(value=False)
        self.countdown_sec = ctk.IntVar(value=0)
        self.strip_utm_var = ctk.BooleanVar(value=False)
        self.sound_var = ctk.BooleanVar(value=False)
        self.auto_pin_var = ctk.BooleanVar(value=False)
        self.auto_lock_var = ctk.BooleanVar(value=s.get("auto_lock", True))
        self.disable_log_var = ctk.BooleanVar(value=s.get("disable_log", False))
        self.retry_failed = ctk.BooleanVar(value=False)
        self.max_tabs = ctk.IntVar(value=0)
        self.range_start = ctk.IntVar(value=1)
        self.range_end = ctk.IntVar(value=0)
        
        if s.get("browser") in BROWSER_PATHS: self.sel_browser.set(s["browser"])
        if s.get("incognito") is not None: self.incognito.set(s["incognito"])
        if s.get("new_window") is not None: self.new_window.set(s["new_window"])
        if s.get("delay") is not None: self.delay_var.set(s["delay"])
        self._total_tabs = s.get("total_tabs", 0)
        if s.get("sound"): self.sound_var.set(s["sound"])
        if s.get("strip_utm"): self.strip_utm_var.set(s["strip_utm"])
        if s.get("auto_pin"): self.auto_pin_var.set(s["auto_pin"])
        
        self.theme_var = ctk.StringVar(value=s.get("theme", "Dark"))
        ctk.set_appearance_mode(self.theme_var.get())
        
        self.after(100, self._process_queue)
        threading.Thread(target=start_ext_server, args=(self._msg_queue, WORKFLOWS_FILE, _read_workflow_urls_for_extension, lambda: self._settings.get("api_token"), LOGGER), daemon=True).start()
        self._build()
        
        geo = self._settings.get("geometry")
        if geo:
            try: self.geometry(geo)
            except Exception: self.state("zoomed")
        else:
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
            self.state("zoomed")
            
        self.deiconify()
        self._setup_hotkeys()
        self._setup_tray()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Control-k>", lambda e: self._open_palette())
        self.bind("<Control-o>", lambda e: self._pick_file())
        self.bind("<Control-Return>", lambda e: self._run())
        self.bind("<Escape>", lambda e: self._stop())
        self.bind("<Configure>", self._on_resize)
        self._setup_mouse_wheel()

    def _process_queue(self):
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                kind = msg.get("kind")
                if kind == "ask":
                    result = messagebox.askyesno(msg["title"], msg["text"])
                    if msg.get("callback"): msg["callback"](result)
                elif kind == "error":
                    messagebox.showerror(msg["title"], msg["text"])
                    if msg.get("callback"): msg["callback"]()
                elif kind == "call": msg["fn"](*msg.get("args", ()))
                elif kind == "ext_get_protected":
                    event = msg.get("event")
                    result = msg.get("result", {})
                    name = msg.get("name")
                    pwd = msg.get("password")
                    try:
                        if self._verify_protected_password(pwd):
                            wf_data = self._workflows.get(name)
                            if wf_data:
                                fp = wf_data.get("path", "")
                                if fp and os.path.exists(fp):
                                    content = read_file_content(fp, True, self._protected_secret())
                                    urls = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
                                    result["urls"] = urls
                                else:
                                    result["status"] = "error"
                            else:
                                result["status"] = "error"
                        else:
                            result["status"] = "error"
                            result["message"] = "Incorrect password"
                    except Exception as e:
                        LOGGER.exception("Failed ext_get_protected handling: %s", e)
                        result["status"] = "error"
                    finally:
                        if event: event.set()
                elif kind == "ext_import":
                    data = msg["data"]
                    event = msg.get("event")
                    result = msg.get("result", {})
                    target = data.get("target", "_new_session")
                    name = data.get("name", "Extension Import")
                    urls = data.get("urls", [])
                    metadata = data.get("metadata", [])
                    save_type = data.get("save_type", "workflow")
                    try:
                        if urls:
                            if target == "_new_session" and hasattr(self, "_save_session_dlg") and self._save_session_dlg and self._save_session_dlg.winfo_exists():
                                self._save_session_dlg.add_urls_from_ext(urls)
                                Toast(self, "Tabs received from extension!", "green")
                            elif save_type == "session":
                                self._sessions[name] = {"browser": "System Default", "urls": urls, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
                                _save(SESSIONS_FILE, self._sessions)
                                self._render_sessions()
                                Toast(self, f"Saved session '{name}'!", "purple")
                            else:
                                if target != "_new_workflow" and target != "_new_session" and target in self._workflows:
                                    wf_data = self._workflows[target]
                                    fp = wf_data.get("path", "")
                                    if fp:
                                        content = read_file_content(fp, wf_data.get("is_protected", False), self._protected_secret())
                                        new_content = content + "\n" + "\n".join(urls) + "\n"
                                        write_file_content(fp, new_content, wf_data.get("is_protected", False), self._protected_secret())
                                        
                                        if name and name != target and name not in self._workflows:
                                            self._workflows[name] = self._workflows.pop(target)
                                            _save(WORKFLOWS_FILE, self._workflows)
                                            self._render_wf()
                                            Toast(self, f"Added {len(urls)} tabs and renamed to '{name}'!", "green")
                                        else:
                                            Toast(self, f"Added {len(urls)} tabs to '{target}'!", "green")
                                else:
                                    is_protected = data.get("is_protected", False)
                                    password = self._protected_secret()
                                    
                                    if is_protected and not self._has_protected_password():
                                        messagebox.showwarning("No Password", "Cannot save as protected because no password is set in Settings. Saving as regular workflow.")
                                        is_protected = False
                                        
                                    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
                                    fp = os.path.join(APP_DIR, f"{safe}.txt")
                                    
                                    content_lines = []
                                    if metadata:
                                        current_group = None
                                        for item in metadata:
                                            grp = item.get("group")
                                            if grp and grp != current_group:
                                                current_group = grp
                                                content_lines.append(f"\n# Group: {current_group}")
                                            content_lines.append(item.get("url", ""))
                                    else:
                                        content_lines = urls
                                        
                                    content_str = "\n".join(content_lines) + "\n"
                                    write_file_content(fp, content_str, is_protected, password)
                                    
                                    self._workflows[name] = {
                                        "path": fp, "runs": 0, "last_run": None, "pinned": False,
                                        "is_protected": is_protected, "is_hidden": False
                                    }
                                    _save(WORKFLOWS_FILE, self._workflows)
                                    if is_protected and hasattr(self, "_render_protected"):
                                        self._render_protected()
                                    self._render_wf()
                                    Toast(self, f"Imported '{name}' from browser!", "green")
                    except Exception as e:
                        result["status"] = "error"
                        result["message"] = str(e)
                    finally:
                        if event: event.set()
                elif kind == "ext_launch":
                    name = msg.get("name")
                    incognito = msg.get("incognito", False)
                    new_window = msg.get("new_window", False)
                    specific_urls = msg.get("specific_urls")
                    if name and name in self._workflows:
                        if specific_urls:
                            self._run_queue_selected(name, specific_urls, delete_after=False, ext_incognito=incognito, ext_new_window=new_window)
                        else:
                            self._run_workflow(name, ext_incognito=incognito, ext_new_window=new_window)
                        Toast(self, f"Launched '{name}' from browser!", "green")
                elif kind == "ext_add_dialog":
                    url = msg.get("url")
                    title = msg.get("title")
                    self._show_add_to_workflow_dialog(url, title)
        except queue.Empty: pass
        self.after(100, self._process_queue)

    def _on_resize(self, e):
        if e.widget is self: self._settings["geometry"] = self.geometry()

    def _open_data_folder(self):
        open_folder(self._app_dir)

    def _setup_mouse_wheel(self):
        try:
            self.bind_all("<MouseWheel>", self._on_mouse_wheel, add="+")
            self.bind_all("<Button-4>", self._on_mouse_wheel, add="+")
            self.bind_all("<Button-5>", self._on_mouse_wheel, add="+")
        except Exception as exc:
            LOGGER.exception("Mouse wheel setup failed: %s", exc)

    def _find_scroll_canvas(self, widget):
        w = widget
        while w is not None:
            if hasattr(w, "_parent_canvas"):
                return w._parent_canvas
            if isinstance(w, tk.Canvas):
                return w
            w = getattr(w, "master", None)
        return None

    def _on_mouse_wheel(self, event):
        target = self.winfo_containing(event.x_root, event.y_root) or event.widget
        canvas = self._find_scroll_canvas(target)
        if canvas is None:
            return

        if hasattr(event, "num") and event.num in (4, 5):
            steps = -1 if event.num == 4 else 1
        else:
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return
            steps = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)

        try:
            canvas.yview_scroll(steps, "units")
            return "break"
        except Exception:
            return

    def _get_tray_menu(self):
        def make_run_action(w):
            return lambda icon, item: self.after(0, lambda: self._run_workflow(w))
            
        items = [pystray.MenuItem("Show Elvar", self._show_window, default=True), pystray.Menu.SEPARATOR]
        for wf in list(self._workflows.keys())[:5]:
            items.append(pystray.MenuItem(f" Run: {wf}", make_run_action(wf)))
        items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings", lambda icon, item: self.after(0, lambda: self._switch("settings"))),
            pystray.MenuItem("Quit", lambda icon, item: self.after(0, self._quit_app))
        ])
        return pystray.Menu(*items)

    def _setup_tray(self):
        if not TRAY_OK: return
        img = make_tray_icon()
        if not img: return
        self._tray = pystray.Icon("Elvar", img, "Elvar  by Ash", self._get_tray_menu())
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _show_window(self, icon=None, item=None):
        self.deiconify()
        self.state("zoomed")
        self.focus_force()

    def _hide_to_tray(self):
        if self.auto_lock_var.get():
            self._lock_protected()
        if TRAY_OK:
            self.withdraw()
            Toast(self, "Elvar running in tray", "green")
        else:
            self.iconify()

    def _setup_hotkeys(self):
        if not KB_OK: return
        try:
            kb.add_hotkey("ctrl+shift+t", lambda: self.after(0, self._open_palette))
            kb.add_hotkey("ctrl+shift+o", lambda: self.after(0, self._show_window))
            kb.add_hotkey("ctrl+shift+r", lambda: self.after(0, self._run_last_hotkey))
        except Exception as exc:
            LOGGER.exception("Hotkey setup failed: %s", exc)

    def _run_last_hotkey(self):
        if self._last_run_wf and self._last_run_wf in self._workflows:
            self._run_workflow(self._last_run_wf)
            Toast(self, f"Running: {self._last_run_wf}", "green")

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("Running", "Tabs are opening. Close anyway?"): return
        if TRAY_OK:
            if messagebox.askyesno("Minimize to Tray?", "Minimize to system tray instead of closing?"):
                self._hide_to_tray()
                return
        self._quit_app()

    def _quit_app(self, icon=None, item=None):
        self._save_settings()
        try:
            if TRAY_OK and hasattr(self, "_tray"): self._tray.stop()
        except Exception as exc:
            LOGGER.exception("Non-critical operation failed: %s", exc)
        self.destroy()

    def _save_settings(self):
        self._settings.update({
            "browser": self.sel_browser.get(),
            "incognito": self.incognito.get(),
            "new_window": self.new_window.get(),
            "delay": self.delay_var.get(),
            "total_tabs": self._total_tabs,
            "sound": self.sound_var.get(),
            "strip_utm": self.strip_utm_var.get(),
            "auto_pin": self.auto_pin_var.get(),
            "auto_lock": self.auto_lock_var.get(),
            "disable_log": self.disable_log_var.get(),
            "theme": self.theme_var.get(),
            "schema_version": SETTINGS_SCHEMA_VERSION
        })
        _save(SETTINGS_FILE, self._settings)

    def _protected_secret(self):
        return self._settings.get("protected_key")

    def _has_protected_password(self):
        return has_password(self._settings)

    def _verify_protected_password(self, plain_password):
        return verify_password_from_settings(self._settings, plain_password)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1)
        
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        try:
            from PIL import Image
            img_path = _resource_path("elvar_icon.ico")
            if os.path.exists(img_path):
                logo_img = ctk.CTkImage(light_image=Image.open(img_path), dark_image=Image.open(img_path), size=(28, 28))
                ctk.CTkLabel(logo_frame, text="", image=logo_img).pack(side="left", padx=(0, 10))
        except Exception as exc:
            LOGGER.debug("Sidebar icon load failed: %s", exc)

        ctk.CTkLabel(logo_frame, text="Elvar", font=("Helvetica", 24, "bold"), text_color="#007AFF").pack(side="left")
        
        gh_lbl = ctk.CTkLabel(self.sidebar, text="by Ash - GitHub", font=("Helvetica", 12, "underline"), text_color=("#8E8E93", "#98989D"), cursor="hand2")
        gh_lbl.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")
        gh_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/get-elvar"))
        
        self._tab_btns = {}
        tab_defs = [("workflows", "\u2318 Workflows"), ("launcher", "\u25B6 Launcher"), ("sessions", "\u25C9 Sessions"),
                    ("history", "\u23F1 History"), ("analytics", "\U0001F4CA Analytics"), ("protected", "\U0001F512 Protected")]
                    
        for i, (key, label) in enumerate(tab_defs, start=3):
            btn = ctk.CTkButton(self.sidebar, text=label, font=("Helvetica", 15), anchor="w",
                                fg_color="transparent", text_color=("#000000", "#FFFFFF"),
                                hover_color=("#E5E5EA", "#3A3A3C"), height=36,
                                command=lambda k=key: self._switch(k))
            btn.grid(row=i, column=0, padx=10, pady=5, sticky="ew")
            self._tab_btns[key] = btn
            
        # Spacer
        ctk.CTkFrame(self.sidebar, fg_color="transparent").grid(row=9, column=0, sticky="nsew")
        
        settings_btn = ctk.CTkButton(self.sidebar, text="\u2699 Settings", font=("Helvetica", 15), anchor="w",
                            fg_color="transparent", text_color=("#000000", "#FFFFFF"),
                            hover_color=("#E5E5EA", "#3A3A3C"), height=36,
                            command=lambda: self._switch("settings"))
        settings_btn.grid(row=10, column=0, padx=10, pady=5, sticky="ew")
        self._tab_btns["settings"] = settings_btn
            
        self._total_lbl = ctk.CTkLabel(self.sidebar, text=f"\u2191 {self._total_tabs} tabs lifetime", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D"))
        self._total_lbl.grid(row=11, column=0, padx=20, pady=(10, 5), sticky="w")
        
        ctk.CTkButton(self.sidebar, text="\u22DF Tray", font=("Helvetica", 12), fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF"), command=self._hide_to_tray).grid(row=12, column=0, padx=20, pady=(0, 5), sticky="ew")
        
        ctk.CTkButton(self.sidebar, text="Mini Widget", font=("Helvetica", 12), fg_color="transparent",
                      border_width=1, text_color=("#000000", "#FFFFFF"), command=self._mini_widget).grid(row=13, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        
        self._pages = {}
        for key, _ in tab_defs:
            frame = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)
            self._pages[key] = frame
            
        self._pages["settings"] = ctk.CTkFrame(self.main_container, fg_color="transparent", corner_radius=0)
            
        self._build_workflows(self._pages["workflows"])
        self._build_launcher(self._pages["launcher"])
        self._build_sessions(self._pages["sessions"])
        self._build_history(self._pages["history"])
        self._build_analytics(self._pages["analytics"])
        self._build_protected(self._pages["protected"])
        self._build_settings(self._pages["settings"])
        
        self._switch("workflows")

    def _switch(self, key):
        for k, f in self._pages.items(): 
            f.place_forget()
            
        target_frame = self._pages[key]
        
        # Simple slide-up animation
        def animate(step=0):
            if step <= 10:
                offset = 0.05 * (1 - (step / 10))
                target_frame.place(relx=0, rely=offset, relwidth=1, relheight=1)
                self.after(10, lambda: animate(step + 1))
            else:
                target_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
                
        animate(0)
        
        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(fg_color=("#E5E5EA", "#3A3A3C"), text_color="#007AFF")
            else:
                btn.configure(fg_color="transparent", text_color=("#000000", "#FFFFFF"))

    #  WORKFLOWS PAGE 
    def _build_workflows(self, parent):
        return build_workflows(self, parent)
        
    def _toggle_batch_mode(self):
        self._batch_mode = not self._batch_mode
        if self._batch_mode:
            self._batch_btn.configure(fg_color="#007AFF", text_color="#FFFFFF")
            self._wf_scroll.pack_forget()
            self._batch_actions_frame.pack(fill="x", padx=30, pady=(0, 20), side="bottom")
            self._wf_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        else:
            self._batch_btn.configure(fg_color="transparent", text_color=("#000000", "#FFFFFF"))
            self._batch_actions_frame.pack_forget()
            self._batch_vars.clear()
        self._render_wf()
        
    def _batch_select_all(self):
        all_selected = all(var.get() for var in self._batch_vars.values())
        for var in self._batch_vars.values():
            var.set(not all_selected)
            
    def _batch_delete(self):
        selected = [name for name, var in self._batch_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one workflow to delete.")
            return
        if messagebox.askyesno("Delete Workflows", f"Are you sure you want to delete {len(selected)} workflows?"):
            for name in selected:
                if name in self._workflows:
                    del self._workflows[name]
            _save(WORKFLOWS_FILE, self._workflows)
            self._render_wf()
            Toast(self, f"Deleted {len(selected)} workflows", "red")
            
    def _batch_export(self):
        selected = [name for name, var in self._batch_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("No Selection", "Please select at least one workflow to export.")
            return
            
        fp = filedialog.asksaveasfilename(title="Export Selected Workflows", defaultextension=".zip", filetypes=[("ZIP files", "*.zip")])
        if not fp: return
        
        try:
            with zipfile.ZipFile(fp, 'w') as zf:
                for name in selected:
                    data = self._workflows.get(name, {})
                    if isinstance(data, str): data = {"path": data}
                    path = data.get("path", "")
                    if os.path.exists(path):
                        zf.write(path, os.path.basename(path))
            Toast(self, f"Exported {len(selected)} workflows to {os.path.basename(fp)}", "green")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def _sorted_workflows(self):
        items = [(k, v) for k, v in self._workflows.items() if not (isinstance(v, dict) and (v.get("is_hidden", False) or v.get("is_protected", False)))]
        sort = self._sort_var.get()
        if sort == "name": items.sort(key=lambda x: x[0].lower())
        elif sort == "runs": items.sort(key=lambda x: (x[1].get("runs", 0) if isinstance(x[1], dict) else 0), reverse=True)
        elif sort == "last_run": items.sort(key=lambda x: (x[1].get("last_run") or "") if isinstance(x[1], dict) else "", reverse=True)
        elif sort == "links":
            def lc(item):
                data = item[1]
                fp = (data if isinstance(data, str) else data.get("path", ""))
                try:
                    with open(fp, "r", encoding="utf-8") as f: return sum(1 for l in f if normalize_url(l))
                except: return 0
            items.sort(key=lc, reverse=True)
            
        if self._show_pinned_first.get():
            pinned = [(k, v) for k, v in items if isinstance(v, dict) and v.get("pinned")]
            unpinned = [(k, v) for k, v in items if not (isinstance(v, dict) and v.get("pinned"))]
            items = pinned + unpinned
        return items

    def _render_wf(self):
        q = self._wf_search.get().strip().lower()
        for w in self._wf_scroll.winfo_children(): w.destroy()
        self._wf_cards.clear()
        
        matches = [(k, v) for k, v in self._sorted_workflows() if not q or q in k.lower()]
        self._wf_count_lbl.configure(text=f"  {len(self._workflows)} saved")
        
        if hasattr(self, '_update_mini_widget'):
            self._update_mini_widget()
        if hasattr(self, '_update_quick_select'):
            self._update_quick_select()
            
        if not matches:
            ctk.CTkLabel(self._wf_scroll, text="No workflows match." if q else "No workflows yet.", font=("Helvetica", 18), text_color=("#8E8E93", "#98989D")).pack(pady=40)
            return
            
        cbs = {"run": self._run_workflow, "delete": self._del_workflow, "rename": self._rename_workflow,
               "pin": self._pin_workflow, "duplicate": self._duplicate_workflow, "export": self._export_workflow_menu,
               "edit": self._open_editor, "refresh": self._render_wf, "protect": self._protect_workflow,
               "ping": self._ping_workflow, "settings": self._workflow_settings, "run_selected": self._run_selected_workflow}
               
        for name, data in matches:
            if isinstance(data, str): data = {"path": data, "runs": 0, "last_run": None}
            
            batch_var = None
            if self._batch_mode:
                if name not in self._batch_vars:
                    self._batch_vars[name] = ctk.BooleanVar(value=False)
                batch_var = self._batch_vars[name]
                
            card = WorkflowCard(self._wf_scroll, name, data, callbacks=cbs, password=self._protected_secret(), batch_var=batch_var)
            card.pack(fill="x", pady=6, padx=10)
            self._wf_cards[name] = card

    def _new_workflow(self):
        NewWorkflowDialog(self, on_create=self._on_wf_created, existing_names=list(self._workflows.keys()))

    def _new_queue(self):
        dialog = NewWorkflowDialog(self, on_create=self._on_wf_created, existing_names=list(self._workflows.keys()))
        dialog._type_var.set("queue")

    def _on_wf_created(self, name, fp, color=None, notes="", tags=None, flags_data=None):
        if tags is None: tags = []
        if flags_data is None: flags_data = {}
        
        self._workflows[name] = {
            "path": fp, "runs": 0, "last_run": None, "color": color, 
            "notes": notes, "tags": tags, "pinned": False,
            "is_queue": flags_data.get("is_queue", False),
            "is_task_list": flags_data.get("is_task_list", False),
            "hide_from_history": flags_data.get("hide_from_history", False),
            "is_protected": flags_data.get("is_protected", False),
            "is_hidden": flags_data.get("is_hidden", False)
        }
        _save(WORKFLOWS_FILE, self._workflows)
        _auto_backup(self._workflows)
        self._render_wf()
        Toast(self, f"Created '{name}'", "green")

    def _import_file(self):
        fp = filedialog.askopenfilename(title="Select links .txt file", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if not fp: return
        
        default_name = os.path.splitext(os.path.basename(fp))[0]
        dialog = ctk.CTkInputDialog(text="Enter a name for this workflow:", title="Import Workflow")
        name = dialog.get_input()
        
        if not name:
            name = default_name
        if not name:
            name = f"Workflow {len(self._workflows)+1}"
            
        if name in self._workflows:
            messagebox.showerror("Error", f"A workflow named '{name}' already exists.")
            return
            
        self._workflows[name] = {
            "path": fp, "runs": 0, "last_run": None, "pinned": False,
            "is_queue": False, "is_task_list": False, "hide_from_history": False,
            "is_protected": False, "is_hidden": False
        }
        _save(WORKFLOWS_FILE, self._workflows)
        _auto_backup(self._workflows)
        self._render_wf()
        Toast(self, f"Imported '{name}'", "green")

    def _del_workflow(self, name):
        if messagebox.askyesno("Delete", f"Delete workflow '{name}'?"):
            del self._workflows[name]
            _save(WORKFLOWS_FILE, self._workflows)
            self._render_wf()
            Toast(self, f"Deleted '{name}'", "red")

    def _rename_workflow(self, old):
        dialog = ctk.CTkInputDialog(text=f"Enter new name for '{old}':", title="Rename Workflow")
        new_name = dialog.get_input()
        if new_name and new_name.strip() and new_name.strip() != old:
            new_name = new_name.strip()
            if new_name in self._workflows:
                messagebox.showerror("Error", f"Workflow '{new_name}' already exists.")
                return
            self._workflows[new_name] = self._workflows.pop(old)
            _save(WORKFLOWS_FILE, self._workflows)
            self._render_wf()
            Toast(self, f"Renamed to '{new_name}'", "green")

    def _pin_workflow(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data, "runs": 0}
        was = data.get("pinned", False)
        data["pinned"] = not was
        self._workflows[name] = data
        _save(WORKFLOWS_FILE, self._workflows)
        self._render_wf()
        Toast(self, f"{'Unpinned' if was else 'Pinned'} '{name}'", "orange")

    def _protect_workflow(self, name):
        if not self._has_protected_password():
            messagebox.showwarning("No Password", "Please set a Protected Area Password in Settings first.")
            return
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data, "runs": 0}
        
        # Read plain text content before protecting
        fp = data.get("path", "")
        if os.path.exists(fp):
            content = read_file_content(fp, False, None)
            # Write back as encrypted content
            write_file_content(fp, content, True, self._protected_secret())
            
        data["is_protected"] = True
        self._workflows[name] = data
        _save(WORKFLOWS_FILE, self._workflows)
        self._render_wf()
        Toast(self, f"Protected '{name}'", "orange")

    def _unprotect_workflow(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data, "runs": 0}
        
        # Read encrypted content before unprotecting
        fp = data.get("path", "")
        if os.path.exists(fp):
            content = read_file_content(fp, True, self._protected_secret())
            # Write back as plain text content
            write_file_content(fp, content, False, None)
            
        data["is_protected"] = False
        data["is_hidden"] = False
        self._workflows[name] = data
        _save(WORKFLOWS_FILE, self._workflows)
        if hasattr(self, "_render_protected"): self._render_protected()
        self._render_wf()
        Toast(self, f"Unprotected '{name}'", "green")

    def _toggle_hidden_workflow(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data, "runs": 0}
        was = data.get("is_hidden", False)
        data["is_hidden"] = not was
        self._workflows[name] = data
        _save(WORKFLOWS_FILE, self._workflows)
        if hasattr(self, "_render_protected"): self._render_protected()
        Toast(self, f"{'Shown' if was else 'Hidden'} '{name}'", "blue")

    def _duplicate_workflow(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data, "runs": 0}
        
        new_name = f"{name} (copy)"
        i = 1
        while new_name in self._workflows:
            new_name = f"{name} (copy {i})"
            i += 1
            
        new_data = data.copy()
        new_data["runs"] = 0
        new_data["last_run"] = None
        
        old_fp = data.get("path", "")
        if old_fp and os.path.isfile(old_fp):
            safe = re.sub(r"[^a-zA-Z0-9_-]", "_", new_name)
            new_fp = os.path.join(APP_DIR, f"{safe}.txt")
            try:
                shutil.copy2(old_fp, new_fp)
                new_data["path"] = new_fp
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy file: {e}")
                
        self._workflows[new_name] = new_data
        _save(WORKFLOWS_FILE, self._workflows)
        self._render_wf()
        Toast(self, f"Duplicated '{name}'", "green")

    def _workflow_settings(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        
        def on_save(wf_name, new_settings):
            data["settings"] = new_settings
            self._workflows[wf_name] = data
            _save(WORKFLOWS_FILE, self._workflows)
            Toast(self, f"Settings saved for '{wf_name}'", "green")
            
        WorkflowSettingsDialog(self, name, data, on_save)

    def _open_editor(self, name, skip_auth=False):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        
        if data.get("is_protected") and not skip_auth:
            if self._has_protected_password():
                dialog = ctk.CTkInputDialog(text="Enter password to edit protected workflow:", title="Protected Workflow")
                if not self._verify_protected_password(dialog.get_input() or ""):
                    messagebox.showerror("Error", "Incorrect password")
                    return
                    
        self._workflows[name] = data
        fp = data.get("path", "")
        if not fp or not os.path.isfile(fp): messagebox.showerror("File Not Found", f"File missing:\n{fp}"); return
        
        def on_save():
            _save(WORKFLOWS_FILE, self._workflows)
            if hasattr(self, "_render_protected"): self._render_protected()
            self._render_wf()
            
        LinkEditorDialog(self, name, data, on_save=on_save, password=self._protected_secret())

    def _export_workflow_menu(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        fp = data.get("path", "")
        if not fp or not os.path.isfile(fp):
            messagebox.showerror("Error", "File not found.")
            return
            
        save_fp = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")], initialfile=f"{name}.txt")
        if save_fp:
            try:
                content = read_file_content(fp, data.get("is_protected", False), self._protected_secret())
                with open(save_fp, "w", encoding="utf-8") as f:
                    f.write(content)
                Toast(self, f"Exported '{name}'", "green")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export: {e}")

    def _ping_workflow(self, name):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        fp = data.get("path", "")
        if not fp or not os.path.isfile(fp): return
        
        try:
            content = read_file_content(fp, data.get("is_protected", False), self._protected_secret())
            urls = [normalize_url(l) for l in content.splitlines() if normalize_url(l)]
        except Exception: return
        
        if not urls:
            messagebox.showinfo("No URLs", "No valid URLs found in this workflow.")
            return
            
        Toast(self, f"Pinging {len(urls)} links in '{name}'...", "blue")
        
        def worker():
            dead = []
            for u in urls:
                alive, code, msg = check_link_alive(u)
                if not alive: dead.append(f"{u} ({msg})")
            
            if dead:
                self.after(0, lambda: messagebox.showwarning("Dead Links Found", f"Found {len(dead)} dead links in '{name}':\n" + "\n".join(dead[:10]) + ("\n..." if len(dead) > 10 else "")))
            else:
                self.after(0, lambda: messagebox.showinfo("Ping Complete", f"All {len(urls)} links in '{name}' appear to be alive!"))
                
        threading.Thread(target=worker, daemon=True).start()

    def _export_all_zip(self):
        fp = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP", "*.zip")],
                                        initialfile="flux_all_workflows.zip")
        if not fp: return
        try:
            with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(WORKFLOWS_FILE, "workflows.json")
                for name, data in self._workflows.items():
                    wfp = (data if isinstance(data, str) else data.get("path", ""))
                    if wfp and os.path.isfile(wfp):
                        content = read_file_content(wfp, data.get("is_protected", False) if isinstance(data, dict) else False, self._protected_secret())
                        zf.writestr(os.path.basename(wfp), content)
            Toast(self, f"Exported {len(self._workflows)} workflows as .zip", "green")
        except Exception as e: messagebox.showerror("Zip Error", str(e))

    def _run_workflow(self, name, skip_auth=False, ext_incognito=None, ext_new_window=None):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        
        if data.get("is_protected") and not skip_auth:
            if self._has_protected_password():
                dialog = ctk.CTkInputDialog(text="Enter password to run protected workflow:", title="Protected Workflow")
                if not self._verify_protected_password(dialog.get_input() or ""):
                    messagebox.showerror("Error", "Incorrect password")
                    return
                    
        fp = data.get("path", "")
        if not fp or not os.path.isfile(fp): messagebox.showerror("File Not Found", f"File missing:\n{fp}"); return
        
        if data.get("is_task_list"):
            TaskListDialog(self, name, data, on_close=self._render_wf)
            return
            
        if data.get("is_queue"):
            RunQueueDialog(self, name, data, on_run=lambda n, urls, d: self._run_queue_selected(n, urls, d, ext_incognito, ext_new_window), password=self._protected_secret())
            return
            
        self.sel_file.set(fp)
        self._run(workflow_name=name, ext_incognito=ext_incognito, ext_new_window=ext_new_window)
        
    def _run_selected_workflow(self, name, skip_auth=False, ext_incognito=None, ext_new_window=None):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        
        if data.get("is_protected") and not skip_auth:
            if self._has_protected_password():
                dialog = ctk.CTkInputDialog(text="Enter password to run protected workflow:", title="Protected Workflow")
                if not self._verify_protected_password(dialog.get_input() or ""):
                    messagebox.showerror("Error", "Incorrect password")
                    return
                    
        fp = data.get("path", "")
        if not fp or not os.path.isfile(fp): messagebox.showerror("File Not Found", f"File missing:\n{fp}"); return
        
        RunQueueDialog(self, name, data, on_run=lambda n, urls, d: self._run_queue_selected(n, urls, d, ext_incognito, ext_new_window), password=self._protected_secret())

    def _run_queue_selected(self, name, selected_urls, delete_after=False, ext_incognito=None, ext_new_window=None):
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        fp = data.get("path", "")
        if not fp or not os.path.isfile(fp): return
        
        self.sel_file.set(fp)
        self._run(workflow_name=name, specific_urls=selected_urls, delete_after=delete_after, ext_incognito=ext_incognito, ext_new_window=ext_new_window)
        
    def _toggle_theme(self):
        ctk.set_appearance_mode(self.theme_var.get())
        self._settings["theme"] = self.theme_var.get()
        _save(SETTINGS_FILE, self._settings)
        
    def _build_settings(self, parent):
        return build_settings(self, parent)

    def _save_extension_files(self):
        folder = filedialog.askdirectory(title="Select Folder to Save Extension")
        if not folder:
            return

        api_token = self._settings.get("api_token", "")
        if not api_token:
            messagebox.showerror("Error", "API token missing. Restart Elvar and try again.")
            return

        templates_dir = _resource_path("templates", "extension")
        required = ["manifest.json", "popup.html", "popup.js", "background.js", "README.txt"]
        missing = [f for f in required if not os.path.exists(os.path.join(templates_dir, f))]
        if missing:
            messagebox.showerror("Error", f"Missing extension templates: {', '.join(missing)}")
            return

        try:
            ext_dir = os.path.join(folder, "ElvarExtension")
            os.makedirs(ext_dir, exist_ok=True)

            for name in ["manifest.json", "popup.html", "README.txt"]:
                src = os.path.join(templates_dir, name)
                dst = os.path.join(ext_dir, name)
                with open(src, "r", encoding="utf-8") as fsrc, open(dst, "w", encoding="utf-8") as fdst:
                    fdst.write(fsrc.read())

            for name in ["popup.js", "background.js"]:
                src = os.path.join(templates_dir, name)
                dst = os.path.join(ext_dir, name)
                with open(src, "r", encoding="utf-8") as fsrc, open(dst, "w", encoding="utf-8") as fdst:
                    fdst.write(fsrc.read().replace("__ELVAR_API_TOKEN__", api_token))

            # icon.png for extension
            icon_dst = os.path.join(ext_dir, "icon.png")
            try:
                if PIL_OK:
                    from PIL import Image
                    ico_path = _resource_path("elvar_icon.ico")
                    if os.path.exists(ico_path):
                        Image.open(ico_path).save(icon_dst, format="PNG")
                    else:
                        raise FileNotFoundError("elvar_icon.ico not found")
                else:
                    raise RuntimeError("Pillow unavailable")
            except Exception:
                import base64
                icon_b64 = "iVBORw0KGgoAAAANSUhEUgAAAIAAAACACAYAAADDPmHLAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAABTSURBVHhe7cExAQAAAMKg9U9tCy8gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOBqA2YAAQG+xW0UAAAAAElFTkSuQmCC"
                with open(icon_dst, "wb") as f:
                    f.write(base64.b64decode(icon_b64))

            messagebox.showinfo("Success", f"Extension saved to:\n{ext_dir}\n\nLoad this folder as unpacked extension.")
        except Exception as e:
            LOGGER.exception("Failed to export extension files: %s", e)
            messagebox.showerror("Error", f"Failed to save extension:\n{e}")

    def _backup_data(self):
        fp = filedialog.asksaveasfilename(defaultextension=".elvarbak", filetypes=[("Elvar Backup", "*.elvarbak")], initialfile=f"elvar-backup-{datetime.now().strftime('%Y-%m-%d')}.elvarbak")
        if not fp: return
        try:
            with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(WORKFLOWS_FILE, "workflows.json")
                zf.write(SESSIONS_FILE, "sessions.json")
                zf.write(SETTINGS_FILE, "settings.json")
                zf.write(HISTORY_FILE, "history.json")
                for name, data in self._workflows.items():
                    wfp = (data if isinstance(data, str) else data.get("path", ""))
                    if wfp and os.path.isfile(wfp):
                        zf.write(wfp, os.path.basename(wfp))
            Toast(self, "Backup saved successfully!", "green")
        except Exception as e:
            messagebox.showerror("Backup Error", str(e))

    def _restore_data(self):
        fp = filedialog.askopenfilename(title="Select Backup File", filetypes=[("Elvar Backup", "*.elvarbak")])
        if not fp: return
        if not messagebox.askyesno("Restore Backup", "Are you sure you want to restore this backup? This will overwrite all current data."): return
        try:
            safe_extract_zip(fp, APP_DIR, LOGGER)

            Toast(self, "Restore successful! Please restart Elvar.", "green")
            self.after(2000, self._quit_app)
        except UnsafeArchiveError as e:
            messagebox.showerror("Restore Error", f"Unsafe backup blocked: {e}")
        except Exception as e:
            messagebox.showerror("Restore Error", f"Invalid backup file: {e}")

    def _get_gdrive_service(self):
        creds = None
        token_path = os.path.join(APP_DIR, 'token.json')
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/drive.file'])
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds_path = os.path.join(APP_DIR, 'credentials.json')
                if not os.path.exists(creds_path):
                    messagebox.showerror("Error", "credentials.json not found in Elvar data folder. Please download it from Google Cloud Console.")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, ['https://www.googleapis.com/auth/drive.file'])
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        return build('drive', 'v3', credentials=creds)

    def _backup_gdrive(self):
        if not GDRIVE_OK: return
        service = self._get_gdrive_service()
        if not service: return
        
        tmp_fp = os.path.join(APP_DIR, f"elvar-backup-{datetime.now().strftime('%Y-%m-%d')}.elvarbak")
        try:
            with zipfile.ZipFile(tmp_fp, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(WORKFLOWS_FILE, "workflows.json")
                zf.write(SESSIONS_FILE, "sessions.json")
                zf.write(SETTINGS_FILE, "settings.json")
                zf.write(HISTORY_FILE, "history.json")
                for name, data in self._workflows.items():
                    wfp = (data if isinstance(data, str) else data.get("path", ""))
                    if wfp and os.path.isfile(wfp):
                        zf.write(wfp, os.path.basename(wfp))
            
            file_metadata = {'name': os.path.basename(tmp_fp)}
            media = MediaFileUpload(tmp_fp, mimetype='application/zip')
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            Toast(self, "Backup uploaded to Google Drive!", "green")
        except Exception as e:
            messagebox.showerror("Drive Backup Error", str(e))
        finally:
            if os.path.exists(tmp_fp): os.remove(tmp_fp)

    def _restore_gdrive(self):
        if not GDRIVE_OK: return
        service = self._get_gdrive_service()
        if not service: return
        
        try:
            results = service.files().list(q="name contains 'elvar-backup-' and mimeType='application/zip'",
                                          spaces='drive',
                                          fields='files(id, name, createdTime)',
                                          orderBy='createdTime desc').execute()
            items = results.get('files', [])
            if not items:
                messagebox.showinfo("Restore", "No Elvar backups found on Google Drive.")
                return
                
            latest = items[0]
            if not messagebox.askyesno("Restore from Drive", f"Restore from latest backup: {latest['name']}?\nThis will overwrite all current data."): return
            
            request = service.files().get_media(fileId=latest['id'])
            tmp_fp = os.path.join(APP_DIR, "downloaded_backup.elvarbak")
            
            with io.FileIO(tmp_fp, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            safe_extract_zip(tmp_fp, APP_DIR, LOGGER)

            os.remove(tmp_fp)
            Toast(self, "Restore successful! Please restart Elvar.", "green")
            self.after(2000, self._quit_app)
        except UnsafeArchiveError as e:
            messagebox.showerror("Drive Restore Error", f"Unsafe backup blocked: {e}")
        except Exception as e:
            messagebox.showerror("Drive Restore Error", str(e))

    def _change_password(self):
        if self._has_protected_password():
            dialog_auth = ctk.CTkInputDialog(text="Enter current password or security answer:", title="Authentication Required")
            ans = dialog_auth.get_input()
            if not ans:
                return
            if (not self._verify_protected_password(ans)) and (ans.lower().strip() != self._settings.get("security_answer", "")):
                messagebox.showerror("Error", "Incorrect password or security answer.")
                return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Change Password")
        dialog.geometry("400x350")
        dialog.transient(self)
        dialog.grab_set()
        dialog.focus_force()

        ctk.CTkLabel(dialog, text="Set Protected Area Password", font=("Helvetica", 16, "bold")).pack(pady=15)

        ctk.CTkLabel(dialog, text="New Password (leave blank to remove):").pack()
        pwd_entry = ctk.CTkEntry(dialog, show="*")
        pwd_entry.pack(pady=5)

        ctk.CTkLabel(dialog, text="Security Question (for recovery):").pack()
        q_entry = ctk.CTkEntry(dialog)
        q_entry.pack(pady=5)

        ctk.CTkLabel(dialog, text="Security Answer:").pack()
        a_entry = ctk.CTkEntry(dialog)
        a_entry.pack(pady=5)

        def save():
            pwd = pwd_entry.get()
            if pwd:
                if not q_entry.get() or not a_entry.get():
                    messagebox.showerror("Error", "Security question and answer are required when setting a password.")
                    return
                self._settings["protected_password_hash"] = hash_password(pwd)
                self._settings["protected_key"] = self._settings.get("protected_key") or make_protected_key()
                self._settings["security_question"] = q_entry.get()
                self._settings["security_answer"] = a_entry.get().lower().strip()
                self._settings.pop("protected_password", None)
            else:
                to_unprotect = [n for n, d in self._workflows.items() if isinstance(d, dict) and d.get("is_protected")]
                secret = self._protected_secret()
                for wf_name in to_unprotect:
                    wf = self._workflows.get(wf_name, {})
                    fp = wf.get("path", "")
                    if fp and os.path.exists(fp):
                        try:
                            content = read_file_content(fp, True, secret)
                            write_file_content(fp, content, False, None)
                            wf["is_protected"] = False
                            self._workflows[wf_name] = wf
                        except Exception as exc:
                            LOGGER.exception("Failed unprotecting workflow during password removal (%s): %s", wf_name, exc)
                _save(WORKFLOWS_FILE, self._workflows)
                self._settings.pop("protected_password_hash", None)
                self._settings.pop("protected_key", None)
                self._settings.pop("security_question", None)
                self._settings.pop("security_answer", None)
                self._settings.pop("protected_password", None)

            _save(SETTINGS_FILE, self._settings)
            if hasattr(self, "_render_protected"):
                self._render_protected()
            self._render_wf()
            Toast(self, "Password updated successfully." if pwd else "Password removed and protected workflows unlocked.", "green")
            dialog.destroy()

        ctk.CTkButton(dialog, text="Save", command=save).pack(pady=20)

    def _force_reset_password(self):
        if not messagebox.askyesno("\u26A0 DANGER", "This will PERMANENTLY delete all protected workflows and reset your password. Are you sure?"): return
        
        to_delete = [name for name, data in self._workflows.items() if isinstance(data, dict) and data.get("is_protected")]
        for name in to_delete:
            wf_data = self._workflows[name]
            fp = wf_data.get("path", "")
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception as exc:
                    LOGGER.exception("Failed deleting protected workflow file (%s): %s", fp, exc)
            del self._workflows[name]
            
        _save(WORKFLOWS_FILE, self._workflows)
        
        self._settings.pop("protected_password", None)
        self._settings.pop("protected_password_hash", None)
        self._settings.pop("protected_key", None)
        self._settings.pop("security_question", None)
        self._settings.pop("security_answer", None)
        _save(SETTINGS_FILE, self._settings)
        
        self._render_wf()
        if hasattr(self, "_render_protected"): self._render_protected()
        Toast(self, "Password reset and protected workflows deleted.", "green")

    def _reset_all_data(self):
        if not messagebox.askyesno("\u26A0 DANGER", "This will PERMANENTLY delete all your workflows, sessions, and history. Are you absolutely sure?"): return
        if not messagebox.askyesno("FINAL CONFIRMATION", "Last chance. Delete everything?"): return
        
        try:
            for f in [WORKFLOWS_FILE, SESSIONS_FILE, SETTINGS_FILE, HISTORY_FILE, BACKUP_FILE]:
                if os.path.exists(f): os.remove(f)
            # Also delete .txt files in APP_DIR
            for f in os.listdir(APP_DIR):
                if f.endswith(".txt"): os.remove(os.path.join(APP_DIR, f))
            
            Toast(self, "All data reset. Restarting...", "red")
            self.after(2000, self._quit_app)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to reset data: {e}")

    def _open_palette(self):
        CommandPalette(self, list(self._workflows.keys()), self._run_workflow, self._switch, self._last_run_wf)
    #  LAUNCHER PAGE 
    def _build_launcher(self, parent):
        return build_launcher(self, parent)

    def _pick_file(self):
        fp = filedialog.askopenfilename(title="Select URLs File", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if fp:
            self.sel_file.set(fp)
            self._log(f"Selected: {os.path.basename(fp)}")
            
    def _update_quick_select(self):
        if not hasattr(self, 'qs_dropdown'): return
        names = ["Select Workflow..."] + list(self._workflows.keys())
        self.qs_dropdown.configure(values=names)
        if self.qs_var.get() not in names:
            self.qs_var.set("Select Workflow...")
            
    def _load_quick_select(self):
        name = self.qs_var.get()
        if name == "Select Workflow...": return
        data = self._workflows.get(name, {})
        if isinstance(data, str): data = {"path": data}
        
        if data.get("is_protected"):
            if self._has_protected_password():
                dialog = ctk.CTkInputDialog(text="Enter password to load protected workflow:", title="Protected Workflow")
                if not self._verify_protected_password(dialog.get_input() or ""):
                    messagebox.showerror("Error", "Incorrect password")
                    return
                    
        fp = data.get("path", "")
        if fp and os.path.exists(fp):
            self.sel_file.set(fp)
            self._log(f"Loaded workflow: {name}")
        else:
            messagebox.showerror("Error", "Workflow file not found.")

    def _log(self, msg):
        self._log_txt.configure(state="normal")
        self._log_txt.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self._log_txt.see("end")
        self._log_txt.configure(state="disabled")

    def _run(self, workflow_name=None, specific_urls=None, delete_after=None, ext_incognito=None, ext_new_window=None):
        if self._running: return
        fp = self.sel_file.get()
        if not fp or fp == "no file selected" or not os.path.isfile(fp):
            messagebox.showerror("Error", "Please select a valid file first."); return
            
        browser = self.sel_browser.get()
        if browser == "Custom..." and not self.custom_exe.get():
            messagebox.showerror("Error", "Please specify a custom browser executable in Settings."); return
            
        user_input = None
        try:
            is_protected = False
            if workflow_name and hasattr(self, '_workflows'):
                data = self._workflows.get(workflow_name, {})
                if isinstance(data, dict):
                    is_protected = data.get("is_protected", False)
            content = read_file_content(fp, is_protected, self._protected_secret())
            if "{input}" in content:
                dialog = ctk.CTkInputDialog(text="Enter value for {input}:", title="Input Required")
                user_input = dialog.get_input()
                if user_input is None:
                    return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")
            return
            
        self._running = True
        self._stop_flag = False
        self._pause_flag = False
        self._run_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        if hasattr(self, '_pause_btn'):
            self._pause_btn.configure(state="normal", text="\u23F8 Pause", fg_color="#FF9500", hover_color="#E68A00")
        self._prog.set(0)
        self._log("Starting run...")
        
        if workflow_name:
            self._last_run_wf = workflow_name
            data = self._workflows.get(workflow_name, {})
            if isinstance(data, str): data = {"path": data, "runs": 0}
            data["runs"] = data.get("runs", 0) + 1
            data["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            self._workflows[workflow_name] = data
            _save(WORKFLOWS_FILE, self._workflows)
            
        threading.Thread(target=self._worker, args=(fp, browser, workflow_name, user_input, specific_urls, delete_after, ext_incognito, ext_new_window), daemon=True).start()

    def _stop(self):
        if self._running:
            self._stop_flag = True
            self._log("Stopping...")
            self._run_btn.configure(state="normal")
            self._stop_btn.configure(state="disabled")
            if hasattr(self, '_pause_btn'):
                self._pause_btn.configure(state="disabled")

    def _pause(self):
        if self._running:
            self._pause_flag = not self._pause_flag
            if self._pause_flag:
                self._log("Paused...")
                self._pause_btn.configure(text="\u25B6 Resume", fg_color="#34C759", hover_color="#28A745")
            else:
                self._log("Resumed...")
                self._pause_btn.configure(text="\u23F8 Pause", fg_color="#FF9500", hover_color="#E68A00")

    def _worker(self, fp, browser, wf_name, user_input=None, specific_urls=None, delete_after=None, ext_incognito=None, ext_new_window=None):
        try:
            data = self._workflows.get(wf_name, {}) if wf_name else {}
            content = read_file_content(fp, data.get("is_protected", False), self._protected_secret())
            lines = content.splitlines()

            mode = data.get("settings", {}).get("run_mode", self.run_mode.get())
            pairs = prepare_pairs(
                lines,
                normalize_url=normalize_url,
                strip_tracking=strip_tracking,
                mode=mode,
                strip_utm=self.strip_utm_var.get(),
                start=data.get("settings", {}).get("range_start", self.range_start.get()),
                end=data.get("settings", {}).get("range_end", self.range_end.get()),
                max_tabs=data.get("settings", {}).get("max_tabs", self.max_tabs.get()),
                user_input=user_input,
                specific_urls=specific_urls,
            )
            
            total = len(pairs)
            opened = 0
            failed = []
            opened_orig_urls = []
            
            if total == 0:
                self.after(0, self._log, "No valid links found.")
                return
                
            self.after(0, self._log, f"Found {total} links. Mode: {mode}")

            exe = self.custom_exe.get() if browser == "Custom..." else detect_browser(browser)
            if not exe and browser != "System Default":
                self.after(0, self._log, f"Browser '{browser}' not found.")
                return

            def open_one(url, is_first_in_batch=False):
                if self.dry_run.get(): return True
                args = [exe] if browser != "System Default" else []
                
                wf_incognito = data.get("settings", {}).get("incognito", self.incognito.get())
                use_incognito = ext_incognito if ext_incognito is not None else wf_incognito
                
                wf_new_window = data.get("settings", {}).get("new_window", self.new_window.get())
                use_new_window = ext_new_window if ext_new_window is not None else wf_new_window
                
                if use_incognito and browser != "System Default":
                    flag = INCOGNITO_FLAGS.get(browser, "")
                    if flag: args.append(flag)
                if use_new_window and browser != "System Default":
                    flag = NEW_WINDOW_FLAGS.get(browser, "")
                    if flag: args.append(flag)
                
                if self.auto_pin_var.get() and browser in ["Google Chrome", "Microsoft Edge", "Brave", "Vivaldi"]:
                    pass
                args.append(url)
                try:
                    if browser == "System Default":
                        import webbrowser
                        webbrowser.open(url)
                    else:
                        open_subprocess(args)
                    return True
                except Exception as e:
                    self.after(0, self._log, f"Failed: {str(e)}")
                    return False

            delay = data.get("settings", {}).get("delay", self.delay_var.get())
            batch_n = max(1, data.get("settings", {}).get("batch_size", self.batch_size.get()))

            if mode == "batch":
                for bs in range(0, total, batch_n):
                    if self._stop_flag:
                        self.after(0, self._log, "Stopped by user.")
                        break
                    while self._pause_flag and not self._stop_flag: time.sleep(0.2)
                    if self._stop_flag:
                        self.after(0, self._log, "Stopped by user.")
                        break
                    
                    batch = pairs[bs:bs+batch_n]
                    results = []
                    
                    def open_wrapper(orig_u, u):
                        success = open_one(u)
                        results.append((orig_u, u, success))
                        
                    ts = [threading.Thread(target=open_wrapper, args=(orig_u, u), daemon=True) for orig_u, u in batch]
                    for t in ts: t.start()
                    for t in ts: t.join()
                    
                    for orig_u, u, success in results:
                        if success:
                            opened += 1
                            opened_orig_urls.append(orig_u)
                            self.after(0, self._log, u)
                            self._total_tabs += 1
                        else:
                            failed.append(u)
                            
                    frac = min((bs + batch_n) / max(total, 1), 1.0)
                    self.after(0, self._prog.set, frac)
                    
                    self.after(0, self._total_lbl.configure, {"text": f" {self._total_tabs} tabs lifetime"})
                    time.sleep(delay)
            else:
                for i, (orig_url, url) in enumerate(pairs):
                    if self._stop_flag:
                        self.after(0, self._log, "Stopped by user.")
                        break
                    while self._pause_flag and not self._stop_flag: time.sleep(0.2)
                    if self._stop_flag:
                        self.after(0, self._log, "Stopped by user.")
                        break
                    
                    if open_one(url):
                        opened += 1
                        opened_orig_urls.append(orig_url)
                        self.after(0, self._log, url)
                        self._total_tabs += 1
                        self.after(0, self._total_lbl.configure, {"text": f" {self._total_tabs} tabs lifetime"})
                    else:
                        failed.append(url)
                        
                    frac = (i + 1) / max(total, 1)
                    self.after(0, self._prog.set, frac)
                    time.sleep(delay)

            self.after(0, self._log, f"Done. Opened: {opened}, Failed: {len(failed)}")
            if self.sound_var.get(): play_sound()
            
            if wf_name:
                data = self._workflows.get(wf_name, {})
                if isinstance(data, dict):
                    should_delete = delete_after if delete_after is not None else data.get("is_queue", False)
                    if should_delete and opened_orig_urls:
                        try:
                            orig_fp = data.get("path", fp)
                            content = read_file_content(orig_fp, data.get("is_protected", False), self._protected_secret())
                            file_lines = content.splitlines(True)
                            
                            new_lines = []
                            opened_set = set(opened_orig_urls)
                            for l in file_lines:
                                u = normalize_url(l)
                                if u in opened_set:
                                    opened_set.remove(u)
                                    continue
                                new_lines.append(l)
                                
                            write_file_content(orig_fp, "".join(new_lines), data.get("is_protected", False), self._protected_secret())
                            prefix = "Queue Mode" if data.get("is_queue", False) else "Run Selected"
                            self.after(0, self._log, f"{prefix}: Removed {len(opened_orig_urls)} URLs from file.")
                        except Exception as e:
                            self.after(0, self._log, f"Failed to update queue file: {str(e)}")
                            
                    if not data.get("hide_from_history") and not data.get("is_protected") and not data.get("is_hidden") and not self.disable_log_var.get():
                        hist_entry = {"date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                      "workflow": wf_name, "opened": opened, "failed": len(failed)}
                        self._history.insert(0, hist_entry)
                        self._history = self._history[:100]
                        _save(HISTORY_FILE, self._history)
                        self.after(0, self._render_history)
            else:
                if not self.disable_log_var.get():
                    hist_entry = {"date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  "workflow": "Custom File", "opened": opened, "failed": len(failed)}
                    self._history.insert(0, hist_entry)
                    self._history = self._history[:100]
                    _save(HISTORY_FILE, self._history)
                    self.after(0, self._render_history)

        except Exception as e:
            self.after(0, self._log, f"Error: {str(e)}")
        finally:
            self._running = False
            self.after(0, lambda: self._run_btn.configure(state="normal"))
            self.after(0, lambda: self._stop_btn.configure(state="disabled"))
            if hasattr(self, '_pause_btn'):
                self.after(0, lambda: self._pause_btn.configure(state="disabled"))

    #  SESSIONS PAGE 
    def _build_sessions(self, parent):
        return build_sessions(self, parent)

    def _render_sessions(self):
        for w in self._sess_scroll.winfo_children(): w.destroy()
        if not self._sessions:
            ctk.CTkLabel(self._sess_scroll, text="No sessions saved.", font=("Helvetica", 18), text_color=("#8E8E93", "#98989D")).pack(pady=40)
            return
        for name, data in sorted(self._sessions.items(), key=lambda x: x[1].get("date", ""), reverse=True):
            card = ctk.CTkFrame(self._sess_scroll, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
            card.pack(fill="x", pady=6, padx=10)
            
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=15, pady=12)
            
            ctk.CTkLabel(top, text=name, font=("Helvetica", 16, "bold")).pack(side="left")
            ctk.CTkLabel(top, text=f"{len(data.get('urls', []))} tabs", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D"),
                         fg_color=("#F2F2F7", "#2C2C2E"), corner_radius=6).pack(side="left", padx=10, ipadx=6, ipady=2)
            ctk.CTkLabel(top, text=data.get("browser", "Unknown"), font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left")
            
            btn_row = ctk.CTkFrame(top, fg_color="transparent")
            btn_row.pack(side="right")
            
            ctk.CTkButton(btn_row, text="\u25B6 Restore", width=80, height=28, fg_color="#34C759", hover_color="#28A745",
                          command=lambda n=name: self._restore_session(n)).pack(side="left", padx=5)
            ctk.CTkButton(btn_row, text="X", width=30, height=28, fg_color="transparent", text_color="#FF3B30", hover_color=("#E5E5EA", "#3A3A3C"),
                          command=lambda n=name: self._del_session(n)).pack(side="left", padx=5)
                          
            ctk.CTkLabel(card, text=data.get("date", ""), font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=15, pady=(0, 12))

    def _save_session(self):
        self._save_session_dlg = SaveSessionDialog(self, self._detected, self._on_session_saved)

    def _on_session_saved(self, name, browser, urls):
        self._sessions[name] = {"browser": browser, "urls": urls, "date": datetime.now().strftime("%Y-%m-%d %H:%M")}
        _save(SESSIONS_FILE, self._sessions)
        self._render_sessions()
        Toast(self, f"Saved '{name}'", "purple")

    def _restore_session(self, name):
        data = self._sessions.get(name)
        if not data: return
        RestoreSessionDialog(self, name, data, self._do_restore_session)
        
    def _do_restore_session(self, name, urls, browser):
        fp = os.path.join(APP_DIR, f"session_{re.sub(r'[^a-zA-Z0-9_-]', '_', name)}.txt")
        with open(fp, "w", encoding="utf-8") as f: f.write("\n".join(urls) + "\n")
        self.sel_file.set(fp)
        self.sel_browser.set(browser)
        self._switch("launcher")
        self._run()

    def _del_session(self, name):
        if messagebox.askyesno("Delete Session", f"Delete session '{name}'?"):
            del self._sessions[name]
            _save(SESSIONS_FILE, self._sessions)
            self._render_sessions()
            Toast(self, f"Deleted '{name}'", "red")

    def _mini_widget(self):
        if hasattr(self, "_mini_win") and self._mini_win and self._mini_win.winfo_exists():
            self._mini_win.lift()
            return
            
        self._mini_win = ctk.CTkToplevel(self)
        self._mini_win.title("Elvar Mini")
        self._mini_win.geometry("300x150")
        self._mini_win.attributes("-topmost", True)
        self._mini_win.resizable(False, False)
        
        frame = ctk.CTkFrame(self._mini_win, corner_radius=10)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self._mini_wf_var = ctk.StringVar(value="Select Workflow")
        wfs = list(self._workflows.keys())
        if wfs: self._mini_wf_var.set(wfs[0])
        
        self._mini_cb = ctk.CTkComboBox(frame, values=wfs, variable=self._mini_wf_var, font=("Helvetica", 14), state="readonly")
        self._mini_cb.pack(fill="x", padx=15, pady=(15, 10))
        
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        def run_mini():
            wf = self._mini_wf_var.get()
            if wf and wf in self._workflows:
                self._run_workflow(wf)
                
        def stop_mini():
            self._stop()
            
        ctk.CTkButton(btn_frame, text="\u25B6 Run", command=run_mini, fg_color="#34C759", hover_color="#28A745", width=100).pack(side="left", expand=True, padx=(0, 5))
        ctk.CTkButton(btn_frame, text="\u25A0 Stop", command=stop_mini, fg_color="#FF3B30", hover_color="#D32F2F", width=100).pack(side="right", expand=True, padx=(5, 0))

    def _update_mini_widget(self):
        if hasattr(self, "_mini_win") and self._mini_win and self._mini_win.winfo_exists():
            wfs = list(self._workflows.keys())
            if hasattr(self, "_mini_cb"):
                self._mini_cb.configure(values=wfs)
            if wfs and self._mini_wf_var.get() not in wfs:
                self._mini_wf_var.set(wfs[0])
            elif not wfs:
                self._mini_wf_var.set("Select Workflow")

    #  HISTORY PAGE 
    def _build_history(self, parent):
        return build_history(self, parent)

    def _render_history(self):
        for w in self._hist_scroll.winfo_children(): w.destroy()
        if not self._history:
            ctk.CTkLabel(self._hist_scroll, text="No history yet.", font=("Helvetica", 18), text_color=("#8E8E93", "#98989D")).pack(pady=40)
            return
        for item in self._history:
            row = ctk.CTkFrame(self._hist_scroll, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=8)
            row.pack(fill="x", pady=4, padx=10)
            
            ctk.CTkLabel(row, text=item.get("date", ""), font=("Courier New", 13), text_color=("#8E8E93", "#98989D"), width=180, anchor="w").pack(side="left", padx=15, pady=10)
            ctk.CTkLabel(row, text=item.get("workflow", "Unknown"), font=("Helvetica", 14, "bold"), width=250, anchor="w").pack(side="left", padx=15)
            
            stats_frame = ctk.CTkFrame(row, fg_color="transparent")
            stats_frame.pack(side="right", padx=15)
            
            ctk.CTkLabel(stats_frame, text=f"{item.get('opened', 0)} opened", font=("Helvetica", 13), text_color="#34C759").pack(side="left", padx=5)
            if item.get("failed", 0):
                ctk.CTkLabel(stats_frame, text=f"{item.get('failed')} failed", font=("Helvetica", 13), text_color="#FF3B30").pack(side="left", padx=5)

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Clear all run history?"):
            self._history = []
            _save(HISTORY_FILE, self._history)
            self._render_history()

    def _export_history_csv(self):
        if not self._history: return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="elvar_history.csv")
        if fp:
            try:
                import csv
                with open(fp, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Date", "Workflow", "Opened", "Failed"])
                    for item in self._history:
                        writer.writerow([item.get("date", ""), item.get("workflow", ""), item.get("opened", 0), item.get("failed", 0)])
                messagebox.showinfo("Exported", f"History exported to {fp}")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _show_add_to_workflow_dialog(self, url, title):
        workflows = list(self._workflows.keys())
        if not workflows:
            messagebox.showinfo("No Workflows", "You don't have any workflows yet. Create one first.")
            return
            
        def on_add(wf_name, link):
            if wf_name in self._workflows:
                fp = self._workflows[wf_name]["path"]
                try:
                    with open(fp, "a", encoding="utf-8") as f:
                        f.write(f"{link}\n")
                    Toast(self, f"Added to {wf_name}!", "green")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add link: {e}")
                    
        AddToWorkflowDialog(self, url, title, workflows, on_add)

    #  ANALYTICS PAGE 
    def _build_analytics(self, parent):
        return build_analytics(self, parent)

    def _render_analytics(self):
        for w in self._analytics_scroll.winfo_children(): w.destroy()
        
        total_runs = len(self._history)
        total_opened = sum(item.get("opened", 0) for item in self._history)
        total_failed = sum(item.get("failed", 0) for item in self._history)
        
        # Assume an average of 5 seconds saved per tab opened automatically
        time_saved_seconds = total_opened * 5
        if time_saved_seconds < 60:
            time_saved_str = f"{time_saved_seconds}s"
        elif time_saved_seconds < 3600:
            time_saved_str = f"{time_saved_seconds // 60}m {time_saved_seconds % 60}s"
        else:
            time_saved_str = f"{time_saved_seconds // 3600}h {(time_saved_seconds % 3600) // 60}m"
        
        stats_frame = ctk.CTkFrame(self._analytics_scroll, fg_color="transparent")
        stats_frame.pack(fill="x", pady=10)
        
        def make_stat(parent, title, val, color):
            f = ctk.CTkFrame(parent, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
            f.pack(side="left", fill="x", expand=True, padx=5)
            ctk.CTkLabel(f, text=title, font=("Helvetica", 14), text_color=("#8E8E93", "#98989D")).pack(pady=(15, 5))
            ctk.CTkLabel(f, text=str(val), font=("Helvetica", 32, "bold"), text_color=color).pack(pady=(0, 15))
            
        make_stat(stats_frame, "Total Runs", total_runs, "#007AFF")
        make_stat(stats_frame, "Tabs Opened", total_opened, "green")
        make_stat(stats_frame, "Failed Links", total_failed, "red")
        make_stat(stats_frame, "Time Saved", time_saved_str, "purple")
        
        if not self._history: return
        
        wf_counts = {}
        for item in self._history:
            w = item.get("workflow", "Unknown")
            wf_counts[w] = wf_counts.get(w, 0) + 1
            
        top_wfs = sorted(wf_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        ctk.CTkLabel(self._analytics_scroll, text="Top Workflows", font=("Helvetica", 18, "bold")).pack(anchor="w", pady=(30, 10))
        
        for wf, count in top_wfs:
            row = ctk.CTkFrame(self._analytics_scroll, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=8)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=wf, font=("Helvetica", 14)).pack(side="left", padx=15, pady=10)
            ctk.CTkLabel(row, text=f"{count} runs", font=("Helvetica", 14, "bold"), text_color="#007AFF").pack(side="right", padx=15)

    def _build_protected(self, parent):
        return build_protected(self, parent)

    def _auth_protected(self):
        pwd = self._prot_pw_entry.get()
        if not self._has_protected_password():
            self._prot_err_lbl.configure(text="No password set in Settings.")
            return
        if self._verify_protected_password(pwd):
            self._prot_auth_frame.pack_forget()
            self._prot_main_frame.pack(fill="both", expand=True)
            self._prot_pw_entry.delete(0, "end")
            self._prot_err_lbl.configure(text="")
            self._render_protected()
        else:
            self._prot_err_lbl.configure(text="Incorrect password")
            self._prot_pw_entry.delete(0, "end")

    def _forgot_password(self):
        q = self._settings.get("security_question")
        if not q:
            messagebox.showerror("Error", "No security question set.")
            return

        dialog = ctk.CTkInputDialog(text=f"Security Question:\n{q}", title="Forgot Password")
        ans = dialog.get_input()
        if ans and ans.lower().strip() == self._settings.get("security_answer", ""):
            if messagebox.askyesno("Reset Password", "Security answer verified. Reset now? This will delete all protected workflows."):
                self._force_reset_password()
        elif ans:
            messagebox.showerror("Error", "Incorrect answer.")

    def _lock_protected(self):
        self._prot_main_frame.pack_forget()
        self._prot_auth_frame.pack(fill="both", expand=True, padx=30, pady=20)

    def _render_protected(self):
        for w in self._prot_scroll.winfo_children(): w.destroy()
        
        matches = [(k, v) for k, v in self._workflows.items() if isinstance(v, dict) and v.get("is_protected")]
        self._prot_count_lbl.configure(text=f"  {len(matches)} secured")
        
        if not matches:
            ctk.CTkLabel(self._prot_scroll, text="No protected workflows.", font=("Helvetica", 18), text_color=("#8E8E93", "#98989D")).pack(pady=40)
            return
            
        cbs = {"run": lambda n: self._run_workflow(n, skip_auth=True), 
               "delete": self._del_workflow, "rename": self._rename_workflow,
               "pin": self._pin_workflow, "duplicate": self._duplicate_workflow, "export": self._export_workflow_menu,
               "edit": lambda n: self._open_editor(n, skip_auth=True), 
               "refresh": self._render_protected, "unprotect": self._unprotect_workflow, "toggle_hidden": self._toggle_hidden_workflow,
               "ping": self._ping_workflow, "settings": self._workflow_settings, "run_selected": lambda n: self._run_selected_workflow(n, skip_auth=True)}
               
        for name, data in matches:
            card = WorkflowCard(self._prot_scroll, name, data, callbacks=cbs, is_protected_view=True, password=self._protected_secret())
            card.pack(fill="x", pady=6, padx=10)

if __name__ == "__main__":
    _set_windows_app_id()
    app = App()

    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        wf_name = sys.argv[2] if len(sys.argv) > 2 else None
        if wf_name and wf_name in app._workflows:
            app.after(500, lambda: app._run_workflow(wf_name))

    app.mainloop()




































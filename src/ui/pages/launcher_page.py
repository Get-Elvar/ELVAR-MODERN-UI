import customtkinter as ctk
from tkinter import filedialog, messagebox
import os


def build_launcher(app, parent):
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)
    ctk.CTkLabel(hdr, text="Launcher", font=("Helvetica", 28, "bold")).pack(side="left")

    body = ctk.CTkFrame(parent, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=30, pady=(0, 20))

    # File Selection
    f_row = ctk.CTkFrame(body, fg_color="transparent")
    f_row.pack(fill="x", pady=5)
    ctk.CTkLabel(f_row, text="File:", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkEntry(f_row, textvariable=app.sel_file, state="disabled", font=("Helvetica", 14)).pack(side="left", fill="x", expand=True, padx=10)
    ctk.CTkButton(f_row, text="Browse", command=app._pick_file, width=100).pack(side="left")

    # Quick Select Workflow
    qs_row = ctk.CTkFrame(body, fg_color="transparent")
    qs_row.pack(fill="x", pady=5)
    ctk.CTkLabel(qs_row, text="Workflow:", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    app.qs_var = ctk.StringVar(value="Select Workflow...")
    app.qs_dropdown = ctk.CTkOptionMenu(qs_row, variable=app.qs_var, values=["Select Workflow..."], font=("Helvetica", 14), dynamic_resizing=False)
    app.qs_dropdown.pack(side="left", fill="x", expand=True, padx=10)
    ctk.CTkButton(qs_row, text="Load", command=app._load_quick_select, width=100, fg_color="#5AC8FA", hover_color="#34AADC").pack(side="left")

    # Browser Selection
    b_row = ctk.CTkFrame(body, fg_color="transparent")
    b_row.pack(fill="x", pady=5)
    ctk.CTkLabel(b_row, text="Browser:", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    browsers = ["System Default"] + list(app._detected.keys()) + ["Custom..."]
    ctk.CTkComboBox(b_row, values=browsers, variable=app.sel_browser, font=("Helvetica", 14), state="readonly").pack(side="left", fill="x", expand=True, padx=10)

    # Delay
    d_row = ctk.CTkFrame(body, fg_color="transparent")
    d_row.pack(fill="x", pady=5)
    ctk.CTkLabel(d_row, text="Delay (s):", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    app.d_val_lbl = ctk.CTkLabel(d_row, text=f"{app.delay_var.get():.1f}s", width=40)
    app.d_val_lbl.pack(side="right")
    def update_d_lbl(val):
        app.d_val_lbl.configure(text=f"{float(val):.1f}s")
        app.delay_var.set(float(val))
    ctk.CTkSlider(d_row, from_=0, to=10, variable=app.delay_var, number_of_steps=100, command=update_d_lbl).pack(side="left", fill="x", expand=True, padx=10)

    # Mode & Range
    m_row = ctk.CTkFrame(body, fg_color="transparent")
    m_row.pack(fill="x", pady=5)
    ctk.CTkLabel(m_row, text="Mode:", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkComboBox(m_row, values=["sequential", "reverse", "shuffle", "batch"], variable=app.run_mode, width=120).pack(side="left", padx=(10, 20))

    ctk.CTkLabel(m_row, text="Start:", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkEntry(m_row, textvariable=app.range_start, width=60).pack(side="left", padx=5)
    ctk.CTkLabel(m_row, text="End:", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkEntry(m_row, textvariable=app.range_end, width=60).pack(side="left", padx=5)
    ctk.CTkLabel(m_row, text="(0 = all)", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left")

    # Max Tabs & Batch Size
    mt_row = ctk.CTkFrame(body, fg_color="transparent")
    mt_row.pack(fill="x", pady=5)
    ctk.CTkLabel(mt_row, text="Max Tabs:", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkEntry(mt_row, textvariable=app.max_tabs, width=60).pack(side="left", padx=10)
    ctk.CTkLabel(mt_row, text="(0 = unlimited)", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=(0, 20))

    ctk.CTkLabel(mt_row, text="Batch Size:", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkEntry(mt_row, textvariable=app.batch_size, width=60).pack(side="left", padx=10)

    # Options
    opt_row = ctk.CTkFrame(body, fg_color="transparent")
    opt_row.pack(fill="x", pady=5)
    ctk.CTkLabel(opt_row, text="Options:", width=80, anchor="w", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkSwitch(opt_row, text="Incognito Mode", variable=app.incognito, font=("Helvetica", 14)).pack(side="left", padx=(0, 20))
    ctk.CTkSwitch(opt_row, text="Force New Window", variable=app.new_window, font=("Helvetica", 14)).pack(side="left")

    # Controls
    c_row = ctk.CTkFrame(body, fg_color="transparent")
    c_row.pack(fill="x", pady=20)
    app._run_btn = ctk.CTkButton(c_row, text="\u25B6 Run", command=app._run, fg_color="#34C759", hover_color="#28A745", font=("Helvetica", 14, "bold"), height=36)
    app._run_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
    app._pause_btn = ctk.CTkButton(c_row, text="\u23F8 Pause", command=app._pause, fg_color="#FF9500", hover_color="#E68A00", font=("Helvetica", 14, "bold"), height=36, state="disabled")
    app._pause_btn.pack(side="left", fill="x", expand=True, padx=5)
    app._stop_btn = ctk.CTkButton(c_row, text="\u23F9 Stop", command=app._stop, fg_color="#FF3B30", hover_color="#D32F2F", font=("Helvetica", 14, "bold"), height=36, state="disabled")
    app._stop_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

    # Progress
    app._prog = ctk.CTkProgressBar(body)
    app._prog.pack(fill="x", pady=10)
    app._prog.set(0)

    # Log
    app._log_txt = ctk.CTkTextbox(body, font=("Courier New", 12), state="disabled")
    app._log_txt.pack(fill="both", expand=True, pady=10)

    app._update_quick_select()

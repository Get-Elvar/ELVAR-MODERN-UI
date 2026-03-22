import customtkinter as ctk
from tkinter import messagebox, filedialog
import os, zipfile
from datetime import datetime


def build_workflows(app, parent):
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)

    ctk.CTkLabel(hdr, text="Workflows", font=("Helvetica", 28, "bold")).pack(side="left")
    app._wf_count_lbl = ctk.CTkLabel(hdr, text=f"  {len(app._workflows)} saved", font=("Helvetica", 14), text_color=("#8E8E93", "#98989D"))
    app._wf_count_lbl.pack(side="left", padx=10)

    app._batch_mode = False
    app._batch_vars = {}

    btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_row.pack(side="right")

    app._batch_btn = ctk.CTkButton(btn_row, text="Batch Mode", command=app._toggle_batch_mode, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), width=100)
    app._batch_btn.pack(side="left", padx=5)

    ctk.CTkButton(btn_row, text="+ New", command=app._new_workflow, fg_color="#007AFF", width=100).pack(side="left", padx=5)
    ctk.CTkButton(btn_row, text="+ Queue", command=app._new_queue, fg_color="#34C759", hover_color="#28A745", width=100).pack(side="left", padx=5)
    ctk.CTkButton(btn_row, text="Import .txt", command=app._import_file, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), width=100).pack(side="left", padx=5)
    ctk.CTkButton(btn_row, text="Export All .zip", command=app._export_all_zip, fg_color="#5AC8FA", width=120).pack(side="left", padx=5)

    search_row = ctk.CTkFrame(parent, fg_color="transparent")
    search_row.pack(fill="x", padx=30, pady=(0, 10))

    app._wf_search = ctk.CTkEntry(search_row, placeholder_text="\u2315 Search workflows...", font=("Helvetica", 14), height=35)
    app._wf_search.pack(side="left", fill="x", expand=True)
    app._wf_search.bind("<KeyRelease>", lambda e: app._render_wf())

    app._sort_var = ctk.StringVar(value="default")
    app._show_pinned_first = ctk.BooleanVar(value=True)

    sort_frame = ctk.CTkFrame(search_row, fg_color="transparent")
    sort_frame.pack(side="right", padx=(15, 0))

    ctk.CTkLabel(sort_frame, text="Sort:", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=5)
    for label, val in [("Default", "default"), ("Name", "name"), ("Runs", "runs"), ("Last", "last_run"), ("Links", "links")]:
        ctk.CTkRadioButton(sort_frame, text=label, variable=app._sort_var, value=val, font=("Helvetica", 12),
                           command=app._render_wf).pack(side="left", padx=5)
                           
    ctk.CTkCheckBox(sort_frame, text="\U0001F4CC first", variable=app._show_pinned_first, font=("Helvetica", 12),
                    command=app._render_wf).pack(side="left", padx=10)
                    
    app._wf_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    app._wf_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    app._batch_actions_frame = ctk.CTkFrame(parent, fg_color="transparent")

    ctk.CTkButton(app._batch_actions_frame, text="Select All", command=app._batch_select_all, fg_color="#8E8E93", hover_color="#636366", width=120).pack(side="left", padx=10)
    ctk.CTkButton(app._batch_actions_frame, text="Delete Selected", command=app._batch_delete, fg_color="#FF3B30", hover_color="#D32F2F", width=120).pack(side="right", padx=10)
    ctk.CTkButton(app._batch_actions_frame, text="Export Selected", command=app._batch_export, fg_color="#5AC8FA", hover_color="#34AADC", width=120).pack(side="right", padx=10)

    app._wf_cards = {}
    app._render_wf()

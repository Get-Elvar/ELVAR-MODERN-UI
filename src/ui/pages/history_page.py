import customtkinter as ctk


def build_history(app, parent):
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)
    ctk.CTkLabel(hdr, text="History", font=("Helvetica", 28, "bold")).pack(side="left")

    btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_row.pack(side="right")
    ctk.CTkButton(btn_row, text="Export CSV", command=app._export_history_csv, fg_color="#5AC8FA", width=120).pack(side="left", padx=5)
    ctk.CTkButton(btn_row, text="Clear History", command=app._clear_history, fg_color="#FF3B30", hover_color="#D32F2F", width=120).pack(side="left")

    app._hist_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    app._hist_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    app._render_history()

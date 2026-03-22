import customtkinter as ctk


def build_sessions(app, parent):
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)
    ctk.CTkLabel(hdr, text="Sessions", font=("Helvetica", 28, "bold")).pack(side="left")
    app._sess_count = ctk.CTkLabel(hdr, text=f"  {len(app._sessions)} saved", font=("Helvetica", 14), text_color=("#8E8E93", "#98989D"))
    app._sess_count.pack(side="left", padx=10)

    btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_row.pack(side="right")
    ctk.CTkButton(btn_row, text="+ Save Session", command=app._save_session, fg_color="#AF52DE", hover_color="#8E33B7", width=120).pack(side="left")

    app._sess_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    app._sess_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    app._render_sessions()

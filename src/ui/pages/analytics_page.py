import customtkinter as ctk


def build_analytics(app, parent):
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)
    ctk.CTkLabel(hdr, text="Analytics", font=("Helvetica", 28, "bold")).pack(side="left")

    btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_row.pack(side="right")
    ctk.CTkButton(btn_row, text="Refresh", command=app._render_analytics, fg_color="#007AFF", width=100).pack(side="left")

    app._analytics_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    app._analytics_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
    app._render_analytics()

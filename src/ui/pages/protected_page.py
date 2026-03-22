import customtkinter as ctk


def build_protected(app, parent):
    app._protected_parent = parent
    app._protected_auth = False

    app._prot_auth_frame = ctk.CTkFrame(parent, fg_color="transparent")
    app._prot_auth_frame.pack(fill="both", expand=True, padx=30, pady=20)

    box = ctk.CTkFrame(app._prot_auth_frame, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=15)
    box.place(relx=0.5, rely=0.5, anchor="center")

    ctk.CTkLabel(box, text="\U0001F512 Protected Area", font=("Helvetica", 24, "bold")).pack(pady=(30, 10), padx=50)
    ctk.CTkLabel(box, text="Enter password to access protected workflows.", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(pady=(0, 20))

    app._prot_pw_entry = ctk.CTkEntry(box, show="*", font=("Helvetica", 14), width=250, height=40, justify="center")
    app._prot_pw_entry.pack(pady=(0, 10))
    app._prot_pw_entry.bind("<Return>", lambda e: app._auth_protected())

    app._prot_err_lbl = ctk.CTkLabel(box, text="", font=("Helvetica", 12), text_color="#FF3B30")
    app._prot_err_lbl.pack(pady=(0, 10))

    btn_frame = ctk.CTkFrame(box, fg_color="transparent")
    btn_frame.pack(pady=(0, 30))

    ctk.CTkButton(btn_frame, text="Unlock", command=app._auth_protected, fg_color="#FFCC00", hover_color="#E6B800", font=("Helvetica", 14, "bold"), height=36, width=120).pack(side="left", padx=5)
    ctk.CTkButton(btn_frame, text="Forgot?", command=app._forgot_password, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), height=36, width=120).pack(side="left", padx=5)

    app._prot_main_frame = ctk.CTkFrame(parent, fg_color="transparent")

    hdr = ctk.CTkFrame(app._prot_main_frame, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)
    ctk.CTkLabel(hdr, text="Protected Workflows", font=("Helvetica", 28, "bold")).pack(side="left")
    app._prot_count_lbl = ctk.CTkLabel(hdr, text="  0 secured", font=("Helvetica", 14), text_color="#FFCC00")
    app._prot_count_lbl.pack(side="left", padx=10)

    btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_row.pack(side="right")
    ctk.CTkButton(btn_row, text="\U0001F512 Lock", command=app._lock_protected, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), width=100).pack(side="left")

    app._prot_scroll = ctk.CTkScrollableFrame(app._prot_main_frame, fg_color="transparent")
    app._prot_scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

import customtkinter as ctk
import webbrowser
from tkinter import filedialog


def build_settings(app, parent):
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.pack(fill="x", padx=30, pady=20)
    ctk.CTkLabel(hdr, text="Settings", font=("Helvetica", 28, "bold")).pack(side="left")

    sf = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    sf.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    sec1 = ctk.CTkFrame(sf, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
    sec1.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(sec1, text="GENERAL", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(15, 5))

    ctk.CTkSwitch(sec1, text="Dark Mode", variable=app.theme_var, onvalue="Dark", offvalue="Light", command=app._toggle_theme, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=10)
    ctk.CTkSwitch(sec1, text="Play sound on completion", variable=app.sound_var, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=10)
    ctk.CTkSwitch(sec1, text="Strip tracking parameters (UTM tags) from URLs", variable=app.strip_utm_var, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=10)
    ctk.CTkSwitch(sec1, text="Auto-Pin Tabs (where supported)", variable=app.auto_pin_var, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=10)
    ctk.CTkSwitch(sec1, text="Auto-Lock Protected Area on minimize/tray", variable=app.auto_lock_var, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=10)
    ctk.CTkSwitch(sec1, text="Disable Activity Log entirely", variable=app.disable_log_var, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=10)
    ctk.CTkSwitch(sec1, text="Dry Run mode (simulate opening tabs)", variable=app.dry_run, font=("Helvetica", 14)).pack(anchor="w", padx=20, pady=(10, 20))

    sec2 = ctk.CTkFrame(sf, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
    sec2.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(sec2, text="CUSTOM BROWSER", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(15, 5))
    ce = ctk.CTkEntry(sec2, textvariable=app.custom_exe, font=("Courier New", 14), height=35)
    ce.pack(fill="x", padx=20, pady=10)
    ctk.CTkButton(sec2, text="Browse...", command=lambda: app.custom_exe.set(filedialog.askopenfilename() or app.custom_exe.get()), fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF")).pack(anchor="w", padx=20, pady=(0, 20))

    sec_ext = ctk.CTkFrame(sf, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
    sec_ext.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(sec_ext, text="BROWSER EXTENSION", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(15, 5))
    ext_row = ctk.CTkFrame(sec_ext, fg_color="transparent")
    ext_row.pack(fill="x", padx=20, pady=10)
    ctk.CTkLabel(ext_row, text="Export Extension", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkLabel(ext_row, text="Save the extension files to a custom folder", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
    ctk.CTkButton(ext_row, text="Save Extension", command=app._save_extension_files, fg_color="#007AFF", width=120).pack(side="right")

    sec3 = ctk.CTkFrame(sf, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
    sec3.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(sec3, text="DATA MANAGEMENT", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(15, 5))

    # Backup
    bk_row = ctk.CTkFrame(sec3, fg_color="transparent")
    bk_row.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(bk_row, text="Local Backup", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkLabel(bk_row, text="Download a full backup of your data", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
    ctk.CTkButton(bk_row, text=" Backup", command=app._backup_data, fg_color="#007AFF", width=100).pack(side="right")

    # Restore
    rs_row = ctk.CTkFrame(sec3, fg_color="transparent")
    rs_row.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(rs_row, text="Restore Backup", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkLabel(rs_row, text="Restore your data from a JSON backup file", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
    ctk.CTkButton(rs_row, text=" Restore", command=app._restore_data, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), width=100).pack(side="right")

    # Google Drive Backup
    if app._gdrive_ok:
        gd_bk_row = ctk.CTkFrame(sec3, fg_color="transparent")
        gd_bk_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(gd_bk_row, text="Google Drive Backup", font=("Helvetica", 14)).pack(side="left")
        ctk.CTkLabel(gd_bk_row, text="Backup your data to Google Drive", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
        ctk.CTkButton(gd_bk_row, text=" Backup to Drive", command=app._backup_gdrive, fg_color="#34A853", hover_color="#2B8A44", width=140).pack(side="right")

        gd_rs_row = ctk.CTkFrame(sec3, fg_color="transparent")
        gd_rs_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(gd_rs_row, text="Google Drive Restore", font=("Helvetica", 14)).pack(side="left")
        ctk.CTkLabel(gd_rs_row, text="Restore your data from Google Drive", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
        ctk.CTkButton(gd_rs_row, text=" Restore from Drive", command=app._restore_gdrive, fg_color="#4285F4", hover_color="#3367D6", width=140).pack(side="right")
    else:
        gd_err_row = ctk.CTkFrame(sec3, fg_color="transparent")
        gd_err_row.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(gd_err_row, text="Google Drive API not installed. Run: pip install google-api-python-client google-auth-oauthlib", font=("Helvetica", 12), text_color="#FF3B30").pack(side="left")

    # Protected Area Password
    pw_row = ctk.CTkFrame(sec3, fg_color="transparent")
    pw_row.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(pw_row, text="Protected Area Password", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkLabel(pw_row, text="Set password for protected workflows", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
    ctk.CTkButton(pw_row, text="Change Password", command=app._change_password, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF"), width=120).pack(side="right")

    # Force Reset Password
    frp_row = ctk.CTkFrame(sec3, fg_color="transparent")
    frp_row.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(frp_row, text="Force Reset Password", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkLabel(frp_row, text="Deletes all protected workflows and resets password", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(side="left", padx=10)
    ctk.CTkButton(frp_row, text="Force Reset", command=app._force_reset_password, fg_color="transparent", border_width=1, text_color=("#FF3B30", "#FF453A"), border_color=("#FF3B30", "#FF453A"), hover_color=("#FF3B30", "#FF453A"), width=120).pack(side="right")

    # Reset Data
    rs_all_row = ctk.CTkFrame(sec3, fg_color="transparent")
    rs_all_row.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(rs_all_row, text="Reset All Data", font=("Helvetica", 14)).pack(side="left")
    ctk.CTkLabel(rs_all_row, text="Permanently delete all workflows and settings", font=("Helvetica", 12), text_color="#FF3B30").pack(side="left", padx=10)
    ctk.CTkButton(rs_all_row, text=" Reset", command=app._reset_all_data, fg_color="transparent", border_width=1, border_color="#FF3B30", text_color="#FF3B30", width=100).pack(side="right")

    ctk.CTkLabel(sec3, text="DATA FOLDER", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(15, 5))
    ctk.CTkLabel(sec3, text=app._app_dir, font=("Courier New", 14)).pack(anchor="w", padx=20, pady=5)
    ctk.CTkButton(sec3, text="Open Folder", command=app._open_data_folder, fg_color="transparent", border_width=1, text_color=("#000000", "#FFFFFF")).pack(anchor="w", padx=20, pady=(5, 20))

    sec4 = ctk.CTkFrame(sf, fg_color=("#FFFFFF", "#1C1C1E"), corner_radius=10)
    sec4.pack(fill="x", padx=30, pady=10)

    ctk.CTkLabel(sec4, text="DEVELOPER CREDITS", font=("Helvetica", 12, "bold"), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(15, 5))

    dev_row1 = ctk.CTkFrame(sec4, fg_color="transparent")
    dev_row1.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(dev_row1, text="Main Developer: Ash", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkButton(dev_row1, text="GitHub Profile", command=lambda: webbrowser.open("https://github.com/HFFX4"), fg_color="#007AFF", hover_color="#0056B3", width=120).pack(side="right")

    dev_row2 = ctk.CTkFrame(sec4, fg_color="transparent")
    dev_row2.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(dev_row2, text="Elvar Official", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkButton(dev_row2, text="GitHub Repo", command=lambda: webbrowser.open("https://github.com/get-elvar"), fg_color="#34C759", hover_color="#28A745", width=120).pack(side="right")

    dev_row3 = ctk.CTkFrame(sec4, fg_color="transparent")
    dev_row3.pack(fill="x", padx=20, pady=5)
    ctk.CTkLabel(dev_row3, text="Contributor: Ibrahimlaique54", font=("Helvetica", 14, "bold")).pack(side="left")
    ctk.CTkButton(dev_row3, text="GitHub Profile", command=lambda: webbrowser.open("https://github.com/Ibrahimlaique54"), fg_color="#5AC8FA", hover_color="#34AADC", width=120).pack(side="right")

    ctk.CTkLabel(sec4, text="Elvar is a powerful workflow automation tool inspired by systems-level architecture.", font=("Helvetica", 12), text_color=("#8E8E93", "#98989D")).pack(anchor="w", padx=20, pady=(10, 20))

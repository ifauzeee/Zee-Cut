"""
Toolbar frame creator for Zee-Cut main window.
"""

import customtkinter as ctk

from ui.theme import COLORS, FONTS


def create_toolbar(app):
    """Create the toolbar with interface selector, mode, theme, and action buttons."""
    app.toolbar_frame = ctk.CTkFrame(app, fg_color=COLORS["bg_card"], corner_radius=0, height=60)
    app.toolbar_frame.grid(row=1, column=0, sticky="ew", pady=(1, 0))
    app.toolbar_frame.grid_propagate(False)
    app.toolbar_frame.grid_columnconfigure(1, weight=1)

    left_toolbar = ctk.CTkFrame(app.toolbar_frame, fg_color="transparent")
    left_toolbar.grid(row=0, column=0, padx=16, pady=10, sticky="w")

    iface_label = ctk.CTkLabel(
        left_toolbar, text="Interface:",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    iface_label.pack(side="left", padx=(0, 8))

    app.iface_var = ctk.StringVar(value="Select interface...")
    app.iface_dropdown = ctk.CTkOptionMenu(
        left_toolbar, variable=app.iface_var, values=["Loading..."],
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        button_color=COLORS["accent_primary"],
        button_hover_color=COLORS["accent_primary_hover"],
        dropdown_fg_color=COLORS["bg_card"],
        dropdown_hover_color=COLORS["bg_card_hover"],
        corner_radius=8, width=190, command=app._on_interface_selected
    )
    app.iface_dropdown.pack(side="left", padx=(0, 12))

    mode_label = ctk.CTkLabel(
        left_toolbar, text="Mode:",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    mode_label.pack(side="left", padx=(0, 6))

    app.filter_mode_dropdown = ctk.CTkOptionMenu(
        left_toolbar, variable=app.filter_mode_var,
        values=["All Devices", "Targets Only", "Throttled Only", "Protected Only"],
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        button_color=COLORS["accent_primary"],
        button_hover_color=COLORS["accent_primary_hover"],
        dropdown_fg_color=COLORS["bg_card"],
        dropdown_hover_color=COLORS["bg_card_hover"],
        corner_radius=8, width=125, command=app._on_filter_mode_changed
    )
    app.filter_mode_dropdown.pack(side="left", padx=(0, 10))

    right_toolbar = ctk.CTkFrame(app.toolbar_frame, fg_color="transparent")
    right_toolbar.grid(row=0, column=1, padx=16, pady=10, sticky="e")

    theme_label = ctk.CTkLabel(
        right_toolbar, text="Theme:",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    theme_label.pack(side="left", padx=(0, 6))

    app.theme_dropdown = ctk.CTkOptionMenu(
        right_toolbar, variable=app.theme_var,
        values=list(app.theme_options.keys()),
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        button_color=COLORS["accent_primary"],
        button_hover_color=COLORS["accent_primary_hover"],
        dropdown_fg_color=COLORS["bg_card"],
        dropdown_hover_color=COLORS["bg_card_hover"],
        corner_radius=8, width=130, command=app._on_theme_changed
    )
    app.theme_dropdown.pack(side="left", padx=(0, 10))

    app.flush_arp_btn = ctk.CTkButton(
        right_toolbar, text="Flush ARP (Admin)",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=140, height=38, command=app._flush_arp_admin
    )
    app.flush_arp_btn.pack(side="left", padx=(0, 8))

    app.export_diag_btn = ctk.CTkButton(
        right_toolbar, text="Export Diagnostics",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=148, height=38, command=app._export_diagnostics
    )
    app.export_diag_btn.pack(side="left", padx=(0, 8))

    app.scan_btn = ctk.CTkButton(
        right_toolbar, text="Scan Network",
        font=FONTS["body_bold"], fg_color=COLORS["accent_primary"],
        hover_color=COLORS["accent_primary_hover"],
        corner_radius=8, width=130, height=38, command=app._scan_network
    )
    app.scan_btn.pack(side="left", padx=(0, 6))

    app.auto_scan_switch = ctk.CTkSwitch(
        right_toolbar, text="Auto",
        font=FONTS["small"], variable=app.auto_scan_enabled,
        onvalue=True, offvalue=False,
        button_color=COLORS["accent_primary"],
        progress_color=COLORS["accent_primary"],
        command=app._on_auto_scan_toggle, width=60
    )
    app.auto_scan_switch.pack(side="left", padx=(0, 4))

    app.auto_scan_interval_dropdown = ctk.CTkOptionMenu(
        right_toolbar, values=["2 min", "3 min", "5 min", "10 min"],
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        button_color=COLORS["accent_primary"],
        button_hover_color=COLORS["accent_primary_hover"],
        dropdown_fg_color=COLORS["bg_card"],
        dropdown_hover_color=COLORS["bg_card_hover"],
        corner_radius=8, width=72, command=app._on_auto_scan_interval_changed
    )
    interval_label = f"{app.auto_scan_interval} min"
    app.auto_scan_interval_dropdown.set(
        interval_label if interval_label in ["2 min", "3 min", "5 min", "10 min"] else "3 min"
    )
    app.auto_scan_interval_dropdown.pack(side="left", padx=(0, 6))

    app.dl_oui_btn = ctk.CTkButton(
        right_toolbar, text="DL OUI DB",
        font=FONTS["tiny"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_muted"],
        corner_radius=8, width=70, height=30, command=app._download_oui_db
    )
    app.dl_oui_btn.pack(side="left")

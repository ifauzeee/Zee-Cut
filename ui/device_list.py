"""
Device list container and rendering for Zee-Cut.
"""

import customtkinter as ctk

from core.models import NetworkDevice
from ui.theme import COLORS, FONTS

__all__ = [
    "create_device_container",
    "render_list_view",
    "render_empty_state",
    "populate_list_row",
]


def create_device_container(app):
    """Create the device list container with header, selection controls, and scroll frame."""
    container = ctk.CTkFrame(app, fg_color="transparent")
    container.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
    container.grid_rowconfigure(2, weight=1)
    container.grid_columnconfigure(0, weight=1)

    app.device_header = ctk.CTkLabel(
        container, text="Connected Devices (0)",
        font=FONTS["subtitle"], text_color=COLORS["text_primary"], anchor="w"
    )
    app.device_header.grid(row=0, column=0, sticky="w", pady=(0, 12))

    app.selection_controls = ctk.CTkFrame(
        container, fg_color=COLORS["bg_card"],
        corner_radius=8, border_width=1, border_color=COLORS["border"]
    )
    app.selection_controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    app.selection_controls.grid_columnconfigure(0, weight=1)
    app.selection_controls.grid_columnconfigure(1, weight=0)

    selection_left = ctk.CTkFrame(app.selection_controls, fg_color="transparent")
    selection_left.grid(row=0, column=0, padx=10, pady=8, sticky="w")

    app.check_all_btn = ctk.CTkButton(
        selection_left, text="Check All",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=90, height=30, command=app._check_all_targets
    )
    app.check_all_btn.pack(side="left", padx=(0, 8))

    app.clear_select_btn = ctk.CTkButton(
        selection_left, text="Clear",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=82, height=30, command=app._clear_selected_targets
    )
    app.clear_select_btn.pack(side="left", padx=(0, 10))

    app.protect_selected_btn = ctk.CTkButton(
        selection_left, text="Protect Selected",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=128, height=30, command=app._protect_selected_targets
    )
    app.protect_selected_btn.pack(side="left", padx=(0, 8))

    app.clear_safe_list_btn = ctk.CTkButton(
        selection_left, text="Clear Safe List",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=120, height=30, command=app._clear_custom_safe_list
    )
    app.clear_safe_list_btn.pack(side="left", padx=(0, 10))

    app.selected_count_label = ctk.CTkLabel(
        selection_left, text="Selected: 0",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    app.selected_count_label.pack(side="left", padx=(0, 10))

    app.safe_count_label = ctk.CTkLabel(
        selection_left, text="Safe: 0",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    app.safe_count_label.pack(side="left")

    # Bulk lag controls
    app.bulk_speed_frame = ctk.CTkFrame(app.selection_controls, fg_color="transparent")
    app.bulk_speed_frame.grid(row=0, column=1, padx=10, pady=8, sticky="e")

    app.bulk_speed_label = ctk.CTkLabel(
        app.bulk_speed_frame, text="Selected Lag",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    app.bulk_speed_label.pack(side="left", padx=(0, 8))

    app.bulk_speed_slider = ctk.CTkSlider(
        app.bulk_speed_frame, from_=0, to=100, number_of_steps=100, width=160,
        button_color=COLORS["accent_danger"], progress_color=COLORS["accent_danger"],
        button_hover_color=COLORS["accent_danger_hover"], command=app._on_bulk_speed_change
    )
    app.bulk_speed_slider.set(app.bulk_lag_percent)
    app.bulk_speed_slider.pack(side="left", padx=(0, 6))

    app.bulk_speed_value_label = ctk.CTkLabel(
        app.bulk_speed_frame, text=f"{app.bulk_lag_percent}%",
        font=FONTS["tiny"], text_color=COLORS["text_secondary"], width=36
    )
    app.bulk_speed_value_label.pack(side="left", padx=(0, 8))

    app.preset_label = ctk.CTkLabel(
        app.bulk_speed_frame, text="Preset",
        font=FONTS["small"], text_color=COLORS["text_secondary"]
    )
    app.preset_label.pack(side="left", padx=(4, 6))

    app.lag_preset_dropdown = ctk.CTkOptionMenu(
        app.bulk_speed_frame, variable=app.lag_preset_var,
        values=list(app.lag_presets.keys()),
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        button_color=COLORS["accent_primary"],
        button_hover_color=COLORS["accent_primary_hover"],
        dropdown_fg_color=COLORS["bg_card"],
        dropdown_hover_color=COLORS["bg_card_hover"],
        corner_radius=8, width=130
    )
    app.lag_preset_dropdown.pack(side="left", padx=(0, 6))

    app.apply_preset_btn = ctk.CTkButton(
        app.bulk_speed_frame, text="Apply Preset",
        font=FONTS["small"], fg_color=COLORS["accent_warning"],
        hover_color=COLORS["accent_warning_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=110, height=30, command=app._apply_preset_to_selected
    )
    app.apply_preset_btn.pack(side="left", padx=(0, 6))

    app.apply_selected_btn = ctk.CTkButton(
        app.bulk_speed_frame, text="Apply Selected",
        font=FONTS["small"], fg_color=COLORS["accent_danger"],
        hover_color=COLORS["accent_danger_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=120, height=30, command=app._apply_bulk_speed_to_selected
    )
    app.apply_selected_btn.pack(side="left")

    app.bulk_speed_frame.grid_remove()

    # Scrollable device list
    app.device_scroll = ctk.CTkScrollableFrame(
        container, fg_color="transparent", corner_radius=0,
        scrollbar_button_color=COLORS["border_light"],
        scrollbar_button_hover_color=COLORS["accent_primary"]
    )
    app.device_scroll.grid(row=2, column=0, sticky="nsew")
    app.device_scroll.grid_columnconfigure(0, weight=1)


def render_empty_state(scroll_frame, message="No devices found on this network."):
    """Render the empty state placeholder."""
    empty_state = ctk.CTkFrame(scroll_frame, fg_color="transparent")
    empty_state.grid(row=0, column=0, sticky="nsew", pady=80)

    ctk.CTkLabel(empty_state, text="📡", font=("Segoe UI Emoji", 48)).pack(pady=(0, 16))
    ctk.CTkLabel(
        empty_state, text="No Devices Found",
        font=FONTS["subtitle"], text_color=COLORS["text_secondary"]
    ).pack(pady=(0, 8))
    ctk.CTkLabel(
        empty_state, text=message,
        font=FONTS["small"], text_color=COLORS["text_muted"]
    ).pack()


def render_list_view(app, devices: list[NetworkDevice]):
    """Render the device list header and rows into the scroll frame."""
    scroll = app.device_scroll

    header = ctk.CTkFrame(
        scroll, fg_color=COLORS["bg_card"],
        corner_radius=8, border_width=1, border_color=COLORS["border"]
    )
    header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    _configure_list_columns(header, app)

    for idx, title in enumerate(["Sel", "Device", "IP", "MAC", "Vendor", "Type", "Lag %", "Status", "\u2191\u2193 KB/s"]):
        label = ctk.CTkLabel(
            header, text=title,
            font=FONTS["small"], text_color=COLORS["text_secondary"], anchor="center"
        )
        label.grid(row=0, column=idx, sticky="nsew", padx=6, pady=8)

    for idx, device in enumerate(devices, start=1):
        row = ctk.CTkFrame(
            scroll, fg_color=_get_row_color(app, device),
            corner_radius=8, border_width=1, border_color=COLORS["border"]
        )
        row.grid(row=idx, column=0, sticky="ew", pady=(0, 4))
        _configure_list_columns(row, app)
        populate_list_row(app, row, device)


def _configure_list_columns(frame: ctk.CTkFrame, app):
    """Apply column size configuration to a grid frame."""
    for col, minsize in app.list_column_minsize.items():
        frame.grid_columnconfigure(col, weight=1, minsize=minsize)


def populate_list_row(app, row: ctk.CTkFrame, device: NetworkDevice):
    """Populate a single device row with all control widgets."""

    # Column 0: selection checkbox
    if app._is_target_device(device):
        selected_var = ctk.IntVar(value=1 if device.ip in app.selected_target_ips else 0)
        select_box = ctk.CTkCheckBox(
            row, text="", width=18, checkbox_width=18, checkbox_height=18,
            corner_radius=4, border_width=2,
            fg_color=COLORS["accent_primary"], hover_color=COLORS["accent_primary_hover"],
            border_color=COLORS["border_light"], checkmark_color=COLORS["text_primary"],
            state="normal" if app._is_admin else "disabled",
            variable=selected_var,
            command=lambda ip=device.ip, var=selected_var: app._on_row_select_change(ip, var.get())
        )
        select_box.grid(row=0, column=0, sticky="nsew", padx=6, pady=8)
    else:
        ctk.CTkLabel(
            row, text="-", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="center"
        ).grid(row=0, column=0, sticky="nsew", padx=6, pady=8)

    # Columns 1-5: text data
    values = [
        _device_display_name(device),
        device.ip,
        device.mac.upper(),
        device.vendor if device.vendor != "Unknown" else "",
        _device_type_label(app, device),
    ]
    colors = [COLORS["text_primary"], COLORS["text_secondary"], COLORS["text_muted"], COLORS["text_muted"], COLORS["text_secondary"]]
    fonts = [FONTS["small"], FONTS["mono_small"], FONTS["mono_small"], FONTS["tiny"], FONTS["small"]]

    for idx, value in enumerate(values):
        ctk.CTkLabel(
            row, text=value, font=fonts[idx],
            text_color=colors[idx], anchor="center"
        ).grid(row=0, column=idx + 1, sticky="nsew", padx=4, pady=8)

    # Column 6: lag slider
    lag_frame = ctk.CTkFrame(row, fg_color="transparent")
    lag_frame.grid(row=0, column=6, sticky="nsew", padx=4, pady=6)
    lag_frame.grid_columnconfigure(0, weight=1)
    lag_frame.grid_columnconfigure(1, weight=1)

    if app._is_target_device(device):
        lag_var = ctk.IntVar(value=app._get_lag_percent(device.ip))
        lag_slider = ctk.CTkSlider(
            lag_frame, from_=0, to=100, number_of_steps=100, width=80,
            state="normal" if app._is_admin else "disabled",
            button_color=COLORS["accent_danger"], progress_color=COLORS["accent_danger"],
            button_hover_color=COLORS["accent_danger_hover"]
        )
        lag_value = ctk.CTkLabel(
            lag_frame, text=f"{lag_var.get()}%",
            font=FONTS["tiny"], text_color=COLORS["text_secondary"], width=28
        )

        def _make_on_lag_change(ip, var, label_ref):
            def on_lag_change(value):
                lag_percent = max(0, min(100, int(round(float(value)))))
                app._mark_lag_interaction()
                var.set(lag_percent)
                label_ref.configure(text=f"{lag_percent}%")
                app._set_lag_percent(ip, lag_percent)
                app._schedule_lag_apply(ip)
            return on_lag_change

        lag_slider.configure(command=_make_on_lag_change(device.ip, lag_var, lag_value))
        lag_slider.set(lag_var.get())
        lag_slider.grid(row=0, column=0, sticky="e", padx=(0, 4))
        lag_value.grid(row=0, column=1, sticky="w")
    else:
        ctk.CTkLabel(
            lag_frame, text="-", font=FONTS["small"],
            text_color=COLORS["text_muted"], anchor="center"
        ).grid(row=0, column=0, columnspan=2, sticky="nsew")

    # Column 7: status
    ctk.CTkLabel(
        row, text=_device_status_label(app, device),
        font=FONTS["small"], text_color=_status_color(app, device), anchor="center"
    ).grid(row=0, column=7, sticky="nsew", padx=4, pady=8)

    # Column 8: bandwidth
    bw_label = ctk.CTkLabel(
        row, text="", font=FONTS["tiny"],
        text_color=COLORS["text_muted"], anchor="center"
    )
    bw_label.grid(row=0, column=8, sticky="nsew", padx=4, pady=8)
    if not hasattr(row, "bw_labels"):
        row.bw_labels = []
    row.bw_labels.append((device.mac, bw_label))
    _update_bw_label(app, bw_label, device.mac)


def _update_bw_label(app, label: ctk.CTkLabel, mac: str):
    """Update a single bandwidth label with current rates."""
    mac_key = mac.lower().replace("-", ":")
    rates = app._bandwidth.get_rates(mac_key)
    up = rates.get("up_kbps", 0.0)
    down = rates.get("down_kbps", 0.0)
    if up < 0.01 and down < 0.01:
        label.configure(text="")
    else:
        label.configure(text=f"\u2191{up:.1f} \u2193{down:.1f}")


def refresh_bandwidth_labels(app):
    """Update bandwidth labels for all visible device rows."""
    if not hasattr(app, "device_scroll"):
        return
    for widget in app.device_scroll.winfo_children():
        if isinstance(widget, ctk.CTkFrame) and hasattr(widget, "bw_labels"):
            for mac, label_ref in widget.bw_labels:
                try:
                    _update_bw_label(app, label_ref, mac)
                except Exception:
                    pass


def _device_display_name(device: NetworkDevice) -> str:
    if device.is_self:
        return f"{device.hostname} (You)"
    if device.is_gateway:
        return f"{device.hostname} (Gateway)"
    return device.hostname


def _device_type_label(app, device: NetworkDevice) -> str:
    if device.is_self:
        return "Self"
    if device.is_gateway:
        return "Gateway"
    if app._is_custom_protected_ip(device.ip):
        return "Protected"
    return "Target"


def _device_status_label(app, device: NetworkDevice) -> str:
    if app._is_custom_protected_ip(device.ip):
        return "Protected"
    return "Throttled" if device.is_throttled else "Normal"


def _status_color(app, device: NetworkDevice) -> str:
    if app._is_custom_protected_ip(device.ip):
        return COLORS["accent_warning"]
    return COLORS["accent_danger"] if device.is_throttled else COLORS["accent_success"]


def _get_row_color(app, device: NetworkDevice) -> str:
    if device.is_self:
        return COLORS["self_bg"]
    if device.is_gateway:
        return COLORS["gateway_bg"]
    if app._is_custom_protected_ip(device.ip):
        return COLORS["bg_input"]
    if device.is_throttled:
        return COLORS["throttled_bg"]
    return COLORS["bg_card"]

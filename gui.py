"""
Zee-Cut - Modern GUI Application
Advanced WiFi Network Device Controller.
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
import time
import sys
import os
from typing import Optional

from core.network import NetworkEngine, NetworkDevice, NetworkInterface

# ─── Theme Configuration ───────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Color palette
COLORS = {
    "bg_dark": "#0a0e17",
    "bg_card": "#111827",
    "bg_card_hover": "#1a2332",
    "bg_input": "#1e293b",
    "accent_primary": "#6366f1",
    "accent_primary_hover": "#818cf8",
    "accent_danger": "#ef4444",
    "accent_danger_hover": "#f87171",
    "accent_success": "#10b981",
    "accent_success_hover": "#34d399",
    "accent_warning": "#f59e0b",
    "accent_warning_hover": "#fbbf24",
    "text_primary": "#f1f5f9",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "border": "#1e293b",
    "border_light": "#334155",
    "gradient_start": "#6366f1",
    "gradient_end": "#8b5cf6",
    "throttled_bg": "#1c1017",
    "normal_bg": "#111827",
    "self_bg": "#0d1a2d",
    "gateway_bg": "#0d1f17",
}

FONTS = {
    "title": ("Segoe UI", 24, "bold"),
    "subtitle": ("Segoe UI", 16, "bold"),
    "heading": ("Segoe UI", 14, "bold"),
    "body": ("Segoe UI", 13),
    "body_bold": ("Segoe UI", 13, "bold"),
    "small": ("Segoe UI", 11),
    "tiny": ("Segoe UI", 10),
    "mono": ("Cascadia Code", 12),
    "mono_small": ("Cascadia Code", 11),
    "icon": ("Segoe UI Emoji", 16),
    "icon_large": ("Segoe UI Emoji", 22),
}


class DeviceCard(ctk.CTkFrame):
    """Individual device card widget with per-device selection and lag speed."""

    def __init__(
        self,
        master,
        device: NetworkDevice,
        on_throttle,
        on_restore,
        is_selected,
        on_selected_changed,
        get_lag_percent,
        on_lag_percent_changed,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.device = device
        self.on_throttle = on_throttle
        self.on_restore = on_restore
        self.is_selected = is_selected
        self.on_selected_changed = on_selected_changed
        self.get_lag_percent = get_lag_percent
        self.on_lag_percent_changed = on_lag_percent_changed

        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        if self.device.is_self:
            bg = COLORS["self_bg"]
        elif self.device.is_gateway:
            bg = COLORS["gateway_bg"]
        elif self.device.is_throttled:
            bg = COLORS["throttled_bg"]
        else:
            bg = COLORS["bg_card"]

        self.configure(
            fg_color=bg,
            corner_radius=12,
            border_width=1,
            border_color=COLORS["border"]
        )

    def _create_widgets(self):
        self.grid_columnconfigure(1, weight=1)

        if self.device.is_self:
            icon = "PC"
            status_color = COLORS["accent_primary"]
        elif self.device.is_gateway:
            icon = "GW"
            status_color = COLORS["accent_success"]
        elif self.device.is_throttled:
            icon = "TH"
            status_color = COLORS["accent_danger"]
        else:
            icon = "DV"
            status_color = COLORS["text_muted"]

        icon_frame = ctk.CTkFrame(self, fg_color="transparent", width=50)
        icon_frame.grid(row=0, column=0, rowspan=3, padx=(16, 8), pady=12, sticky="ns")
        icon_frame.grid_propagate(False)

        icon_label = ctk.CTkLabel(
            icon_frame, text=icon, font=FONTS["small"],
            text_color=COLORS["text_primary"]
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        dot_frame = ctk.CTkFrame(
            icon_frame, width=12, height=12,
            corner_radius=6, fg_color=status_color
        )
        dot_frame.place(relx=0.85, rely=0.2, anchor="center")

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, rowspan=3, padx=4, pady=12, sticky="nsew")

        label_text = self.device.hostname
        if self.device.is_self:
            label_text += "  (You)"
        elif self.device.is_gateway:
            label_text += "  (Gateway)"

        hostname_label = ctk.CTkLabel(
            info_frame, text=label_text,
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        hostname_label.pack(fill="x", pady=(0, 2))

        ip_label = ctk.CTkLabel(
            info_frame, text=f"IP: {self.device.ip}",
            font=FONTS["mono_small"],
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        ip_label.pack(fill="x", pady=(0, 1))

        mac_label = ctk.CTkLabel(
            info_frame, text=f"MAC: {self.device.mac.upper()}",
            font=FONTS["mono_small"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        mac_label.pack(fill="x")

        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=0, column=2, rowspan=3, padx=16, pady=10, sticky="e")

        if self.device.is_self or self.device.is_gateway:
            protected = ctk.CTkLabel(
                action_frame,
                text="Protected",
                font=FONTS["tiny"],
                text_color=COLORS["text_muted"]
            )
            protected.pack(pady=(10, 0))
            return

        self.selected_var = ctk.BooleanVar(value=self.is_selected)
        select_cb = ctk.CTkCheckBox(
            action_frame,
            text="Select",
            variable=self.selected_var,
            font=FONTS["tiny"],
            command=self._on_select_changed,
            checkbox_width=16,
            checkbox_height=16
        )
        select_cb.pack(anchor="e", pady=(0, 4))

        initial_lag = int(self.get_lag_percent(self.device.ip))
        self.lag_percent_var = ctk.IntVar(value=max(0, min(100, initial_lag)))

        lag_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        lag_row.pack(fill="x", pady=(0, 4))
        lag_row.grid_columnconfigure(0, weight=1)

        self.lag_slider = ctk.CTkSlider(
            lag_row,
            from_=0,
            to=100,
            number_of_steps=100,
            width=120,
            button_color=COLORS["accent_danger"],
            progress_color=COLORS["accent_danger"],
            button_hover_color=COLORS["accent_danger_hover"],
            command=self._on_lag_percent_changed
        )
        self.lag_slider.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.lag_slider.set(self.lag_percent_var.get())

        self.lag_value_label = ctk.CTkLabel(
            lag_row,
            text=f"{self.lag_percent_var.get()}%",
            font=FONTS["tiny"],
            text_color=COLORS["text_secondary"],
            width=34
        )
        self.lag_value_label.grid(row=0, column=1, sticky="e")

        if self.device.is_throttled:
            restore_btn = ctk.CTkButton(
                action_frame,
                text="Restore",
                font=FONTS["small"],
                fg_color=COLORS["accent_success"],
                hover_color=COLORS["accent_success_hover"],
                text_color="white",
                corner_radius=8,
                width=120,
                height=32,
                command=lambda: self.on_restore(self.device.ip)
            )
            restore_btn.pack(pady=(2, 0))
        else:
            lag_btn = ctk.CTkButton(
                action_frame,
                text="Lag Device",
                font=FONTS["small"],
                fg_color=COLORS["accent_danger"],
                hover_color=COLORS["accent_danger_hover"],
                text_color="white",
                corner_radius=8,
                width=120,
                height=32,
                command=lambda: self.on_throttle(self.device.ip, self._get_throttle_level())
            )
            lag_btn.pack(pady=(2, 0))

    def _on_select_changed(self):
        self.on_selected_changed(self.device.ip, bool(self.selected_var.get()))

    def _on_lag_percent_changed(self, value: float):
        lag_percent = max(0, min(100, int(round(float(value)))))
        self.lag_percent_var.set(lag_percent)
        self.lag_value_label.configure(text=f"{lag_percent}%")
        self.on_lag_percent_changed(self.device.ip, lag_percent)

    def _get_throttle_level(self) -> int:
        return 100 - int(self.lag_percent_var.get())


class WiFiThrottlerApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.engine = NetworkEngine()
        self.engine.on_devices_updated = self._on_devices_updated
        self.engine.on_status_changed = self._on_status_changed
        self.view_mode_var = ctk.StringVar(value="Card View")
        self.filter_mode_var = ctk.StringVar(value="All Devices")
        self.selected_device_ips: set[str] = set()
        self.device_lag_percents: dict[str, int] = {}

        self._setup_window()
        self._create_layout()
        self._check_admin()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self):
        self.title("Zee-Cut - Network Device Controller")
        self.geometry("920x720")
        self.minsize(800, 600)
        self.configure(fg_color=COLORS["bg_dark"])

        try:
            if getattr(sys, 'frozen', False):
                base = sys._MEIPASS
            else:
                base = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base, "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _create_layout(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._create_header()
        self._create_toolbar()
        self._create_device_list()
        self._create_statusbar()

    # ─── Header ─────────────────────────────────────────────────────────

    def _create_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=80)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(1, weight=1)

        # App icon and title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=24, pady=16, sticky="w")

        app_icon = ctk.CTkLabel(
            title_frame, text="📡",
            font=("Segoe UI Emoji", 30)
        )
        app_icon.pack(side="left", padx=(0, 12))

        title_text = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_text.pack(side="left")

        title = ctk.CTkLabel(
            title_text, text="Zee-Cut",
            font=FONTS["title"],
            text_color=COLORS["text_primary"]
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            title_text, text="Network Device Controller",
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        subtitle.pack(anchor="w")

        # Admin badge
        self.admin_badge = ctk.CTkLabel(
            header, text="",
            font=FONTS["tiny"],
            corner_radius=6,
        )
        self.admin_badge.grid(row=0, column=1, padx=24, pady=16, sticky="e")

    # ─── Toolbar ────────────────────────────────────────────────────────

    def _create_toolbar(self):
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=60)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(1, weight=1)

        left_toolbar = ctk.CTkFrame(toolbar, fg_color="transparent")
        left_toolbar.grid(row=0, column=0, padx=16, pady=10, sticky="w")

        # Interface selector
        iface_label = ctk.CTkLabel(
            left_toolbar, text="Interface:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        iface_label.pack(side="left", padx=(0, 8))

        self.iface_var = ctk.StringVar(value="Select interface...")
        self.iface_dropdown = ctk.CTkOptionMenu(
            left_toolbar,
            variable=self.iface_var,
            values=["Loading..."],
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_primary"],
            button_hover_color=COLORS["accent_primary_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=190,
            command=self._on_interface_selected
        )
        self.iface_dropdown.pack(side="left", padx=(0, 12))

        view_label = ctk.CTkLabel(
            left_toolbar,
            text="View:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        view_label.pack(side="left", padx=(0, 6))

        self.view_mode_dropdown = ctk.CTkOptionMenu(
            left_toolbar,
            variable=self.view_mode_var,
            values=["Card View", "List View", "Compact View"],
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_primary"],
            button_hover_color=COLORS["accent_primary_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=105,
            command=self._on_view_mode_changed
        )
        self.view_mode_dropdown.pack(side="left", padx=(0, 10))

        mode_label = ctk.CTkLabel(
            left_toolbar,
            text="Mode:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        mode_label.pack(side="left", padx=(0, 6))

        self.filter_mode_dropdown = ctk.CTkOptionMenu(
            left_toolbar,
            variable=self.filter_mode_var,
            values=["All Devices", "Targets Only", "Throttled Only", "Protected Only"],
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_primary"],
            button_hover_color=COLORS["accent_primary_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=125,
            command=self._on_filter_mode_changed
        )
        self.filter_mode_dropdown.pack(side="left", padx=(0, 10))

        # Right toolbar buttons
        right_toolbar = ctk.CTkFrame(toolbar, fg_color="transparent")
        right_toolbar.grid(row=0, column=1, padx=16, pady=10, sticky="e")

        # Scan button
        self.scan_btn = ctk.CTkButton(
            right_toolbar,
            text="🔍 Scan Network",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_primary_hover"],
            corner_radius=8,
            width=130,
            height=38,
            command=self._scan_network
        )
        self.scan_btn.pack(side="left", padx=(0, 8))

        # Restore All button
        self.restore_all_btn = ctk.CTkButton(
            right_toolbar,
            text="✅ Restore All",
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_success"],
            hover_color=COLORS["accent_success_hover"],
            corner_radius=8,
            width=120,
            height=38,
            command=self._restore_all
        )
        self.restore_all_btn.pack(side="left")

    # ─── Device List ────────────────────────────────────────────────────

    def _create_device_list(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0)

        # Device count header
        self.device_header = ctk.CTkLabel(
            container,
            text="📋 Connected Devices (0)",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.device_header.grid(row=0, column=0, sticky="w", pady=(0, 12))

        batch_controls = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        batch_controls.grid(row=0, column=1, sticky="e", pady=(0, 12))

        self.check_all_btn = ctk.CTkButton(
            batch_controls,
            text="Check All",
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=90,
            height=30,
            command=self._toggle_select_all
        )
        self.check_all_btn.pack(side="left", padx=(8, 6), pady=6)

        self.clear_selection_btn = ctk.CTkButton(
            batch_controls,
            text="Clear",
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=70,
            height=30,
            command=self._clear_selection
        )
        self.clear_selection_btn.pack(side="left", padx=(0, 6), pady=6)

        self.lag_selected_btn = ctk.CTkButton(
            batch_controls,
            text="Lag Selected (0)",
            font=FONTS["small"],
            fg_color=COLORS["accent_danger"],
            hover_color=COLORS["accent_danger_hover"],
            corner_radius=8,
            width=130,
            height=30,
            command=self._lag_selected
        )
        self.lag_selected_btn.pack(side="left", padx=(0, 6), pady=6)

        self.restore_selected_btn = ctk.CTkButton(
            batch_controls,
            text="Restore Selected (0)",
            font=FONTS["small"],
            fg_color=COLORS["accent_success"],
            hover_color=COLORS["accent_success_hover"],
            corner_radius=8,
            width=150,
            height=30,
            command=self._restore_selected
        )
        self.restore_selected_btn.pack(side="left", padx=(0, 8), pady=6)
        self._refresh_batch_controls()

        # Scrollable device list
        self.device_scroll = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border_light"],
            scrollbar_button_hover_color=COLORS["accent_primary"]
        )
        self.device_scroll.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.device_scroll.grid_columnconfigure(0, weight=1)

        # Empty state
        self.empty_state = ctk.CTkFrame(self.device_scroll, fg_color="transparent")
        self.empty_state.grid(row=0, column=0, sticky="nsew", pady=80)

        empty_icon = ctk.CTkLabel(
            self.empty_state, text="📡",
            font=("Segoe UI Emoji", 48)
        )
        empty_icon.pack(pady=(0, 16))

        empty_title = ctk.CTkLabel(
            self.empty_state,
            text="No Devices Found",
            font=FONTS["subtitle"],
            text_color=COLORS["text_secondary"]
        )
        empty_title.pack(pady=(0, 8))

        empty_desc = ctk.CTkLabel(
            self.empty_state,
            text="Select a network interface and click 'Scan Network' to discover devices",
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        empty_desc.pack()

    # ─── Status Bar ─────────────────────────────────────────────────────

    def _create_statusbar(self):
        statusbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=32)
        statusbar.grid(row=3, column=0, sticky="ew")
        statusbar.grid_propagate(False)
        statusbar.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            statusbar,
            text="Ready - Select an interface to begin",
            font=FONTS["tiny"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=4, sticky="w")

        self.throttle_count_label = ctk.CTkLabel(
            statusbar,
            text="Throttled: 0",
            font=FONTS["tiny"],
            text_color=COLORS["accent_warning"],
            anchor="e"
        )
        self.throttle_count_label.grid(row=0, column=1, padx=16, pady=4, sticky="e")

    # ─── Logic ──────────────────────────────────────────────────────────

    def _check_admin(self):
        is_admin = self.engine.is_admin()
        if is_admin:
            self.admin_badge.configure(
                text="🛡️ Administrator",
                text_color=COLORS["accent_success"],
                fg_color=COLORS["gateway_bg"]
            )
            self._load_interfaces()
            self.engine.enable_ip_forwarding()
        else:
            self.admin_badge.configure(
                text="⚠️ Not Admin",
                text_color=COLORS["accent_warning"],
                fg_color=COLORS["throttled_bg"]
            )
            self._show_admin_warning()
            self._load_interfaces()

    def _show_admin_warning(self):
        messagebox.showwarning(
            "Administrator Required",
            "Zee-Cut needs Administrator privileges to function.\n\n"
            "Please right-click the application and select 'Run as administrator'.\n\n"
            "Without admin rights, scanning and throttling will not work."
        )

    def _load_interfaces(self):
        def _load():
            interfaces = self.engine.get_interfaces()
            self._interfaces = {
                f"{iface.display_name} ({iface.ip})": iface
                for iface in interfaces
            }
            names = list(self._interfaces.keys())
            if not names:
                names = ["No interfaces found"]

            self.after(0, lambda: self._update_interface_list(names))

        self._interfaces = {}
        threading.Thread(target=_load, daemon=True).start()

    def _update_interface_list(self, names: list):
        self.iface_dropdown.configure(values=names)
        if names and names[0] != "No interfaces found":
            self.iface_var.set(names[0])
            self._on_interface_selected(names[0])

    def _on_interface_selected(self, choice: str):
        if choice in self._interfaces:
            iface = self._interfaces[choice]
            self.engine.set_interface(iface)
            self._update_status(
                f"Interface: {iface.display_name} | IP: {iface.ip} | Gateway: {iface.gateway_ip}"
            )

    def _on_view_mode_changed(self, _choice: str):
        self._refresh_device_list()

    def _on_filter_mode_changed(self, _choice: str):
        self._refresh_device_list()

    def _is_target_device(self, device: NetworkDevice) -> bool:
        return not device.is_self and not device.is_gateway

    def _lag_percent_to_level(self, lag_percent: int) -> int:
        lag_percent = max(0, min(100, int(lag_percent)))
        return 100 - lag_percent

    def _get_lag_percent(self, ip: str) -> int:
        return max(0, min(100, int(self.device_lag_percents.get(ip, 100))))

    def _set_lag_percent(self, ip: str, lag_percent: int):
        self.device_lag_percents[ip] = max(0, min(100, int(lag_percent)))

    def _set_device_selected(self, ip: str, selected: bool):
        if selected:
            self.selected_device_ips.add(ip)
        else:
            self.selected_device_ips.discard(ip)
        self._refresh_batch_controls()

    def _sync_device_control_state(self, devices: list[NetworkDevice]):
        target_ips = {d.ip for d in devices if self._is_target_device(d)}
        self.selected_device_ips = {ip for ip in self.selected_device_ips if ip in target_ips}
        self.device_lag_percents = {
            ip: percent for ip, percent in self.device_lag_percents.items()
            if ip in target_ips
        }
        for ip in target_ips:
            self.device_lag_percents.setdefault(ip, 100)
        self._refresh_batch_controls()

    def _refresh_batch_controls(self):
        if not hasattr(self, "lag_selected_btn"):
            return
        selected_count = len(self.selected_device_ips)
        self.lag_selected_btn.configure(text=f"Lag Selected ({selected_count})")
        if hasattr(self, "restore_selected_btn"):
            selected_throttled_count = len([
                ip for ip in self.selected_device_ips
                if ip in self.engine.devices and self.engine.devices[ip].is_throttled
            ])
            self.restore_selected_btn.configure(
                text=f"Restore Selected ({selected_throttled_count})"
            )

        target_count = len([
            d for d in self.engine.devices.values()
            if self._is_target_device(d)
        ])
        if hasattr(self, "check_all_btn"):
            if target_count > 0 and selected_count == target_count:
                self.check_all_btn.configure(text="Uncheck All")
            else:
                self.check_all_btn.configure(text="Check All")

    def _toggle_select_all(self):
        target_ips = {
            d.ip for d in self.engine.devices.values()
            if self._is_target_device(d)
        }
        if not target_ips:
            messagebox.showinfo("Info", "No target devices available.")
            return

        if target_ips.issubset(self.selected_device_ips):
            self.selected_device_ips.difference_update(target_ips)
        else:
            self.selected_device_ips.update(target_ips)
            for ip in target_ips:
                self.device_lag_percents.setdefault(ip, 100)

        self._refresh_batch_controls()
        self._refresh_device_list()

    def _clear_selection(self):
        self.selected_device_ips.clear()
        self._refresh_batch_controls()
        self._refresh_device_list()

    def _lag_selected(self):
        selected_ips = [
            ip for ip in self.selected_device_ips
            if ip in self.engine.devices and self._is_target_device(self.engine.devices[ip])
        ]
        if not selected_ips:
            messagebox.showinfo("Info", "Belum ada device yang dipilih.")
            return

        actionable = []
        skipped = 0
        for ip in selected_ips:
            lag_percent = self._get_lag_percent(ip)
            level = self._lag_percent_to_level(lag_percent)
            if lag_percent <= 0 or level >= 100:
                skipped += 1
                continue
            actionable.append((ip, level, lag_percent))

        if not actionable:
            messagebox.showinfo(
                "Lag Selected",
                "Semua device terpilih punya lag 0%.\nNaikkan lag speed per device dulu."
            )
            return

        confirm = messagebox.askyesno(
            "Confirm Lag Selected",
            f"Lag {len(actionable)} selected device(s)?\nSkipped (0%): {skipped}"
        )
        if not confirm:
            return

        for ip, level, _lag_percent in actionable:
            threading.Thread(
                target=self.engine.throttle_device,
                args=(ip, level),
                daemon=True
            ).start()

    def _restore_selected(self):
        selected_ips = [
            ip for ip in self.selected_device_ips
            if ip in self.engine.devices and self._is_target_device(self.engine.devices[ip])
        ]
        if not selected_ips:
            messagebox.showinfo("Info", "Belum ada device yang dipilih.")
            return

        restore_targets = [
            ip for ip in selected_ips
            if self.engine.devices[ip].is_throttled
        ]
        if not restore_targets:
            messagebox.showinfo(
                "Restore Selected",
                "Tidak ada device terpilih yang sedang di-throttle."
            )
            return

        confirm = messagebox.askyesno(
            "Confirm Restore Selected",
            f"Restore {len(restore_targets)} selected throttled device(s)?"
        )
        if not confirm:
            return

        for ip in restore_targets:
            threading.Thread(
                target=self.engine.restore_device,
                args=(ip,),
                daemon=True
            ).start()

    def _scan_network(self):
        if not self.engine.interface:
            messagebox.showwarning("Warning", "Please select a network interface first.")
            return

        self.scan_btn.configure(state="disabled", text="⏳ Scanning...")
        self.engine.scan_network(callback=self._on_scan_complete)

    def _on_scan_complete(self):
        self.after(0, lambda: self.scan_btn.configure(state="normal", text="🔍 Scan Network"))

    def _on_devices_updated(self):
        self.after(0, self._refresh_device_list)

    def _on_status_changed(self, message: str):
        self.after(0, lambda: self._update_status(message))

    def _update_status(self, message: str):
        self.status_label.configure(text=message)

        throttled = sum(1 for d in self.engine.devices.values() if d.is_throttled)
        self.throttle_count_label.configure(text=f"Throttled: {throttled}")

    def _refresh_device_list(self):
        if not hasattr(self, "device_scroll"):
            return

        for widget in self.device_scroll.winfo_children():
            widget.destroy()

        all_devices = sorted(
            self.engine.devices.values(),
            key=lambda d: (
                not d.is_self,
                not d.is_gateway,
                not d.is_throttled,
                [int(x) for x in d.ip.split('.')]
            )
        )
        self._sync_device_control_state(all_devices)

        if not all_devices:
            self.device_header.configure(text="Connected Devices (0)")
            self._render_empty_state("No devices found on this network.")
            self.throttle_count_label.configure(text="Throttled: 0")
            return

        filtered_devices = self._filter_devices(all_devices)
        self.device_header.configure(
            text=f"Connected Devices ({len(filtered_devices)}/{len(all_devices)})"
        )

        if not filtered_devices:
            self._render_empty_state(
                f"No device matches mode '{self.filter_mode_var.get()}'."
            )
        else:
            view_mode = self.view_mode_var.get()
            if view_mode == "List View":
                self._render_list_view(filtered_devices)
            elif view_mode == "Compact View":
                self._render_compact_view(filtered_devices)
            else:
                self._render_card_view(filtered_devices)

        throttled = sum(1 for d in all_devices if d.is_throttled)
        self.throttle_count_label.configure(text=f"Throttled: {throttled}")

    def _filter_devices(self, devices: list[NetworkDevice]) -> list[NetworkDevice]:
        mode = self.filter_mode_var.get()
        if mode == "Targets Only":
            return [d for d in devices if not d.is_self and not d.is_gateway]
        if mode == "Throttled Only":
            return [d for d in devices if d.is_throttled]
        if mode == "Protected Only":
            return [d for d in devices if d.is_self or d.is_gateway]
        return devices

    def _render_empty_state(self, message: str):
        self.empty_state = ctk.CTkFrame(self.device_scroll, fg_color="transparent")
        self.empty_state.grid(row=0, column=0, sticky="nsew", pady=80)

        empty_icon = ctk.CTkLabel(
            self.empty_state,
            text="📡",
            font=("Segoe UI Emoji", 48)
        )
        empty_icon.pack(pady=(0, 16))

        empty_title = ctk.CTkLabel(
            self.empty_state,
            text="No Devices Found",
            font=FONTS["subtitle"],
            text_color=COLORS["text_secondary"]
        )
        empty_title.pack(pady=(0, 8))

        empty_desc = ctk.CTkLabel(
            self.empty_state,
            text=message,
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        empty_desc.pack()

    def _render_card_view(self, devices: list[NetworkDevice]):
        for idx, device in enumerate(devices):
            card = DeviceCard(
                self.device_scroll,
                device=device,
                on_throttle=self._throttle_device,
                on_restore=self._restore_device,
                is_selected=(device.ip in self.selected_device_ips),
                on_selected_changed=self._set_device_selected,
                get_lag_percent=self._get_lag_percent,
                on_lag_percent_changed=self._set_lag_percent
            )
            card.grid(row=idx, column=0, sticky="ew", pady=(0, 6))

    def _render_list_view(self, devices: list[NetworkDevice]):
        header = ctk.CTkFrame(
            self.device_scroll,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self._configure_list_columns(header)

        for idx, title in enumerate(["Sel", "Device", "IP", "MAC", "Type", "Lag %", "Status", "Action"]):
            label = ctk.CTkLabel(
                header,
                text=title,
                font=FONTS["small"],
                text_color=COLORS["text_secondary"],
                anchor="w"
            )
            label.grid(row=0, column=idx, sticky="w", padx=8, pady=8)

        for idx, device in enumerate(devices, start=1):
            row = ctk.CTkFrame(
                self.device_scroll,
                fg_color=self._get_row_color(device),
                corner_radius=8,
                border_width=1,
                border_color=COLORS["border"]
            )
            row.grid(row=idx, column=0, sticky="ew", pady=(0, 4))
            self._configure_list_columns(row)
            self._populate_list_row(row, device)

    def _render_compact_view(self, devices: list[NetworkDevice]):
        for idx, device in enumerate(devices):
            row = ctk.CTkFrame(
                self.device_scroll,
                fg_color=self._get_row_color(device),
                corner_radius=8,
                border_width=1,
                border_color=COLORS["border"]
            )
            row.grid(row=idx, column=0, sticky="ew", pady=(0, 4))
            row.grid_columnconfigure(1, weight=1)

            if self._is_target_device(device):
                selected_var = ctk.BooleanVar(value=(device.ip in self.selected_device_ips))
                select_cb = ctk.CTkCheckBox(
                    row,
                    text="",
                    variable=selected_var,
                    width=16,
                    checkbox_width=16,
                    checkbox_height=16,
                    command=lambda ip=device.ip, var=selected_var: self._set_device_selected(ip, bool(var.get()))
                )
                select_cb.grid(row=0, column=0, sticky="w", padx=(8, 2), pady=8)
            else:
                spacer = ctk.CTkLabel(row, text=" ", width=16)
                spacer.grid(row=0, column=0, padx=(8, 2), pady=8)

            summary = (
                f"{self._device_display_name(device)} | "
                f"{device.ip} | {self._device_status_label(device)}"
            )
            label = ctk.CTkLabel(
                row,
                text=summary,
                font=FONTS["small"],
                text_color=COLORS["text_primary"],
                anchor="w"
            )
            label.grid(row=0, column=1, sticky="w", padx=8, pady=8)

            lag_frame = ctk.CTkFrame(row, fg_color="transparent")
            lag_frame.grid(row=0, column=2, sticky="e", padx=(4, 6), pady=6)
            if self._is_target_device(device):
                lag_var = ctk.IntVar(value=self._get_lag_percent(device.ip))
                lag_slider = ctk.CTkSlider(
                    lag_frame,
                    from_=0,
                    to=100,
                    number_of_steps=100,
                    width=90,
                    button_color=COLORS["accent_danger"],
                    progress_color=COLORS["accent_danger"],
                    button_hover_color=COLORS["accent_danger_hover"],
                    command=lambda value, ip=device.ip, var=lag_var, label_ref=None: None
                )
                lag_value = ctk.CTkLabel(
                    lag_frame,
                    text=f"{lag_var.get()}%",
                    font=FONTS["tiny"],
                    text_color=COLORS["text_secondary"],
                    width=30
                )

                def on_lag_change(value, ip=device.ip, var=lag_var, label_ref=lag_value):
                    lag_percent = max(0, min(100, int(round(float(value)))))
                    var.set(lag_percent)
                    label_ref.configure(text=f"{lag_percent}%")
                    self._set_lag_percent(ip, lag_percent)

                lag_slider.configure(command=on_lag_change)
                lag_slider.set(lag_var.get())
                lag_slider.pack(side="left", padx=(0, 4))
                lag_value.pack(side="left")
            else:
                lag_na = ctk.CTkLabel(
                    lag_frame,
                    text="-",
                    font=FONTS["small"],
                    text_color=COLORS["text_muted"]
                )
                lag_na.pack()

            action_frame = ctk.CTkFrame(row, fg_color="transparent")
            action_frame.grid(row=0, column=3, sticky="e", padx=(0, 10), pady=6)
            self._create_action_widget(action_frame, device)

    def _configure_list_columns(self, frame: ctk.CTkFrame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=3)
        frame.grid_columnconfigure(2, weight=2)
        frame.grid_columnconfigure(3, weight=3)
        frame.grid_columnconfigure(4, weight=2)
        frame.grid_columnconfigure(5, weight=3)
        frame.grid_columnconfigure(6, weight=2)
        frame.grid_columnconfigure(7, weight=2)

    def _populate_list_row(self, row: ctk.CTkFrame, device: NetworkDevice):
        if self._is_target_device(device):
            selected_var = ctk.BooleanVar(value=(device.ip in self.selected_device_ips))
            select_cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=selected_var,
                width=16,
                checkbox_width=16,
                checkbox_height=16,
                command=lambda ip=device.ip, var=selected_var: self._set_device_selected(ip, bool(var.get()))
            )
            select_cb.grid(row=0, column=0, sticky="w", padx=8, pady=8)
        else:
            protected = ctk.CTkLabel(
                row,
                text="-",
                font=FONTS["small"],
                text_color=COLORS["text_muted"]
            )
            protected.grid(row=0, column=0, sticky="w", padx=8, pady=8)

        values = [
            self._device_display_name(device),
            device.ip,
            device.mac.upper(),
            self._device_type_label(device),
        ]
        colors = [
            COLORS["text_primary"],
            COLORS["text_secondary"],
            COLORS["text_muted"],
            COLORS["text_secondary"],
        ]
        fonts = [FONTS["small"], FONTS["mono_small"], FONTS["mono_small"], FONTS["small"]]

        for idx, value in enumerate(values, start=1):
            label = ctk.CTkLabel(
                row,
                text=value,
                font=fonts[idx - 1],
                text_color=colors[idx - 1],
                anchor="w"
            )
            label.grid(row=0, column=idx, sticky="w", padx=8, pady=8)

        lag_frame = ctk.CTkFrame(row, fg_color="transparent")
        lag_frame.grid(row=0, column=5, sticky="ew", padx=8, pady=6)
        if self._is_target_device(device):
            lag_var = ctk.IntVar(value=self._get_lag_percent(device.ip))
            lag_slider = ctk.CTkSlider(
                lag_frame,
                from_=0,
                to=100,
                number_of_steps=100,
                width=90,
                button_color=COLORS["accent_danger"],
                progress_color=COLORS["accent_danger"],
                button_hover_color=COLORS["accent_danger_hover"],
                command=lambda value, ip=device.ip, var=lag_var, label_ref=None: None
            )
            lag_value = ctk.CTkLabel(
                lag_frame,
                text=f"{lag_var.get()}%",
                font=FONTS["tiny"],
                text_color=COLORS["text_secondary"],
                width=30
            )

            def on_lag_change(value, ip=device.ip, var=lag_var, label_ref=lag_value):
                lag_percent = max(0, min(100, int(round(float(value)))))
                var.set(lag_percent)
                label_ref.configure(text=f"{lag_percent}%")
                self._set_lag_percent(ip, lag_percent)

            lag_slider.configure(command=on_lag_change)
            lag_slider.set(lag_var.get())
            lag_slider.pack(side="left", padx=(0, 4))
            lag_value.pack(side="left")
        else:
            lag_na = ctk.CTkLabel(
                lag_frame,
                text="-",
                font=FONTS["small"],
                text_color=COLORS["text_muted"]
            )
            lag_na.pack(anchor="w")

        status_label = ctk.CTkLabel(
            row,
            text=self._device_status_label(device),
            font=FONTS["small"],
            text_color=self._status_color(device),
            anchor="w"
        )
        status_label.grid(row=0, column=6, sticky="w", padx=8, pady=8)

        action_frame = ctk.CTkFrame(row, fg_color="transparent")
        action_frame.grid(row=0, column=7, sticky="e", padx=8, pady=6)
        self._create_action_widget(action_frame, device)

    def _create_action_widget(self, parent: ctk.CTkFrame, device: NetworkDevice):
        if device.is_self or device.is_gateway:
            label = ctk.CTkLabel(
                parent,
                text="Protected",
                font=FONTS["tiny"],
                text_color=COLORS["text_muted"]
            )
            label.pack()
            return

        if device.is_throttled:
            button = ctk.CTkButton(
                parent,
                text="Restore",
                font=FONTS["tiny"],
                fg_color=COLORS["accent_success"],
                hover_color=COLORS["accent_success_hover"],
                text_color="white",
                corner_radius=8,
                width=86,
                height=28,
                command=lambda: self._restore_device(device.ip)
            )
        else:
            button = ctk.CTkButton(
                parent,
                text="Lag",
                font=FONTS["tiny"],
                fg_color=COLORS["accent_danger"],
                hover_color=COLORS["accent_danger_hover"],
                text_color="white",
                corner_radius=8,
                width=86,
                height=28,
                command=lambda: self._throttle_device(
                    device.ip,
                    self._lag_percent_to_level(self._get_lag_percent(device.ip))
                )
            )
        button.pack()

    def _device_display_name(self, device: NetworkDevice) -> str:
        if device.is_self:
            return f"{device.hostname} (You)"
        if device.is_gateway:
            return f"{device.hostname} (Gateway)"
        return device.hostname

    def _device_type_label(self, device: NetworkDevice) -> str:
        if device.is_self:
            return "Self"
        if device.is_gateway:
            return "Gateway"
        return "Target"

    def _device_status_label(self, device: NetworkDevice) -> str:
        return "Throttled" if device.is_throttled else "Normal"

    def _status_color(self, device: NetworkDevice) -> str:
        return COLORS["accent_danger"] if device.is_throttled else COLORS["accent_success"]

    def _get_row_color(self, device: NetworkDevice) -> str:
        if device.is_self:
            return COLORS["self_bg"]
        if device.is_gateway:
            return COLORS["gateway_bg"]
        if device.is_throttled:
            return COLORS["throttled_bg"]
        return COLORS["bg_card"]

    def _throttle_device(self, ip: str, level: int):
        """Throttle a device."""
        device = self.engine.devices.get(ip)
        if device:
            level = max(0, min(100, int(level)))
            lag_percent = 100 - level
            if lag_percent <= 0:
                messagebox.showinfo(
                    "Lag Speed 0%",
                    "Lag speed untuk device ini masih 0%.\n\nNaikkan Lag % di samping device."
                )
                return

            confirm = messagebox.askyesno(
                "Confirm Throttle",
                f"Lag device {device.hostname} ({ip})?\n\n"
                f"Lag speed: {lag_percent}%.\n"
                f"This will slow down or block their internet connection."
            )
            if confirm:
                threading.Thread(
                    target=self.engine.throttle_device,
                    args=(ip, level),
                    daemon=True
                ).start()

    def _restore_device(self, ip: str):
        """Restore a device to normal."""
        threading.Thread(
            target=self.engine.restore_device,
            args=(ip,),
            daemon=True
        ).start()

    def _restore_all(self):
        """Restore all throttled devices."""
        throttled = [d for d in self.engine.devices.values() if d.is_throttled]
        if not throttled:
            messagebox.showinfo("Info", "No devices are currently throttled.")
            return

        confirm = messagebox.askyesno(
            "Confirm Restore All",
            f"Restore all {len(throttled)} throttled devices to normal?"
        )
        if confirm:
            threading.Thread(
                target=self.engine.restore_all,
                daemon=True
            ).start()

    def _on_close(self):
        """Handle window close - cleanup all spoofing."""
        self._update_status("Cleaning up... Restoring all devices...")
        self.update()

        def _cleanup():
            self.engine.cleanup()
            self.engine.disable_ip_forwarding()
            self.after(0, self.destroy)

        threading.Thread(target=_cleanup, daemon=True).start()

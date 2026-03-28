"""
Zee-Cut - Modern GUI Application
Advanced WiFi Network Device Controller.
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
import sys
import os
import webbrowser

from core.network import NetworkEngine, NetworkDevice

# ─── Theme Configuration ───────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Theme palettes
THEMES = {
    "amoled": {
        "bg_dark": "#000000",
        "bg_card": "#050505",
        "bg_card_hover": "#111111",
        "bg_input": "#0f0f10",
        "accent_primary": "#3b82f6",
        "accent_primary_hover": "#60a5fa",
        "accent_danger": "#ef4444",
        "accent_danger_hover": "#f87171",
        "accent_success": "#10b981",
        "accent_success_hover": "#34d399",
        "accent_warning": "#f59e0b",
        "accent_warning_hover": "#fbbf24",
        "text_primary": "#f8fafc",
        "text_secondary": "#cbd5e1",
        "text_muted": "#94a3b8",
        "border": "#171717",
        "border_light": "#262626",
        "gradient_start": "#3b82f6",
        "gradient_end": "#0ea5e9",
        "throttled_bg": "#1a0909",
        "normal_bg": "#050505",
        "self_bg": "#071223",
        "gateway_bg": "#07190f",
    },
    "google": {
        "bg_dark": "#202124",
        "bg_card": "#2d2f31",
        "bg_card_hover": "#383b3d",
        "bg_input": "#3c4043",
        "accent_primary": "#8ab4f8",
        "accent_primary_hover": "#a8c7fa",
        "accent_danger": "#f28b82",
        "accent_danger_hover": "#f6aea9",
        "accent_success": "#81c995",
        "accent_success_hover": "#9fd8ad",
        "accent_warning": "#fdd663",
        "accent_warning_hover": "#fde293",
        "text_primary": "#e8eaed",
        "text_secondary": "#c7c9cc",
        "text_muted": "#9aa0a6",
        "border": "#444746",
        "border_light": "#5f6368",
        "gradient_start": "#8ab4f8",
        "gradient_end": "#81c995",
        "throttled_bg": "#3a1f1f",
        "normal_bg": "#2d2f31",
        "self_bg": "#1f2f44",
        "gateway_bg": "#1f3728",
    },
}

COLORS = THEMES["amoled"].copy()

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


class WiFiThrottlerApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.engine = NetworkEngine()
        self.engine.on_devices_updated = self._on_devices_updated
        self.engine.on_status_changed = self._on_status_changed
        self.theme_options = {
            "AMOLED Black": "amoled",
            "Google Dark": "google",
        }
        self.theme_var = ctk.StringVar(value="AMOLED Black")
        self.filter_mode_var = ctk.StringVar(value="All Devices")
        self.selected_device_ips: set[str] = set()
        self.device_lag_percents: dict[str, int] = {}
        self.list_column_minsize = {
            0: 64,   # Sel
            1: 280,  # Device
            2: 170,  # IP
            3: 240,  # MAC
            4: 120,  # Type
            5: 220,  # Lag %
            6: 140,  # Status
            7: 132,  # Action
        }
        self.list_label_widths = {
            0: 28,
            1: 250,
            2: 140,
            3: 210,
            4: 90,
            5: 190,
            6: 110,
            7: 100,
        }
        self._is_admin = False
        self._apply_theme(self.theme_options[self.theme_var.get()])

        self._setup_window()
        self._create_layout()
        self._check_admin()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self):
        self.title("Zee-Cut | Network Control Center")
        self.geometry("1180x780")
        self.minsize(980, 640)
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
        self.header_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=86)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)
        self.header_frame.grid_columnconfigure(1, weight=1)

        title_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=24, pady=16, sticky="w")

        self.app_icon_label = ctk.CTkLabel(
            title_frame,
            text="\U0001F4F6",
            font=("Segoe UI Emoji", 34),
            text_color=COLORS["text_primary"],
            width=44
        )
        self.app_icon_label.pack(side="left", padx=(0, 12))

        title_text = ctk.CTkFrame(title_frame, fg_color="transparent")
        title_text.pack(side="left")

        self.title_label = ctk.CTkLabel(
            title_text,
            text="Zee-Cut",
            font=FONTS["title"],
            text_color=COLORS["text_primary"]
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ctk.CTkLabel(
            title_text,
            text="Network Control Center",
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        self.subtitle_label.pack(anchor="w")

        self.credit_label = ctk.CTkLabel(
            title_text,
            text="by Muhammad Ibnu Fauzi",
            font=FONTS["tiny"],
            text_color=COLORS["text_muted"]
        )
        self.credit_label.pack(anchor="w", pady=(1, 0))

        header_actions = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        header_actions.grid(row=0, column=1, padx=24, pady=16, sticky="e")

        self.github_btn = ctk.CTkButton(
            header_actions,
            text="\U0001F419 GitHub",
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            width=118,
            height=34,
            command=self._open_github_repo
        )
        self.github_btn.pack(side="left", padx=(0, 10))

        self.admin_badge = ctk.CTkLabel(
            header_actions,
            text="",
            font=FONTS["tiny"],
            corner_radius=6,
        )
        self.admin_badge.pack(side="left")
    # Toolbar

    def _create_toolbar(self):
        self.toolbar_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=60)
        self.toolbar_frame.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        self.toolbar_frame.grid_propagate(False)
        self.toolbar_frame.grid_columnconfigure(1, weight=1)

        left_toolbar = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
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
        right_toolbar = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        right_toolbar.grid(row=0, column=1, padx=16, pady=10, sticky="e")

        theme_label = ctk.CTkLabel(
            right_toolbar,
            text="Theme:",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        theme_label.pack(side="left", padx=(0, 6))

        self.theme_dropdown = ctk.CTkOptionMenu(
            right_toolbar,
            variable=self.theme_var,
            values=list(self.theme_options.keys()),
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_primary"],
            button_hover_color=COLORS["accent_primary_hover"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["bg_card_hover"],
            corner_radius=8,
            width=130,
            command=self._on_theme_changed
        )
        self.theme_dropdown.pack(side="left", padx=(0, 10))

        # Scan button
        self.scan_btn = ctk.CTkButton(
            right_toolbar,
            text="Scan Network",
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
            text="Restore All",
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
            text="Connected Devices (0)",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.device_header.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.batch_controls_frame = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.batch_controls_frame.grid(row=0, column=1, sticky="e", pady=(0, 12))

        self.check_all_btn = ctk.CTkButton(
            self.batch_controls_frame,
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
            self.batch_controls_frame,
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
            self.batch_controls_frame,
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
            self.batch_controls_frame,
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
        self.statusbar_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=32)
        self.statusbar_frame.grid(row=3, column=0, sticky="ew")
        self.statusbar_frame.grid_propagate(False)
        self.statusbar_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.statusbar_frame,
            text="Ready - Select an interface to begin",
            font=FONTS["tiny"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=4, sticky="w")

        self.throttle_count_label = ctk.CTkLabel(
            self.statusbar_frame,
            text="Throttled: 0",
            font=FONTS["tiny"],
            text_color=COLORS["accent_warning"],
            anchor="e"
        )
        self.throttle_count_label.grid(row=0, column=1, padx=16, pady=4, sticky="e")

    # ─── Logic ──────────────────────────────────────────────────────────

    def _check_admin(self):
        self._is_admin = self.engine.is_admin()
        self._apply_admin_badge_style()
        if self._is_admin:
            self._load_interfaces()
            self.engine.enable_ip_forwarding()
        else:
            self._show_admin_warning()
            self._load_interfaces()

    def _apply_admin_badge_style(self):
        if not hasattr(self, "admin_badge"):
            return
        if self._is_admin:
            self.admin_badge.configure(
                text="Administrator",
                text_color=COLORS["accent_success"],
                fg_color=COLORS["gateway_bg"]
            )
        else:
            self.admin_badge.configure(
                text="Not Admin",
                text_color=COLORS["accent_warning"],
                fg_color=COLORS["throttled_bg"]
            )

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

    def _on_filter_mode_changed(self, _choice: str):
        self._refresh_device_list()

    def _on_theme_changed(self, choice: str):
        theme_key = self.theme_options.get(choice, "amoled")
        self._apply_theme(theme_key, refresh=True)

    def _open_github_repo(self):
        webbrowser.open_new_tab("https://github.com/ifauzeee/Zee-Cut")

    def _apply_theme(self, theme_key: str, refresh: bool = False):
        COLORS.clear()
        COLORS.update(THEMES.get(theme_key, THEMES["amoled"]))

        self.configure(fg_color=COLORS["bg_dark"])

        if hasattr(self, "header_frame"):
            self.header_frame.configure(fg_color=COLORS["bg_card"])
        if hasattr(self, "toolbar_frame"):
            self.toolbar_frame.configure(fg_color=COLORS["bg_card"])
        if hasattr(self, "statusbar_frame"):
            self.statusbar_frame.configure(fg_color=COLORS["bg_card"])
        if hasattr(self, "batch_controls_frame"):
            self.batch_controls_frame.configure(
                fg_color=COLORS["bg_card"],
                border_color=COLORS["border"]
            )

        if hasattr(self, "title_label"):
            self.title_label.configure(text_color=COLORS["text_primary"])
        if hasattr(self, "subtitle_label"):
            self.subtitle_label.configure(text_color=COLORS["text_muted"])
        if hasattr(self, "credit_label"):
            self.credit_label.configure(text_color=COLORS["text_muted"])
        if hasattr(self, "app_icon_label"):
            self.app_icon_label.configure(text_color=COLORS["accent_primary"])
        if hasattr(self, "github_btn"):
            self.github_btn.configure(
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"]
            )

        option_menus = [
            "iface_dropdown",
            "filter_mode_dropdown",
            "theme_dropdown",
        ]
        for name in option_menus:
            if hasattr(self, name):
                getattr(self, name).configure(
                    fg_color=COLORS["bg_input"],
                    button_color=COLORS["accent_primary"],
                    button_hover_color=COLORS["accent_primary_hover"],
                    dropdown_fg_color=COLORS["bg_card"],
                    dropdown_hover_color=COLORS["bg_card_hover"],
                )

        if hasattr(self, "scan_btn"):
            self.scan_btn.configure(
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_primary_hover"]
            )
        if hasattr(self, "restore_all_btn"):
            self.restore_all_btn.configure(
                fg_color=COLORS["accent_success"],
                hover_color=COLORS["accent_success_hover"]
            )
        if hasattr(self, "check_all_btn"):
            self.check_all_btn.configure(
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"]
            )
        if hasattr(self, "clear_selection_btn"):
            self.clear_selection_btn.configure(
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"]
            )
        if hasattr(self, "lag_selected_btn"):
            self.lag_selected_btn.configure(
                fg_color=COLORS["accent_danger"],
                hover_color=COLORS["accent_danger_hover"]
            )
        if hasattr(self, "restore_selected_btn"):
            self.restore_selected_btn.configure(
                fg_color=COLORS["accent_success"],
                hover_color=COLORS["accent_success_hover"]
            )

        if hasattr(self, "device_header"):
            self.device_header.configure(text_color=COLORS["text_primary"])
        if hasattr(self, "status_label"):
            self.status_label.configure(text_color=COLORS["text_muted"])
        if hasattr(self, "throttle_count_label"):
            self.throttle_count_label.configure(text_color=COLORS["accent_warning"])
        if hasattr(self, "device_scroll"):
            self.device_scroll.configure(
                scrollbar_button_color=COLORS["border_light"],
                scrollbar_button_hover_color=COLORS["accent_primary"]
            )
        if hasattr(self, "admin_badge"):
            self._apply_admin_badge_style()

        if refresh and hasattr(self, "device_scroll"):
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
        self.after(0, lambda: self.scan_btn.configure(state="normal", text="Scan Network"))

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
            self._render_list_view(filtered_devices)

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
                anchor="w",
                width=self.list_label_widths.get(idx, 100)
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

    def _configure_list_columns(self, frame: ctk.CTkFrame):
        for col, minsize in self.list_column_minsize.items():
            weight = 1 if col in (1, 5) else 0
            frame.grid_columnconfigure(col, weight=weight, minsize=minsize)

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
                text_color=COLORS["text_muted"],
                width=self.list_label_widths.get(0, 28)
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
                anchor="w",
                width=self.list_label_widths.get(idx, 100)
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

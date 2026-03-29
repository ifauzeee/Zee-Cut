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
import webbrowser

from core.admin import is_admin
from core.models import NetworkDevice
from core.network import NetworkEngine
from ui.theme import THEMES, COLORS, FONTS

# ─── Theme Configuration ───────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
        self.device_lag_percents: dict[str, int] = {}
        self.selected_target_ips: set[str] = set()
        self.bulk_lag_percent = 100
        self.pending_lag_apply_jobs: dict[str, str] = {}
        self.lag_apply_delay_ms = 280
        self.last_lag_interaction_ts = 0.0
        self.scan_in_progress = False
        self.list_column_minsize = {
            0: 70,   # Sel
            1: 290,  # Device
            2: 170,  # IP
            3: 240,  # MAC
            4: 120,  # Type
            5: 230,  # Lag %
            6: 150,  # Status
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

        self.flush_arp_btn = ctk.CTkButton(
            right_toolbar,
            text="Flush ARP (Admin)",
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            width=140,
            height=38,
            command=self._flush_arp_admin
        )
        self.flush_arp_btn.pack(side="left", padx=(0, 8))

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
        self.scan_btn.pack(side="left")

    # ─── Device List ────────────────────────────────────────────────────

    def _create_device_list(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        container.grid_rowconfigure(2, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Device count header
        self.device_header = ctk.CTkLabel(
            container,
            text="Connected Devices (0)",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.device_header.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.selection_controls = ctk.CTkFrame(
            container,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"]
        )
        self.selection_controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.selection_controls.grid_columnconfigure(0, weight=1)

        selection_left = ctk.CTkFrame(self.selection_controls, fg_color="transparent")
        selection_left.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.check_all_btn = ctk.CTkButton(
            selection_left,
            text="Check All",
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            width=90,
            height=30,
            command=self._check_all_targets
        )
        self.check_all_btn.pack(side="left", padx=(0, 8))

        self.clear_select_btn = ctk.CTkButton(
            selection_left,
            text="Clear",
            font=FONTS["small"],
            fg_color=COLORS["bg_input"],
            hover_color=COLORS["bg_card_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            width=82,
            height=30,
            command=self._clear_selected_targets
        )
        self.clear_select_btn.pack(side="left", padx=(0, 10))

        self.selected_count_label = ctk.CTkLabel(
            selection_left,
            text="Selected: 0",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        self.selected_count_label.pack(side="left")

        self.bulk_speed_frame = ctk.CTkFrame(self.selection_controls, fg_color="transparent")
        self.bulk_speed_frame.grid(row=0, column=1, padx=10, pady=8, sticky="e")

        self.bulk_speed_label = ctk.CTkLabel(
            self.bulk_speed_frame,
            text="Selected Lag",
            font=FONTS["small"],
            text_color=COLORS["text_secondary"]
        )
        self.bulk_speed_label.pack(side="left", padx=(0, 8))

        self.bulk_speed_slider = ctk.CTkSlider(
            self.bulk_speed_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            width=160,
            button_color=COLORS["accent_danger"],
            progress_color=COLORS["accent_danger"],
            button_hover_color=COLORS["accent_danger_hover"],
            command=self._on_bulk_speed_change
        )
        self.bulk_speed_slider.set(self.bulk_lag_percent)
        self.bulk_speed_slider.pack(side="left", padx=(0, 6))

        self.bulk_speed_value_label = ctk.CTkLabel(
            self.bulk_speed_frame,
            text=f"{self.bulk_lag_percent}%",
            font=FONTS["tiny"],
            text_color=COLORS["text_secondary"],
            width=36
        )
        self.bulk_speed_value_label.pack(side="left", padx=(0, 8))

        self.apply_selected_btn = ctk.CTkButton(
            self.bulk_speed_frame,
            text="Apply Selected",
            font=FONTS["small"],
            fg_color=COLORS["accent_danger"],
            hover_color=COLORS["accent_danger_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=8,
            width=120,
            height=30,
            command=self._apply_bulk_speed_to_selected
        )
        self.apply_selected_btn.pack(side="left")

        self.bulk_speed_frame.grid_remove()

        # Scrollable device list
        self.device_scroll = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border_light"],
            scrollbar_button_hover_color=COLORS["accent_primary"]
        )
        self.device_scroll.grid(row=2, column=0, sticky="nsew")
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
        self._is_admin = is_admin()
        self._apply_admin_badge_style()
        self._apply_admin_permissions()
        if not self._is_admin:
            self._show_admin_warning()
        self._load_interfaces()

    def _apply_admin_permissions(self):
        if hasattr(self, "flush_arp_btn"):
            self.flush_arp_btn.configure(state="normal" if self._is_admin else "disabled")
        if hasattr(self, "scan_btn"):
            self.scan_btn.configure(
                state="normal" if self._is_admin else "disabled",
                text="Scan Network" if self._is_admin else "Scan Network (Admin)"
            )
        if hasattr(self, "status_label") and not self._is_admin:
            self.status_label.configure(
                text="Limited mode: run as Administrator to scan/throttle devices."
            )

    def _require_admin(self, warn: bool = True) -> bool:
        if self._is_admin:
            return True
        if warn:
            self._show_admin_warning()
        return False

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
        if hasattr(self, "flush_arp_btn"):
            self.flush_arp_btn.configure(
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"]
            )
        if hasattr(self, "selection_controls"):
            self.selection_controls.configure(
                fg_color=COLORS["bg_card"],
                border_color=COLORS["border"]
            )
        if hasattr(self, "check_all_btn"):
            self.check_all_btn.configure(
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"]
            )
        if hasattr(self, "clear_select_btn"):
            self.clear_select_btn.configure(
                fg_color=COLORS["bg_input"],
                hover_color=COLORS["bg_card_hover"],
                text_color=COLORS["text_primary"]
            )
        if hasattr(self, "selected_count_label"):
            self.selected_count_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "bulk_speed_label"):
            self.bulk_speed_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "bulk_speed_value_label"):
            self.bulk_speed_value_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "bulk_speed_slider"):
            self.bulk_speed_slider.configure(
                button_color=COLORS["accent_danger"],
                progress_color=COLORS["accent_danger"],
                button_hover_color=COLORS["accent_danger_hover"]
            )
        if hasattr(self, "apply_selected_btn"):
            self.apply_selected_btn.configure(
                fg_color=COLORS["accent_danger"],
                hover_color=COLORS["accent_danger_hover"],
                text_color=COLORS["text_primary"]
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
        if ip in self.device_lag_percents:
            return max(0, min(100, int(self.device_lag_percents[ip])))
        device = self.engine.get_device_snapshot(ip)
        if device and device.is_throttled:
            return 100
        return 0

    def _set_lag_percent(self, ip: str, lag_percent: int):
        self.device_lag_percents[ip] = max(0, min(100, int(lag_percent)))

    def _sync_device_control_state(self, devices: list[NetworkDevice]):
        device_map = {device.ip: device for device in devices}
        target_ips = {d.ip for d in devices if self._is_target_device(d)}
        self.device_lag_percents = {
            ip: percent for ip, percent in self.device_lag_percents.items()
            if ip in target_ips
        }
        self.selected_target_ips = {
            ip for ip in self.selected_target_ips
            if ip in target_ips
        }
        for ip, after_id in list(self.pending_lag_apply_jobs.items()):
            if ip not in target_ips:
                self.after_cancel(after_id)
                self.pending_lag_apply_jobs.pop(ip, None)
        for ip in target_ips:
            is_throttled = device_map[ip].is_throttled
            self.device_lag_percents.setdefault(ip, 100 if is_throttled else 0)
        self._update_selection_controls(target_ips)

    def _update_selection_controls(self, target_ips: set[str]):
        if not hasattr(self, "selected_count_label"):
            return

        selected_count = len(self.selected_target_ips)
        target_count = len(target_ips)
        self.selected_count_label.configure(text=f"Selected: {selected_count}/{target_count}")

        controls_enabled = self._is_admin
        has_targets = target_count > 0 and controls_enabled
        self.check_all_btn.configure(state="normal" if has_targets else "disabled")
        self.clear_select_btn.configure(state="normal" if selected_count > 0 and controls_enabled else "disabled")
        self.apply_selected_btn.configure(state="normal" if selected_count > 0 and controls_enabled else "disabled")
        self.bulk_speed_slider.configure(state="normal" if selected_count > 0 and controls_enabled else "disabled")

        if selected_count > 0 and controls_enabled:
            self.bulk_speed_frame.grid(row=0, column=1, padx=10, pady=8, sticky="e")
        else:
            self.bulk_speed_frame.grid_remove()

    def _on_row_select_change(self, ip: str, value: int):
        if not self._require_admin(warn=False):
            return
        if value:
            self.selected_target_ips.add(ip)
        else:
            self.selected_target_ips.discard(ip)
        self._refresh_device_list()

    def _check_all_targets(self):
        if not self._require_admin():
            return
        target_ips = {
            d.ip for d in self.engine.get_devices_snapshot()
            if self._is_target_device(d)
        }
        self.selected_target_ips = set(target_ips)
        self._refresh_device_list()

    def _clear_selected_targets(self):
        self.selected_target_ips.clear()
        self._refresh_device_list()

    def _on_bulk_speed_change(self, value):
        self.bulk_lag_percent = max(0, min(100, int(round(float(value)))))
        if hasattr(self, "bulk_speed_value_label"):
            self.bulk_speed_value_label.configure(text=f"{self.bulk_lag_percent}%")

    def _apply_bulk_speed_to_selected(self):
        if not self._require_admin():
            return
        if not self.selected_target_ips:
            return

        self._mark_lag_interaction()
        selected_ips = list(self.selected_target_ips)
        for ip in selected_ips:
            device = self.engine.get_device_snapshot(ip)
            if not device or not self._is_target_device(device):
                continue
            self._set_lag_percent(ip, self.bulk_lag_percent)
            self._schedule_lag_apply(ip)

        self._refresh_device_list()

    def _schedule_lag_apply(self, ip: str):
        previous_job = self.pending_lag_apply_jobs.pop(ip, None)
        if previous_job:
            self.after_cancel(previous_job)
        self.pending_lag_apply_jobs[ip] = self.after(
            self.lag_apply_delay_ms,
            lambda target_ip=ip: self._apply_lag_change(target_ip)
        )

    def _mark_lag_interaction(self):
        self.last_lag_interaction_ts = time.time()

    def _apply_lag_change(self, ip: str):
        if not self._require_admin(warn=False):
            return
        self.pending_lag_apply_jobs.pop(ip, None)
        device = self.engine.get_device_snapshot(ip)
        if not device or not self._is_target_device(device):
            return

        lag_percent = self._get_lag_percent(ip)
        if lag_percent <= 0:
            threading.Thread(
                target=self.engine.restore_device,
                args=(ip,),
                daemon=True
            ).start()
            return

        level = self._lag_percent_to_level(lag_percent)
        threading.Thread(
            target=self.engine.throttle_device,
            args=(ip, level),
            daemon=True
        ).start()

    def _scan_network(self):
        if not self._require_admin():
            return
        if not self.engine.get_interface_snapshot():
            messagebox.showwarning("Warning", "Please select a network interface first.")
            return

        self.scan_in_progress = True
        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.engine.scan_network(callback=self._on_scan_complete)

    def _flush_arp_admin(self):
        if not self._is_admin:
            messagebox.showwarning(
                "Admin Required",
                "Flush ARP membutuhkan hak Administrator.\nJalankan app sebagai Administrator."
            )
            return

        self.flush_arp_btn.configure(state="disabled", text="Flushing...")

        def _run_flush():
            success, message = self.engine.flush_arp_cache()

            def _done():
                self.flush_arp_btn.configure(state="normal", text="Flush ARP (Admin)")
                if success:
                    messagebox.showinfo("Flush ARP", message)
                else:
                    messagebox.showwarning("Flush ARP", message)

            self.after(0, _done)

        threading.Thread(target=_run_flush, daemon=True).start()

    def _on_scan_complete(self):
        def _done():
            self.scan_in_progress = False
            self.scan_btn.configure(state="normal", text="Scan Network")
            self._refresh_device_list()
        self.after(0, _done)

    def _on_devices_updated(self):
        self.after(0, self._handle_devices_updated_ui)

    def _handle_devices_updated_ui(self):
        if self.scan_in_progress:
            self._refresh_device_list()

    def _on_status_changed(self, message: str):
        self.after(0, lambda: self._update_status(message))

    def _update_status(self, message: str):
        self.status_label.configure(text=message)

        throttled = self.engine.get_throttled_count()
        self.throttle_count_label.configure(text=f"Throttled: {throttled}")

    def _refresh_device_list(self):
        if not hasattr(self, "device_scroll"):
            return

        for widget in self.device_scroll.winfo_children():
            widget.destroy()

        all_devices = sorted(
            self.engine.get_devices_snapshot(),
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

        for idx, title in enumerate(["Sel", "Device", "IP", "MAC", "Type", "Lag %", "Status"]):
            label = ctk.CTkLabel(
                header,
                text=title,
                font=FONTS["small"],
                text_color=COLORS["text_secondary"],
                anchor="center"
            )
            label.grid(row=0, column=idx, sticky="nsew", padx=8, pady=8)

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
            weight = 1
            frame.grid_columnconfigure(col, weight=weight, minsize=minsize)

    def _populate_list_row(self, row: ctk.CTkFrame, device: NetworkDevice):
        if self._is_target_device(device):
            selected_var = ctk.IntVar(value=1 if device.ip in self.selected_target_ips else 0)
            select_box = ctk.CTkCheckBox(
                row,
                text="",
                width=18,
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=4,
                border_width=2,
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_primary_hover"],
                border_color=COLORS["border_light"],
                checkmark_color=COLORS["text_primary"],
                state="normal" if self._is_admin else "disabled",
                variable=selected_var,
                command=lambda ip=device.ip, var=selected_var: self._on_row_select_change(ip, var.get())
            )
            select_box.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        else:
            select_na = ctk.CTkLabel(
                row,
                text="-",
                font=FONTS["small"],
                text_color=COLORS["text_muted"],
                anchor="center"
            )
            select_na.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

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

        for idx, value in enumerate(values):
            label = ctk.CTkLabel(
                row,
                text=value,
                font=fonts[idx],
                text_color=colors[idx],
                anchor="center"
            )
            label.grid(row=0, column=idx + 1, sticky="nsew", padx=8, pady=8)

        lag_frame = ctk.CTkFrame(row, fg_color="transparent")
        lag_frame.grid(row=0, column=5, sticky="nsew", padx=8, pady=6)
        lag_frame.grid_columnconfigure(0, weight=1)
        lag_frame.grid_columnconfigure(1, weight=1)
        if self._is_target_device(device):
            lag_var = ctk.IntVar(value=self._get_lag_percent(device.ip))
            lag_slider = ctk.CTkSlider(
                lag_frame,
                from_=0,
                to=100,
                number_of_steps=100,
                width=90,
                state="normal" if self._is_admin else "disabled",
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
                self._mark_lag_interaction()
                var.set(lag_percent)
                label_ref.configure(text=f"{lag_percent}%")
                self._set_lag_percent(ip, lag_percent)
                self._schedule_lag_apply(ip)

            lag_slider.configure(command=on_lag_change)
            lag_slider.set(lag_var.get())
            lag_slider.grid(row=0, column=0, sticky="e", padx=(0, 6))
            lag_value.grid(row=0, column=1, sticky="w")
        else:
            lag_na = ctk.CTkLabel(
                lag_frame,
                text="-",
                font=FONTS["small"],
                text_color=COLORS["text_muted"],
                anchor="center"
            )
            lag_na.grid(row=0, column=0, columnspan=2, sticky="nsew")

        status_label = ctk.CTkLabel(
            row,
            text=self._device_status_label(device),
            font=FONTS["small"],
            text_color=self._status_color(device),
            anchor="center"
        )
        status_label.grid(row=0, column=6, sticky="nsew", padx=8, pady=8)

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

    def _on_close(self):
        """Handle window close - cleanup all spoofing."""
        for after_id in self.pending_lag_apply_jobs.values():
            self.after_cancel(after_id)
        self.pending_lag_apply_jobs.clear()

        self._update_status("Cleaning up... Restoring all devices...")
        self.update()

        def _cleanup():
            self.engine.cleanup()
            self.engine.disable_ip_forwarding()
            self.after(0, self.destroy)

        threading.Thread(target=_cleanup, daemon=True).start()


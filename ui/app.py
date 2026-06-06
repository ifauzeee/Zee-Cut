"""
Zee-Cut - Main Application Window
All core logic and callbacks, with UI creation delegated to submodules.
"""

import json
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from core.admin import is_admin
from core.bandwidth import BandwidthMonitor
from core.config import ConfigManager
from core.models import NetworkDevice
from core.network import NetworkEngine
from core.oui import download_oui_database
from ui.device_list import (
    create_device_container,
    refresh_bandwidth_labels,
    render_empty_state,
    render_list_view,
)
from ui.dialogs import admin_required_dialog, admin_warning, interface_warning
from ui.header import create_header
from ui.theme import COLORS, FONTS, THEMES
from ui.toolbar import create_toolbar

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class WiFiThrottlerApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.engine = NetworkEngine()
        self.engine.on_devices_updated = self._on_devices_updated
        self.engine.on_status_changed = self._on_status_changed

        self.config_mgr = ConfigManager()
        saved_config = self.config_mgr.load()

        self.theme_options = {"AMOLED Black": "amoled", "Google Dark": "google"}
        saved_theme = saved_config.theme if saved_config.theme in self.theme_options else "AMOLED Black"
        self.theme_var = ctk.StringVar(value=saved_theme)
        self.filter_mode_var = ctk.StringVar(value="All Devices")
        self.custom_protected_ips: set[str] = set(saved_config.custom_protected_ips)
        self.lag_presets: dict[str, int] = {
            "Normal (0%)": 0, "Gaming (35%)": 35, "Meeting (60%)": 60, "Block (100%)": 100,
        }
        self.lag_preset_var = ctk.StringVar(value="Meeting (60%)")
        self.device_lag_percents: dict[str, int] = dict(saved_config.device_lag_percents)
        self.selected_target_ips: set[str] = set()
        self.bulk_lag_percent = 100
        self.pending_lag_apply_jobs: dict[str, str] = {}
        self.lag_apply_delay_ms = 280
        self.last_lag_interaction_ts = 0.0
        self.scan_in_progress = False
        self._refresh_pending = False
        self._last_refresh_time = 0.0
        self._refresh_debounce_ms = 850
        self._saved_interface_name = saved_config.interface_name
        self._saved_interface_ip = saved_config.interface_ip
        self._known_device_ips: set[str] = set()
        self.list_column_minsize = {
            0: 60, 1: 200, 2: 150, 3: 190, 4: 150, 5: 90, 6: 160, 7: 130, 8: 130,
        }
        self._is_admin = False

        self._bandwidth = BandwidthMonitor()
        self.auto_scan_enabled = ctk.BooleanVar(value=saved_config.auto_scan_enabled)
        self.auto_scan_interval = saved_config.auto_scan_interval_minutes
        self._auto_scan_job: Optional[str] = None
        self._new_device_notification_enabled = ctk.BooleanVar(
            value=saved_config.new_device_notification_enabled
        )

        self._apply_theme(self.theme_options[self.theme_var.get()])
        self._setup_window(saved_config)
        self._create_layout()
        self._check_admin()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── Window / Layout ───────────────────────────────────────────────

    def _setup_window(self, saved_config=None):
        self.title("Zee-Cut | Network Control Center")
        w = saved_config.last_window_width if saved_config else 1180
        h = saved_config.last_window_height if saved_config else 780
        self.geometry(f"{w}x{h}")
        self.minsize(980, 640)
        self.configure(fg_color=COLORS["bg_dark"])
        try:
            base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(base, "assets", "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

    def _create_layout(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        create_header(self)
        create_toolbar(self)
        create_device_container(self)
        self._create_statusbar()

    def _create_statusbar(self):
        self.statusbar_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=0, height=32)
        self.statusbar_frame.grid(row=3, column=0, sticky="ew")
        self.statusbar_frame.grid_propagate(False)
        self.statusbar_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            self.statusbar_frame, text="Ready - Select an interface to begin",
            font=FONTS["tiny"], text_color=COLORS["text_muted"], anchor="w"
        )
        self.status_label.grid(row=0, column=0, padx=16, pady=4, sticky="w")

        self.throttle_count_label = ctk.CTkLabel(
            self.statusbar_frame, text="Throttled: 0",
            font=FONTS["tiny"], text_color=COLORS["accent_warning"], anchor="e"
        )
        self.throttle_count_label.grid(row=0, column=1, padx=16, pady=4, sticky="e")

    # ─── Admin ──────────────────────────────────────────────────────────

    def _check_admin(self):
        self._is_admin = is_admin()
        self._apply_admin_badge_style()
        self._apply_admin_permissions()
        if not self._is_admin:
            admin_warning()
        self._load_interfaces()

    def _apply_admin_permissions(self):
        admin = self._is_admin
        if hasattr(self, "flush_arp_btn"):
            self.flush_arp_btn.configure(state="normal" if admin else "disabled")
        if hasattr(self, "scan_btn"):
            self.scan_btn.configure(
                state="normal" if admin else "disabled",
                text="Scan Network" if admin else "Scan Network (Admin)"
            )
        if hasattr(self, "auto_scan_switch"):
            self.auto_scan_switch.configure(state="normal" if admin else "disabled")
        if hasattr(self, "auto_scan_interval_dropdown"):
            self.auto_scan_interval_dropdown.configure(state="normal" if admin else "disabled")
        if hasattr(self, "status_label") and not admin:
            self.status_label.configure(
                text="Limited mode: run as Administrator to scan/throttle devices."
            )

    def _require_admin(self, warn: bool = True) -> bool:
        if self._is_admin:
            return True
        if warn:
            admin_warning()
        return False

    def _apply_admin_badge_style(self):
        if not hasattr(self, "admin_badge"):
            return
        if self._is_admin:
            self.admin_badge.configure(
                text="Administrator", text_color=COLORS["accent_success"],
                fg_color=COLORS["gateway_bg"]
            )
        else:
            self.admin_badge.configure(
                text="Not Admin", text_color=COLORS["accent_warning"],
                fg_color=COLORS["throttled_bg"]
            )

    # ─── Interface ──────────────────────────────────────────────────────

    def _load_interfaces(self):
        def _load():
            ifaces = self.engine.get_interfaces()
            self._interfaces = {f"{i.display_name} ({i.ip})": i for i in ifaces}
            names = list(self._interfaces.keys()) or ["No interfaces found"]
            self.after(0, lambda: self._update_interface_list(names))

        self._interfaces = {}
        threading.Thread(target=_load, daemon=True).start()

    def _update_interface_list(self, names: list):
        self.iface_dropdown.configure(values=names)
        if names and names[0] != "No interfaces found":
            saved_name, saved_ip = self._saved_interface_name, self._saved_interface_ip
            selected = names[0]
            for name in names:
                if (saved_name and saved_name in name) or (saved_ip and saved_ip in name):
                    selected = name
                    break
            self.iface_var.set(selected)
            self._on_interface_selected(selected)

    def _on_interface_selected(self, choice: str):
        iface = self._interfaces.get(choice)
        if not iface:
            return
        self.engine.set_interface(iface)
        self._bandwidth.stop()
        self._start_bandwidth_monitor()
        self._update_status(f"Interface: {iface.display_name} | IP: {iface.ip} | Gateway: {iface.gateway_ip}")

    # ─── Theme ─────────────────────────────────────────────────────────

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
            self.github_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])

        for name in ["iface_dropdown", "filter_mode_dropdown", "theme_dropdown", "lag_preset_dropdown", "auto_scan_interval_dropdown"]:
            if hasattr(self, name):
                getattr(self, name).configure(
                    fg_color=COLORS["bg_input"], button_color=COLORS["accent_primary"],
                    button_hover_color=COLORS["accent_primary_hover"],
                    dropdown_fg_color=COLORS["bg_card"], dropdown_hover_color=COLORS["bg_card_hover"]
                )

        if hasattr(self, "scan_btn"):
            self.scan_btn.configure(fg_color=COLORS["accent_primary"], hover_color=COLORS["accent_primary_hover"])
        if hasattr(self, "auto_scan_switch"):
            self.auto_scan_switch.configure(button_color=COLORS["accent_primary"], progress_color=COLORS["accent_primary"])
        if hasattr(self, "dl_oui_btn"):
            self.dl_oui_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_muted"])
        if hasattr(self, "flush_arp_btn"):
            self.flush_arp_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "export_diag_btn"):
            self.export_diag_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "selection_controls"):
            self.selection_controls.configure(fg_color=COLORS["bg_card"], border_color=COLORS["border"])
        if hasattr(self, "check_all_btn"):
            self.check_all_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "clear_select_btn"):
            self.clear_select_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "protect_selected_btn"):
            self.protect_selected_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "clear_safe_list_btn"):
            self.clear_safe_list_btn.configure(fg_color=COLORS["bg_input"], hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "selected_count_label"):
            self.selected_count_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "safe_count_label"):
            self.safe_count_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "bulk_speed_label"):
            self.bulk_speed_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "preset_label"):
            self.preset_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "bulk_speed_value_label"):
            self.bulk_speed_value_label.configure(text_color=COLORS["text_secondary"])
        if hasattr(self, "bulk_speed_slider"):
            self.bulk_speed_slider.configure(button_color=COLORS["accent_danger"], progress_color=COLORS["accent_danger"], button_hover_color=COLORS["accent_danger_hover"])
        if hasattr(self, "apply_preset_btn"):
            self.apply_preset_btn.configure(fg_color=COLORS["accent_warning"], hover_color=COLORS["accent_warning_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "apply_selected_btn"):
            self.apply_selected_btn.configure(fg_color=COLORS["accent_danger"], hover_color=COLORS["accent_danger_hover"], text_color=COLORS["text_primary"])
        if hasattr(self, "device_header"):
            self.device_header.configure(text_color=COLORS["text_primary"])
        if hasattr(self, "status_label"):
            self.status_label.configure(text_color=COLORS["text_muted"])
        if hasattr(self, "throttle_count_label"):
            self.throttle_count_label.configure(text_color=COLORS["accent_warning"])
        if hasattr(self, "device_scroll"):
            self.device_scroll.configure(scrollbar_button_color=COLORS["border_light"], scrollbar_button_hover_color=COLORS["accent_primary"])
        if hasattr(self, "admin_badge"):
            self._apply_admin_badge_style()
        if refresh and hasattr(self, "device_scroll"):
            self._refresh_device_list()

    # ─── Device Targeting ──────────────────────────────────────────────

    def _is_target_device(self, device: NetworkDevice) -> bool:
        return not self._is_protected_device(device)

    def _is_custom_protected_ip(self, ip: str) -> bool:
        return ip in self.custom_protected_ips

    def _is_protected_device(self, device: NetworkDevice) -> bool:
        return device.is_self or device.is_gateway or self._is_custom_protected_ip(device.ip)

    def _lag_percent_to_level(self, lag_percent: int) -> int:
        return 100 - max(0, min(100, int(lag_percent)))

    def _get_lag_percent(self, ip: str) -> int:
        if ip in self.device_lag_percents:
            return max(0, min(100, int(self.device_lag_percents[ip])))
        device = self.engine.get_device_snapshot(ip)
        return 100 if (device and device.is_throttled) else 0

    def _set_lag_percent(self, ip: str, lag_percent: int):
        self.device_lag_percents[ip] = max(0, min(100, int(lag_percent)))

    def _sync_device_control_state(self, devices: list[NetworkDevice]):
        device_map = {d.ip: d for d in devices}
        target_ips = {d.ip for d in devices if self._is_target_device(d)}
        self.device_lag_percents = {ip: p for ip, p in self.device_lag_percents.items() if ip in target_ips}
        self.selected_target_ips = {ip for ip in self.selected_target_ips if ip in target_ips}
        for ip, aid in list(self.pending_lag_apply_jobs.items()):
            if ip not in target_ips:
                self.after_cancel(aid)
                self.pending_lag_apply_jobs.pop(ip, None)
        for ip in target_ips:
            is_throttled = device_map[ip].is_throttled
            self.device_lag_percents.setdefault(ip, 100 if is_throttled else 0)
        self._update_selection_controls(target_ips)

    def _update_selection_controls(self, target_ips: set[str]):
        if not hasattr(self, "selected_count_label"):
            return
        all_ips = {d.ip for d in self.engine.get_devices_snapshot()}
        safe_count = len(self.custom_protected_ips.intersection(all_ips))
        selected = len(self.selected_target_ips)
        target = len(target_ips)
        self.selected_count_label.configure(text=f"Selected: {selected}/{target}")
        if hasattr(self, "safe_count_label"):
            self.safe_count_label.configure(text=f"Safe: {safe_count}")

        enabled = self._is_admin
        has_t = target > 0 and enabled
        self.check_all_btn.configure(state="normal" if has_t else "disabled")
        self.clear_select_btn.configure(state="normal" if selected > 0 and enabled else "disabled")
        self.protect_selected_btn.configure(state="normal" if selected > 0 and enabled else "disabled")
        self.clear_safe_list_btn.configure(state="normal" if safe_count > 0 and enabled else "disabled")
        self.apply_selected_btn.configure(state="normal" if selected > 0 and enabled else "disabled")
        self.apply_preset_btn.configure(state="normal" if selected > 0 and enabled else "disabled")
        self.lag_preset_dropdown.configure(state="normal" if enabled else "disabled")
        self.bulk_speed_slider.configure(state="normal" if selected > 0 and enabled else "disabled")
        if selected > 0 and enabled:
            self.bulk_speed_frame.grid(row=0, column=1, padx=10, pady=8, sticky="e")
        else:
            self.bulk_speed_frame.grid_remove()

    def _on_row_select_change(self, ip: str, value: int):
        if not self._require_admin(warn=False):
            return
        (self.selected_target_ips.add if value else self.selected_target_ips.discard)(ip)
        self._refresh_device_list()

    def _check_all_targets(self):
        if not self._require_admin():
            return
        self.selected_target_ips = {d.ip for d in self.engine.get_devices_snapshot() if self._is_target_device(d)}
        self._refresh_device_list()

    def _clear_selected_targets(self):
        self.selected_target_ips.clear()
        self._refresh_device_list()

    def _protect_selected_targets(self):
        if not self._require_admin() or not self.selected_target_ips:
            return
        protected = list(self.selected_target_ips)
        self.custom_protected_ips.update(protected)
        self.selected_target_ips.clear()
        for ip in protected:
            self.device_lag_percents[ip] = 0
            threading.Thread(target=self.engine.restore_device, args=(ip,), daemon=True).start()
        self._update_status(f"Protected {len(protected)} device(s) in safe list")
        self._refresh_device_list()

    def _clear_custom_safe_list(self):
        if not self._require_admin():
            return
        count = len(self.custom_protected_ips)
        self.custom_protected_ips.clear()
        self._update_status(f"Cleared safe list ({count} device(s))")
        self._refresh_device_list()

    # ─── Bulk Lag ───────────────────────────────────────────────────────

    def _on_bulk_speed_change(self, value):
        self.bulk_lag_percent = max(0, min(100, int(round(float(value)))))
        if hasattr(self, "bulk_speed_value_label"):
            self.bulk_speed_value_label.configure(text=f"{self.bulk_lag_percent}%")

    def _apply_bulk_speed_to_selected(self):
        if not self._require_admin() or not self.selected_target_ips:
            return
        self._mark_lag_interaction()
        for ip in list(self.selected_target_ips):
            device = self.engine.get_device_snapshot(ip)
            if device and self._is_target_device(device):
                self._set_lag_percent(ip, self.bulk_lag_percent)
                self._schedule_lag_apply(ip)
        self._refresh_device_list()

    def _apply_preset_to_selected(self):
        if not self._require_admin() or not self.selected_target_ips:
            return
        preset_lag = self.lag_presets.get(self.lag_preset_var.get(), 0)
        self.bulk_lag_percent = preset_lag
        if hasattr(self, "bulk_speed_slider"):
            self.bulk_speed_slider.set(preset_lag)
        if hasattr(self, "bulk_speed_value_label"):
            self.bulk_speed_value_label.configure(text=f"{preset_lag}%")
        self._apply_bulk_speed_to_selected()

    def _schedule_lag_apply(self, ip: str):
        prev = self.pending_lag_apply_jobs.pop(ip, None)
        if prev:
            self.after_cancel(prev)
        self.pending_lag_apply_jobs[ip] = self.after(
            self.lag_apply_delay_ms, lambda ip=ip: self._apply_lag_change(ip)
        )

    def _mark_lag_interaction(self):
        self.last_lag_interaction_ts = time.time()

    def _apply_lag_change(self, ip: str):
        self.pending_lag_apply_jobs.pop(ip, None)
        if not self._require_admin(warn=False):
            return
        device = self.engine.get_device_snapshot(ip)
        if not device or not self._is_target_device(device):
            return
        lag = self._get_lag_percent(ip)
        if lag <= 0:
            threading.Thread(target=self.engine.restore_device, args=(ip,), daemon=True).start()
        else:
            threading.Thread(target=self.engine.throttle_device, args=(ip, self._lag_percent_to_level(lag)), daemon=True).start()

    # ─── Scan ───────────────────────────────────────────────────────────

    def _scan_network(self):
        if not self._require_admin():
            return
        if not self.engine.get_interface_snapshot():
            interface_warning()
            return
        self.scan_in_progress = True
        self.scan_btn.configure(state="disabled", text="Scanning (Realtime)...")
        self.engine.scan_network(callback=self._on_scan_complete, fast_mode=False, flush_before_scan=True)

    def _on_scan_complete(self):
        def _done():
            self.scan_in_progress = False
            self.scan_btn.configure(state="normal", text="Scan Network")
            devices = self.engine.get_devices_snapshot()
            if not self._known_device_ips:
                self._known_device_ips = {d.ip for d in devices if not d.is_self and not d.is_gateway}
            else:
                self._check_new_device_notification(devices)
            self._start_bandwidth_monitor()
            self._refresh_device_list()
        self.after(0, _done)

    def _on_devices_updated(self):
        if not self._refresh_pending:
            self._refresh_pending = True
            self.after(self._refresh_debounce_ms, self._handle_throttled_devices_update)

    def _handle_throttled_devices_update(self):
        self._refresh_pending = False
        now = time.time()
        if now - self._last_refresh_time < (self._refresh_debounce_ms / 1000.0):
            if not self._refresh_pending:
                self._refresh_pending = True
                self.after(200, self._handle_throttled_devices_update)
            return
        self._last_refresh_time = now
        self._refresh_device_list()

    def _on_status_changed(self, message: str):
        self.after(0, lambda: self._update_status(message))

    def _update_status(self, message: str):
        self.status_label.configure(text=message)
        throttled = self.engine.get_throttled_count()
        self.throttle_count_label.configure(text=f"Throttled: {throttled}")

    # ─── Auto Scan ──────────────────────────────────────────────────────

    def _on_auto_scan_toggle(self):
        (self._start_auto_scan if self.auto_scan_enabled.get() else self._stop_auto_scan)()

    def _on_auto_scan_interval_changed(self, choice: str):
        try:
            self.auto_scan_interval = int(choice.split()[0])
        except (ValueError, IndexError):
            self.auto_scan_interval = 3
        if self.auto_scan_enabled.get():
            self._stop_auto_scan()
            self._start_auto_scan()

    def _start_auto_scan(self):
        self._stop_auto_scan()
        ms = self.auto_scan_interval * 60 * 1000
        self._auto_scan_job = self.after(ms, self._auto_scan_tick)
        self._update_status(f"Auto-scan every {self.auto_scan_interval} min enabled")

    def _stop_auto_scan(self):
        if self._auto_scan_job:
            self.after_cancel(self._auto_scan_job)
            self._auto_scan_job = None

    def _auto_scan_tick(self):
        if not self.auto_scan_enabled.get():
            return
        if not self.scan_in_progress:
            self._scan_network()
        ms = self.auto_scan_interval * 60 * 1000
        self._auto_scan_job = self.after(ms, self._auto_scan_tick)

    # ─── Bandwidth Monitor ──────────────────────────────────────────────

    def _start_bandwidth_monitor(self):
        iface = self.engine.get_interface_snapshot()
        if not iface:
            return
        self._bandwidth.set_interface(iface.scapy_iface, iface.mac, ".".join(iface.ip.split(".")[:3]))
        if not self._bandwidth.is_running:
            self._bandwidth.start()
            self._schedule_bw_refresh()

    def _schedule_bw_refresh(self):
        if not self._bandwidth.is_running:
            return
        refresh_bandwidth_labels(self)
        self.after(2000, self._schedule_bw_refresh)

    # ─── New Device Notification ────────────────────────────────────────

    def _check_new_device_notification(self, devices: list[NetworkDevice]):
        current = {d.ip for d in devices if not d.is_self and not d.is_gateway}
        new_ips = current - self._known_device_ips
        if new_ips and self._new_device_notification_enabled.get():
            for ip in new_ips:
                d = next((x for x in devices if x.ip == ip), None)
                if d:
                    name = d.vendor if d.vendor != "Unknown" else d.hostname
                    self._show_notification("New Device Detected", f"{name} ({d.ip}) - {d.mac.upper()}")
        self._known_device_ips = current

    def _show_notification(self, title: str, message: str):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x00000040 | 0x00001000)
        except Exception:
            pass

    # ─── OUI Download ───────────────────────────────────────────────────

    def _download_oui_db(self):
        def _dl():
            self.after(0, lambda: self.dl_oui_btn.configure(state="disabled", text="Downloading..."))
            ok = download_oui_database()
            self.after(0, lambda: self._update_status(
                "OUI database downloaded successfully" if ok else "OUI download failed (check internet)"
            ))
            if ok:
                self.after(0, self._refresh_device_list)
            self.after(0, lambda: self.dl_oui_btn.configure(state="normal", text="DL OUI DB"))
        threading.Thread(target=_dl, daemon=True).start()

    # ─── Utilities ──────────────────────────────────────────────────────

    def _flush_arp_admin(self):
        if not self._is_admin:
            admin_required_dialog()
            return
        self.flush_arp_btn.configure(state="disabled", text="Flushing...")

        def _run():
            ok, msg = self.engine.flush_arp_cache()
            self.after(0, lambda: self.flush_arp_btn.configure(state="normal", text="Flush ARP (Admin)"))
            self.after(0, lambda: messagebox.showinfo("Flush ARP", msg) if ok else messagebox.showwarning("Flush ARP", msg))

        threading.Thread(target=_run, daemon=True).start()

    def _export_diagnostics(self):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = filedialog.asksaveasfilename(
            title="Export Diagnostics", defaultextension=".json",
            initialfile=f"zee-cut-diagnostics-{timestamp}.json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return
        try:
            diag = self.engine.get_diagnostics_snapshot()
            diag["ui"] = {
                "is_admin": self._is_admin, "filter_mode": self.filter_mode_var.get(),
                "selected_count": len(self.selected_target_ips),
                "safe_list_count": len(self.custom_protected_ips),
                "safe_list_ips": sorted(self.custom_protected_ips),
                "selected_lag_percent": self.bulk_lag_percent,
                "selected_preset": self.lag_preset_var.get(),
            }
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(diag, indent=2, ensure_ascii=False), encoding="utf-8")
            self._update_status(f"Diagnostics exported: {p}")
            messagebox.showinfo("Export Diagnostics", f"Saved to:\n{p}")
        except Exception as e:
            messagebox.showerror("Export Diagnostics", f"Failed to export diagnostics:\n{e}")

    def _refresh_device_list(self):
        if not hasattr(self, "device_scroll"):
            return

        for widget in self.device_scroll.winfo_children():
            widget.destroy()

        all_devices = sorted(
            self.engine.get_devices_snapshot(),
            key=lambda d: (not d.is_self, not d.is_gateway, not d.is_throttled, [int(x) for x in d.ip.split('.')])
        )
        self._sync_device_control_state(all_devices)

        if not all_devices:
            self.device_header.configure(text="Connected Devices (0)")
            render_empty_state(self.device_scroll, "No devices found on this network.")
            self.throttle_count_label.configure(text="Throttled: 0")
            return

        mode = self.filter_mode_var.get()
        filtered = self._filter_devices(all_devices, mode)
        self.device_header.configure(text=f"Connected Devices ({len(filtered)}/{len(all_devices)})")

        if not filtered:
            render_empty_state(self.device_scroll, f"No device matches mode '{mode}'.")
        else:
            render_list_view(self, filtered)

        self.throttle_count_label.configure(text=f"Throttled: {sum(1 for d in all_devices if d.is_throttled)}")

    def _filter_devices(self, devices: list[NetworkDevice], mode: str) -> list[NetworkDevice]:
        if mode == "Targets Only":
            return [d for d in devices if self._is_target_device(d)]
        if mode == "Throttled Only":
            return [d for d in devices if d.is_throttled]
        if mode == "Protected Only":
            return [d for d in devices if self._is_protected_device(d)]
        return devices

    # ─── Close / Save ──────────────────────────────────────────────────

    def _on_close(self):
        for aid in self.pending_lag_apply_jobs.values():
            self.after_cancel(aid)
        self.pending_lag_apply_jobs.clear()
        if self._auto_scan_job:
            self.after_cancel(self._auto_scan_job)
            self._auto_scan_job = None
        self._bandwidth.stop()
        self._save_config()
        self._update_status("Cleaning up... Restoring all devices...")
        self.update()

        def _cleanup():
            self.engine.cleanup()
            self.engine.disable_ip_forwarding()
            self.after(0, self.destroy)

        threading.Thread(target=_cleanup, daemon=True).start()

    def _save_config(self):
        try:
            self.config_mgr.update(
                theme=self.theme_var.get(),
                interface_name=self.iface_var.get() if hasattr(self, "iface_var") else "",
                interface_ip=self.engine.get_interface_snapshot().ip if self.engine.get_interface_snapshot() else "",
                custom_protected_ips=sorted(self.custom_protected_ips),
                device_lag_percents=dict(self.device_lag_percents),
                last_window_width=self.winfo_width(),
                last_window_height=self.winfo_height(),
                auto_scan_enabled=self.auto_scan_enabled.get(),
                auto_scan_interval_minutes=self.auto_scan_interval,
                new_device_notification_enabled=self._new_device_notification_enabled.get(),
            )
            self.config_mgr.save()
        except Exception as e:
            print(f"Config save error: {e}")

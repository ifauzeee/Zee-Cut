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
    """Individual device card widget."""

    def __init__(self, master, device: NetworkDevice, on_throttle, on_restore, **kwargs):
        super().__init__(master, **kwargs)
        self.device = device
        self.on_throttle = on_throttle
        self.on_restore = on_restore

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

        # Status icon
        if self.device.is_self:
            icon = "💻"
            status_color = COLORS["accent_primary"]
        elif self.device.is_gateway:
            icon = "🌐"
            status_color = COLORS["accent_success"]
        elif self.device.is_throttled:
            icon = "🔴"
            status_color = COLORS["accent_danger"]
        else:
            icon = "📱"
            status_color = COLORS["text_muted"]

        icon_frame = ctk.CTkFrame(self, fg_color="transparent", width=50)
        icon_frame.grid(row=0, column=0, rowspan=3, padx=(16, 8), pady=12, sticky="ns")
        icon_frame.grid_propagate(False)

        icon_label = ctk.CTkLabel(
            icon_frame, text=icon, font=FONTS["icon_large"],
            text_color=COLORS["text_primary"]
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Status indicator dot
        dot_frame = ctk.CTkFrame(
            icon_frame, width=12, height=12,
            corner_radius=6, fg_color=status_color
        )
        dot_frame.place(relx=0.85, rely=0.2, anchor="center")

        # Device info
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, rowspan=3, padx=4, pady=12, sticky="nsew")

        # Hostname / label
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

        # IP Address
        ip_label = ctk.CTkLabel(
            info_frame, text=f"IP: {self.device.ip}",
            font=FONTS["mono_small"],
            text_color=COLORS["text_secondary"],
            anchor="w"
        )
        ip_label.pack(fill="x", pady=(0, 1))

        # MAC Address
        mac_label = ctk.CTkLabel(
            info_frame, text=f"MAC: {self.device.mac.upper()}",
            font=FONTS["mono_small"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        mac_label.pack(fill="x")

        # Action buttons
        if not self.device.is_self and not self.device.is_gateway:
            action_frame = ctk.CTkFrame(self, fg_color="transparent")
            action_frame.grid(row=0, column=2, rowspan=3, padx=16, pady=12, sticky="e")

            if self.device.is_throttled:
                # Restore button
                restore_btn = ctk.CTkButton(
                    action_frame,
                    text="✅ Normalkan",
                    font=FONTS["small"],
                    fg_color=COLORS["accent_success"],
                    hover_color=COLORS["accent_success_hover"],
                    text_color="white",
                    corner_radius=8,
                    width=130,
                    height=36,
                    command=lambda: self.on_restore(self.device.ip)
                )
                restore_btn.pack(pady=2)

                # Status label
                status = ctk.CTkLabel(
                    action_frame,
                    text="⚡ Throttled",
                    font=FONTS["tiny"],
                    text_color=COLORS["accent_danger"]
                )
                status.pack(pady=(4, 0))
            else:
                # Throttle button (full lag)
                lag_btn = ctk.CTkButton(
                    action_frame,
                    text="🚫 Lag Device",
                    font=FONTS["small"],
                    fg_color=COLORS["accent_danger"],
                    hover_color=COLORS["accent_danger_hover"],
                    text_color="white",
                    corner_radius=8,
                    width=130,
                    height=36,
                    command=lambda: self.on_throttle(self.device.ip, 0)
                )
                lag_btn.pack(pady=2)

                # Status label
                status = ctk.CTkLabel(
                    action_frame,
                    text="● Normal",
                    font=FONTS["tiny"],
                    text_color=COLORS["accent_success"]
                )
                status.pack(pady=(4, 0))


class WiFiThrottlerApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.engine = NetworkEngine()
        self.engine.on_devices_updated = self._on_devices_updated
        self.engine.on_status_changed = self._on_status_changed

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
            width=300,
            command=self._on_interface_selected
        )
        self.iface_dropdown.pack(side="left", padx=(0, 12))

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
            width=150,
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
            width=140,
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

        # Device count header
        self.device_header = ctk.CTkLabel(
            container,
            text="📋 Connected Devices (0)",
            font=FONTS["subtitle"],
            text_color=COLORS["text_primary"],
            anchor="w"
        )
        self.device_header.grid(row=0, column=0, sticky="w", pady=(0, 12))

        # Scrollable device list
        self.device_scroll = ctk.CTkScrollableFrame(
            container,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=COLORS["border_light"],
            scrollbar_button_hover_color=COLORS["accent_primary"]
        )
        self.device_scroll.grid(row=1, column=0, sticky="nsew")
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
        # Clear existing cards
        for widget in self.device_scroll.winfo_children():
            widget.destroy()

        devices = sorted(
            self.engine.devices.values(),
            key=lambda d: (
                not d.is_self,
                not d.is_gateway,
                not d.is_throttled,
                [int(x) for x in d.ip.split('.')]
            )
        )

        if not devices:
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
            empty_title.pack()
            return

        other_count = sum(1 for d in devices if not d.is_self and not d.is_gateway)
        self.device_header.configure(text=f"📋 Connected Devices ({other_count})")

        for idx, device in enumerate(devices):
            card = DeviceCard(
                self.device_scroll,
                device=device,
                on_throttle=self._throttle_device,
                on_restore=self._restore_device
            )
            card.grid(row=idx, column=0, sticky="ew", pady=(0, 6))

        # Update throttle count
        throttled = sum(1 for d in devices if d.is_throttled)
        self.throttle_count_label.configure(text=f"Throttled: {throttled}")

    def _throttle_device(self, ip: str, level: int):
        """Throttle a device."""
        device = self.engine.devices.get(ip)
        if device:
            confirm = messagebox.askyesno(
                "Confirm Throttle",
                f"Lag device {device.hostname} ({ip})?\n\n"
                f"This will significantly slow down their internet connection."
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

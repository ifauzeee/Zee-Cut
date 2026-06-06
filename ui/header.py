"""
Header frame creator for Zee-Cut main window.
"""

import customtkinter as ctk

from ui.theme import COLORS, FONTS


def create_header(app):
    """Create the header frame with title, credit, github button and admin badge."""
    app.header_frame = ctk.CTkFrame(app, fg_color=COLORS["bg_card"], corner_radius=0, height=86)
    app.header_frame.grid(row=0, column=0, sticky="ew")
    app.header_frame.grid_propagate(False)
    app.header_frame.grid_columnconfigure(1, weight=1)

    title_frame = ctk.CTkFrame(app.header_frame, fg_color="transparent")
    title_frame.grid(row=0, column=0, padx=24, pady=16, sticky="w")

    app.app_icon_label = ctk.CTkLabel(
        title_frame, text="\U0001F4F6",
        font=("Segoe UI Emoji", 34), text_color=COLORS["text_primary"], width=44
    )
    app.app_icon_label.pack(side="left", padx=(0, 12))

    title_text = ctk.CTkFrame(title_frame, fg_color="transparent")
    title_text.pack(side="left")

    app.title_label = ctk.CTkLabel(
        title_text, text="Zee-Cut",
        font=FONTS["title"], text_color=COLORS["text_primary"]
    )
    app.title_label.pack(anchor="w")

    app.subtitle_label = ctk.CTkLabel(
        title_text, text="Network Control Center",
        font=FONTS["small"], text_color=COLORS["text_muted"]
    )
    app.subtitle_label.pack(anchor="w")

    app.credit_label = ctk.CTkLabel(
        title_text, text="by Muhammad Ibnu Fauzi",
        font=FONTS["tiny"], text_color=COLORS["text_muted"]
    )
    app.credit_label.pack(anchor="w", pady=(1, 0))

    header_actions = ctk.CTkFrame(app.header_frame, fg_color="transparent")
    header_actions.grid(row=0, column=1, padx=24, pady=16, sticky="e")

    app.github_btn = ctk.CTkButton(
        header_actions, text="\U0001F419 GitHub",
        font=FONTS["small"], fg_color=COLORS["bg_input"],
        hover_color=COLORS["bg_card_hover"], text_color=COLORS["text_primary"],
        corner_radius=8, width=118, height=34, command=app._open_github_repo
    )
    app.github_btn.pack(side="left", padx=(0, 10))

    app.admin_badge = ctk.CTkLabel(
        header_actions, text="", font=FONTS["tiny"], corner_radius=6
    )
    app.admin_badge.pack(side="left")

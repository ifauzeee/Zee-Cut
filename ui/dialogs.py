"""
Dialog and messagebox helpers abstracted from the main app.
"""

from tkinter import messagebox


def admin_warning():
    messagebox.showwarning(
        "Administrator Required",
        "Zee-Cut needs Administrator privileges to function.\n\n"
        "Please right-click the application and select 'Run as administrator'.\n\n"
        "Without admin rights, scanning and throttling will not work."
    )


def interface_warning():
    messagebox.showwarning("Warning", "Please select a network interface first.")


def admin_required_dialog():
    messagebox.showwarning(
        "Admin Required",
        "Flush ARP membutuhkan hak Administrator.\nJalankan app sebagai Administrator."
    )

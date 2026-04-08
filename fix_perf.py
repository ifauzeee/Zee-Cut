import os
import re

def fix_file(path, replacements):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()
    
    for old, fresh in replacements:
        if old in content:
            content = content.replace(old, fresh)
            print(f"Replaced in {path}")
        else:
            # Try with different line endings if needed
            print(f"Could not find target in {path}")

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)

# GUI Fixes
gui_replacements = [
    (
        "        self.scan_in_progress = False",
        "        self.scan_in_progress = False\n        self._refresh_pending = False\n        self._last_refresh_time = 0.0\n        self._refresh_debounce_ms = 850"
    ),
    (
        """    def _on_devices_updated(self):
        self.after(0, self._handle_devices_updated_ui)

    def _handle_devices_updated_ui(self):
        if self.scan_in_progress:
            self._refresh_device_list()""",
        """    def _on_devices_updated(self):
        \"\"\"Handle signal that device data changed (new devices or hostnames).\"\"\"
        if not self._refresh_pending:
            self._refresh_pending = True
            # Use after to debounce the update
            self.after(self._refresh_debounce_ms, self._handle_throttled_devices_update)

    def _handle_throttled_devices_update(self):
        \"\"\"Throttled UI update to prevent freezing during high-activity scans.\"\"\"
        self._refresh_pending = False
        now = time.time()
        # Ensure at least some time has passed since last refresh to keep UI responsive
        if now - self._last_refresh_time < (self._refresh_debounce_ms / 1000.0):
            # If we refreshed too recently, check again shortly
            if not self._refresh_pending:
                self._refresh_pending = True
                self.after(200, self._handle_throttled_devices_update)
            return

        self._last_refresh_time = now
        # Always refresh if data changed, to show progress
        self._refresh_device_list()"""
    )
]

# Network Fixes
network_replacements = [
    (
        "with ThreadPoolExecutor(max_workers=workers) as pool:",
        "with ThreadPoolExecutor(max_workers=min(workers, 48)) as pool:"
    )
]

if __name__ == "__main__":
    fix_file('gui.py', gui_replacements)
    fix_file('core/network.py', network_replacements)

import os
import re

def fix_gui():
    path = 'gui.py'
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    # Fix the corrupted _on_scan_complete
    # We want to match the mess created by the previous script
    bad_pattern = re.compile(r'def _on_scan_complete\(self\):\n\s+def _done\(\):\n\s+self\.scan_in_progress = False\n\s+self\._refresh_pending = False\n\s+self\._last_refresh_time = 0\.0\n\s+self\._refresh_debounce_ms = 850\n\s+self\.scan_btn\.configure\(state="normal", text="Scan Network"\)\n\s+self\._refresh_device_list\(\)\n\s+self\.after\(0, _done\)', re.MULTILINE)
    
    good_on_scan = """    def _on_scan_complete(self):
        def _done():
            self.scan_in_progress = False
            self.scan_btn.configure(state="normal", text="Scan Network")
            self._refresh_device_list()
        self.after(0, _done)"""

    # Also replace the old methods with the throttled ones
    methods_pattern = re.compile(r'    def _on_devices_updated\(self\):\n\s+self\.after\(0, self\._handle_devices_updated_ui\)\n\n\s+def _handle_devices_updated_ui\(self\):\n\s+if self\.scan_in_progress:\n\s+self\._refresh_device_list\(\)', re.MULTILINE)
    
    new_methods = """    def _on_devices_updated(self):
        \"\"\"Handle signal that device data changed (new devices or hostnames).\"\"\"
        if not self._refresh_pending:
            self._refresh_pending = True
            self.after(self._refresh_debounce_ms, self._handle_throttled_devices_update)

    def _handle_throttled_devices_update(self):
        \"\"\"Throttled UI update to prevent freezing during high-activity scans.\"\"\"
        self._refresh_pending = False
        now = time.time()
        if now - self._last_refresh_time < (self._refresh_debounce_ms / 1000.0):
            if not self._refresh_pending:
                self._refresh_pending = True
                self.after(200, self._handle_throttled_devices_update)
            return
        self._last_refresh_time = now
        self._refresh_device_list()"""

    # If literal replacements failed, regex might work better OR we just find the lines
    
    # Try a more robust line-by-line fix for the corrupted part
    lines = content.splitlines()
    new_lines = []
    skip = 0
    for i in range(len(lines)):
        if skip > 0:
            skip -= 1
            continue
        
        # Detect the corrupted _on_scan_complete
        if "def _on_scan_complete(self):" in lines[i] and i+1 < len(lines) and "def _done():" in lines[i+1]:
            new_lines.append("    def _on_scan_complete(self):")
            new_lines.append("        def _done():")
            new_lines.append("            self.scan_in_progress = False")
            new_lines.append("            self.scan_btn.configure(state=\"normal\", text=\"Scan Network\")")
            new_lines.append("            self._refresh_device_list()")
            new_lines.append("        self.after(0, _done)")
            # Skip the next 8 lines as they are likely the mess
            # Actually find where _on_devices_updated starts to be sure
            j = i + 1
            while j < len(lines) and "_on_devices_updated" not in lines[j]:
                j += 1
            skip = j - i - 1
            continue
            
        # Detect the update methods
        if "def _on_devices_updated(self):" in lines[i]:
            new_lines.append(new_methods)
            # Skip until _on_status_changed or similar
            j = i + 1
            while j < len(lines) and "_on_status_changed" not in lines[j]:
                j += 1
            skip = j - i - 1
            continue
            
        new_lines.append(lines[i])

    content = "\n".join(new_lines)
    
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("Fixed gui.py")

if __name__ == "__main__":
    fix_gui()

"""
Fix setMode function signature to accept btn parameter
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dashboard_file = ROOT / "outputs" / "dashboard.html"

html = dashboard_file.read_text()

old = 'function setMode(mode) {{'
new = 'function setMode(mode, btn) {{'

html = html.replace(old, new)

dashboard_file.write_text(html)

print("✓ Fixed setMode() function signature to accept btn parameter")
print("✓ Dashboard updated successfully")

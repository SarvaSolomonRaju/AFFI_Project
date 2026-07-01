"""
Comprehensive Dashboard Fix Script - Fixes JavaScript event handling bugs
"""
import sys
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
dashboard_file = ROOT / "outputs" / "dashboard.html"

if not dashboard_file.exists():
    print("Error: dashboard.html not found.")
    sys.exit(1)

html = dashboard_file.read_text()

print("Fixing dashboard JavaScript and onclick handlers...")

html = re.sub(
    r'onclick="switchMode\(\'user\'\)"',
    'onclick="switchMode(\'user\', this)"',
    html
)

html = re.sub(
    r'onclick="switchMode\(\'developer\'\)"',
    'onclick="switchMode(\'developer\', this)"',
    html
)

html = re.sub(
    r'onclick="switchTab\(\'([^\']+)\'\)"',
    r'onclick="switchTab(\'\1\', this)"',
    html
)

html = re.sub(
    r'onclick="setMode\(\'([^\']+)\'\)"',
    r'onclick="setMode(\'\1\', this)"',
    html
)

old_switchTab = '''    function switchTab(tabId) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tabId).classList.add('active');
        event.target.classList.add('active');
    }'''

new_switchTab = '''    function switchTab(tabId, btn) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tabId).classList.add('active');
        if (btn) btn.classList.add('active');
    }'''

html = html.replace(old_switchTab, new_switchTab)

old_switchMode = '''    function switchMode(mode) {
        document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(mode + '-pane').classList.add('active');
        event.target.classList.add('active');
    }'''

new_switchMode = '''    function switchMode(mode, btn) {
        document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(mode + '-pane').classList.add('active');
        if (btn) btn.classList.add('active');
    }'''

html = html.replace(old_switchMode, new_switchMode)

old_setMode = '''    function setMode(mode) {
        document.querySelectorAll('[id$="-mode"]').forEach(m => m.style.display = 'none');
        document.querySelectorAll('[data-mode-btn]').forEach(b => b.classList.remove('active'));
        document.getElementById(mode + '-mode').style.display = 'block';
        event.target.classList.add('active');
    }'''

new_setMode = '''    function setMode(mode, btn) {
        document.querySelectorAll('[id$="-mode"]').forEach(m => m.style.display = 'none');
        document.querySelectorAll('[data-mode-btn]').forEach(b => b.classList.remove('active'));
        document.getElementById(mode + '-mode').style.display = 'block';
        if (btn) btn.classList.add('active');
    }'''

html = html.replace(old_setMode, new_setMode)

dashboard_file.write_text(html)

print("✓ Fixed switchMode() to accept button parameter")
print("✓ Fixed switchTab() to accept button parameter")
print("✓ Fixed setMode() to accept button parameter")
print("✓ Updated all onclick handlers to pass 'this' parameter")
print(f"✓ Dashboard saved to {dashboard_file}")
print("\nDashboard fixes applied successfully!")

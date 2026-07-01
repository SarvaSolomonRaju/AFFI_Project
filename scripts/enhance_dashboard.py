"""
Enhanced Dashboard Builder - Adds improved rainfall simulation controls
with better visual feedback, gradient slider, and real-time updates.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dashboard_file = ROOT / "outputs" / "dashboard.html"

if not dashboard_file.exists():
    print("Error: dashboard.html not found. Run build_dashboard.py first.")
    sys.exit(1)

html = dashboard_file.read_text()

enhanced_sim_view = '''    <!-- SIMULATION VIEW -->
    <div id="sim-view" style="display:none;">
    <div class="card" style="border-left:6px solid #b71c1c; background:#fff8f8; margin-top:0;">
      <h3 style="color:#b71c1c;">🌧 Enhanced Rainfall Simulation — Return Period Selector</h3>
      <p style="color:#666; font-size:0.9rem;">
        Select a storm return period (5-yr to 200-yr) using the slider below. All panels update automatically in real-time.
        Use this to test "what would happen if" scenarios for emergency planning with synthetic rainfall data.
      </p>

      <div style="background:linear-gradient(135deg, #1e2d3d 0%, #243a52 100%); padding:24px; border-radius:14px; margin:20px 0; border:3px solid #b71c1c; box-shadow:0 6px 20px rgba(183,28,28,0.25);">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; flex-wrap:wrap; gap:12px;">
          <span style="font-weight:700; color:#e8edf2; font-size:1.1rem;">📊 Return Period Selection:</span>
          <div id="sim-value-display" style="background:linear-gradient(135deg, #b71c1c, #e74c3c); color:#fff; padding:10px 26px; border-radius:24px; font-weight:900; font-size:1.5rem; min-width:140px; text-align:center; box-shadow:0 4px 14px rgba(183,28,28,0.4); letter-spacing:-0.5px;">
            100-yr
          </div>
        </div>
        
        <div style="display:flex; align-items:center; gap:16px; margin:20px 0;">
          <span style="font-weight:700; color:#e8edf2; min-width:40px; font-size:1rem; text-align:right;">5-yr</span>
          <div style="flex:1; position:relative; height:48px; background:linear-gradient(to right, #2ecc71 0%, #f39c12 20%, #e67e22 50%, #e74c3c 75%, #b71c1c 100%); border-radius:24px; padding:8px; box-shadow:0 6px 18px rgba(183,28,28,0.35); border:2px solid rgba(255,255,255,0.1);">
            <input type="range" id="sim-slider" min="0" max="5" step="1" value="4"
                   oninput="updateSimEnhanced(SIM_STEPS[this.value])"
                   style="position:absolute; top:0; left:0; width:100%; height:100%; opacity:0; cursor:pointer; z-index:2;">
            <div id="slider-thumb" style="position:absolute; top:50%; left:66.7%; transform:translate(-50%, -50%); width:36px; height:36px; background:#fff; border-radius:50%; box-shadow:0 4px 12px rgba(0,0,0,0.4); pointer-events:none; border:4px solid #b71c1c; transition:all 0.15s cubic-bezier(0.4, 0, 0.2, 1); z-index:1;"></div>
          </div>
          <span style="font-weight:700; color:#e8edf2; min-width:50px; font-size:1rem;">200-yr</span>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:#8899aa; margin:4px 58px 0px; font-weight:700;">
          <span>5yr</span><span>10yr</span><span>25yr</span><span>50yr</span><span>100yr</span><span>200yr</span>
        </div>
        
        <div style="margin-top:20px; padding:14px; background:rgba(183,28,28,0.1); border-radius:10px; border:1px solid rgba(183,28,28,0.3);">
          <div style="font-size:0.85rem; color:#e8edf2; font-weight:600; margin-bottom:6px;">💡 Rainfall Intensity Guide:</div>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px,1fr)); gap:8px; font-size:0.78rem;">
            <div style="color:#2ecc71;">🟢 5-10yr: Minor</div>
            <div style="color:#f39c12;">🟡 10-25yr: Moderate</div>
            <div style="color:#e67e22;">🟠 25-50yr: Major</div>
            <div style="color:#b71c1c;">🔴 50-200yr: Severe</div>
          </div>
        </div>
      </div>

      <div id="sim-label" style="text-align:center; font-size:1.6rem; font-weight:900; color:#b71c1c; margin:20px 0 10px; letter-spacing:-0.8px; text-shadow:0 2px 4px rgba(183,28,28,0.2);">
        T = 100-yr | Q = 455 cms | 1% annual probability
      </div>
      <div style="text-align:center; margin-bottom:24px;">
        <div id="sim-alert-badge" style="display:inline-block; padding:10px 32px; border-radius:28px; font-weight:900; font-size:1.2rem; background:linear-gradient(135deg, #b71c1c, #e74c3c); color:#fff; box-shadow:0 6px 18px rgba(183,28,28,0.5); text-transform:uppercase; letter-spacing:0.5px;">
          🔴 SEVERE — Catastrophic Flooding Expected
        </div>
      </div>

      <div class="hero-metrics" style="margin-top:24px; gap:16px;">
        <div class="hero-metric" style="border:2px solid rgba(183,28,28,0.4); background:rgba(183,28,28,0.05);">
          <div class="v" style="color:#b71c1c; font-size:2.4rem; font-weight:900;" id="sim-q">455</div><div class="l" style="font-weight:700;">Peak Q (cms)</div>
        </div>
        <div class="hero-metric" style="border:2px solid rgba(183,28,28,0.4); background:rgba(183,28,28,0.05);">
          <div class="v" style="color:#b71c1c; font-size:2.4rem; font-weight:900;" id="sim-maxdepth">12.00 m</div><div class="l" style="font-weight:700;">Max water depth</div>
        </div>
        <div class="hero-metric" style="border:2px solid rgba(183,28,28,0.4); background:rgba(183,28,28,0.05);">
          <div class="v" style="color:#b71c1c; font-size:2.4rem; font-weight:900;" id="sim-wetarea">5.28 km²</div><div class="l" style="font-weight:700;">Flood area</div>
        </div>
        <div class="hero-metric" style="border:2px solid rgba(183,28,28,0.4); background:rgba(183,28,28,0.05);">
          <div class="v" style="color:#b71c1c; font-size:2.4rem; font-weight:900;" id="sim-roads">154</div><div class="l" style="font-weight:700;">Roads at risk</div>
        </div>
      </div>
    </div>

    <script>
    function updateSimEnhanced(T) {
      updateSim(T);
      const slider = document.getElementById('sim-slider');
      const thumb = document.getElementById('slider-thumb');
      const valueDisplay = document.getElementById('sim-value-display');
      if (slider && thumb && valueDisplay) {
        const percent = (slider.value / slider.max) * 100;
        thumb.style.left = percent + '%';
        valueDisplay.textContent = T + '-yr';
        thumb.style.transform = 'translate(-50%, -50%) scale(1.1)';
        setTimeout(() => {
          thumb.style.transform = 'translate(-50%, -50%) scale(1)';
        }, 150);
      }
    }
    window.addEventListener('DOMContentLoaded', function() {
      const slider = document.getElementById('sim-slider');
      if (slider) {
        updateSimEnhanced(SIM_STEPS[parseInt(slider.value)]);
      }
    });
    </script>'''

start_marker = '    <!-- SIMULATION VIEW -->'
end_marker = '    </div><!-- end #sim-view -->'

start_idx = html.find(start_marker)
if start_idx == -1:
    print("Error: Could not find simulation view section")
    sys.exit(1)

end_idx = html.find(end_marker, start_idx)
if end_idx == -1:
    print("Error: Could not find end of simulation view section")
    sys.exit(1)

end_idx += len(end_marker)

enhanced_html = html[:start_idx] + enhanced_sim_view + '\n' + end_marker + '\n    ' + html[end_idx:]

dashboard_file.write_text(enhanced_html)
print(f"✓ Enhanced dashboard written to: {dashboard_file}")
print(f"✓ Rainfall simulation controls upgraded with:")
print("  - Gradient background slider showing intensity levels")
print("  - Real-time value display")  
print("  - Smooth animations and visual feedback")
print("  - Enhanced synthetic mode for gas/forecast data testing")
print(f"\nOpen in browser: file://{dashboard_file}")

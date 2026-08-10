"""Reference flood maps (src/probabilistic/reference_maps.py) — the labeled,
contextual map per return period. Checks the honest part: since this
pilot's flood library keeps the same EXTENT across return periods and only
scales DEPTH, the maps must differentiate by color/label, not by pretending
different buildings flood at each size."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from probabilistic.reference_maps import _depth_color, _m_to_ft, _town_bbox, render_reference_map


class TestReferenceMaps:
    def test_town_bbox_is_a_real_tight_box(self):
        w, e, s, n = _town_bbox()
        assert w < e and s < n
        # sane size — a few km across, not the whole ~18km watershed frame
        assert (e - w) < 0.04  # degrees longitude, roughly < 3.7 km here
        assert (n - s) < 0.04

    def test_depth_color_is_monotonically_darker(self):
        # Darker (lower luminance-ish proxy: just check hex strings differ
        # and follow the expected pale->dark progression via the colormap).
        c0 = _depth_color(0.0)
        c1 = _depth_color(1.0)
        c2 = _depth_color(3.0)
        assert c0 != c1 != c2
        # crude luminance check: sum of RGB channels should decrease as
        # depth increases (pale pink -> dark red)
        def _lum(hexcolor: str) -> int:
            hexcolor = hexcolor.lstrip("#")
            return sum(int(hexcolor[i:i + 2], 16) for i in (0, 2, 4))
        assert _lum(c0) > _lum(c1) > _lum(c2)

    def test_depth_color_clips_extreme_outliers_to_darkest(self):
        # A handful of buildings/road segments sit right at the creek-channel
        # edge with extreme depth values (up to 12+ m) that are a BFE/DEM
        # artifact, not a realistic building depth -- these must clip to the
        # same darkest shade, not blow out the color scale for everything else.
        assert _depth_color(3.5) == _depth_color(12.7)

    def test_m_to_ft_conversion(self):
        assert abs(_m_to_ft(1.0) - 3.28084) < 1e-4

    def test_render_produces_a_real_png_file(self, tmp_path):
        out = render_reference_map(100, tmp_path / "test_100yr.png")
        assert out.exists()
        assert out.stat().st_size > 50_000  # a real rendered map, not a blank/broken file

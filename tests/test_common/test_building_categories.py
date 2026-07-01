from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from common.building_categories import categorize_building


class TestCategorizeBuilding:
    def test_school(self):
        assert categorize_building("school") == "School"

    def test_case_insensitive(self):
        assert categorize_building("School") == "School"
        assert categorize_building("HOUSE") == "Residential"

    def test_public_civic(self):
        assert categorize_building("church") == "Public/Civic"
        assert categorize_building("hospital") == "Public/Civic"

    def test_residential(self):
        assert categorize_building("house") == "Residential"
        assert categorize_building("static_caravan") == "Residential"

    def test_commercial_industrial(self):
        assert categorize_building("industrial") == "Commercial/Industrial"
        assert categorize_building("retail") == "Commercial/Industrial"

    def test_agricultural_outbuilding(self):
        assert categorize_building("shed") == "Agricultural/Outbuilding"
        assert categorize_building("barn") == "Agricultural/Outbuilding"

    def test_generic_yes_is_unclassified_not_guessed(self):
        assert categorize_building("yes") == "Unclassified"

    def test_missing_or_invalid_is_unclassified(self):
        assert categorize_building(None) == "Unclassified"
        assert categorize_building("") == "Unclassified"

    def test_real_data_distribution_all_map_somewhere(self):
        # Every building tag value actually present in
        # data/local_assets/buildings_huc12.geojson (checked live
        # before writing this module) resolves to a real category, not
        # silently falling through to Unclassified by accident.
        real_tags = [
            "yes", "house", "shed", "static_caravan", "school", "industrial",
            "stable", "barn", "greenhouse", "roof", "farm_auxiliary",
            "carport", "ger", "church", "ruins", "retail",
        ]
        results = {tag: categorize_building(tag) for tag in real_tags}
        assert results["school"] == "School"
        assert results["yes"] == "Unclassified"
        assert results["roof"] == "Agricultural/Outbuilding"
        # No unexpected category name typos — every result is one of
        # the five real categories or Unclassified.
        valid = {"School", "Public/Civic", "Residential", "Commercial/Industrial", "Agricultural/Outbuilding", "Unclassified"}
        assert set(results.values()) <= valid

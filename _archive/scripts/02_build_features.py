"""
02_build_features.py — Build train/val/test datasets and persist scalers.

Run after 01_download_data.py succeeds.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.common import configure_logging
from src.common.paths import DATA_INTERIM, MODELS_DIR
from src.hydrology.features import build_sequences


def main() -> int:
    configure_logging("INFO", to_file=True)

    parquet = DATA_INTERIM / "walnut_gulch_daily.parquet"
    if not parquet.exists():
        print(f"❌ Missing {parquet}. Run scripts/01_download_data.py first.")
        return 1

    df = pd.read_parquet(parquet)

    lookback = 30
    X, y_cls, y_reg, _ = build_sequences(
        df,
        lookback=lookback,
        fit_scaler=True,
        scaler_path=MODELS_DIR / "feature_scaler.joblib",
    )

    n = len(X)
    t1, t2 = int(n * 0.70), int(n * 0.85)

    print("\n✓ Feature build complete")
    print(f"  train windows : {t1}")
    print(f"  val windows   : {t2 - t1}")
    print(f"  test windows  : {n - t2}")
    print(f"  x shape       : {tuple(X.shape)}")
    print(f"  y_cls dtype   : {y_cls.dtype}")
    print(f"  y_reg dtype   : {y_reg.dtype}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""
paths.py — Single source of truth for all filesystem paths.

WHY THIS EXISTS:
    Hardcoded paths like "data/raw/file.csv" break when:
    - You run a script from a different folder
    - You move the project to another machine
    - A teammate clones the repo on Linux instead of macOS

    This module computes the project root ONCE (relative to this file)
    and exposes every path your code might need. Import from here, never
    write paths inline.

USAGE:
    from common.paths import DATA_RAW, MODELS_DIR
    df = pd.read_csv(DATA_RAW / "usgs" / "09471500.csv")
    torch.save(state, MODELS_DIR / "best.pt")

DESIGN NOTE:
    Uses pathlib.Path, not os.path strings. Path objects support /
    operator (Path / "subdir" / "file.csv") which is OS-agnostic and
    far less error-prone than os.path.join().
"""

from pathlib import Path

# ============================================================================
# Project root — computed ONCE relative to this file's location.
# This file lives at:  <root>/src/common/paths.py
# So root = parents[2]: paths.py → common → src → <root>
# ============================================================================
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

# ============================================================================
# Top-level directories
# ============================================================================
CONFIG_DIR:    Path = PROJECT_ROOT / "config"
SRC_DIR:       Path = PROJECT_ROOT / "src"
SCRIPTS_DIR:   Path = PROJECT_ROOT / "scripts"
TESTS_DIR:     Path = PROJECT_ROOT / "tests"
DATA_DIR:      Path = PROJECT_ROOT / "data"
MODELS_DIR:    Path = PROJECT_ROOT / "models"
OUTPUTS_DIR:   Path = PROJECT_ROOT / "outputs"

# ============================================================================
# Data subdirectories — three-tier data architecture (industry standard)
#   raw/       = exactly as downloaded; NEVER modified, NEVER committed
#   interim/   = cleaned, aligned, quality-checked; intermediate stage
#   processed/ = ML-ready tensors + scalers; what the trainer consumes
# ============================================================================
DATA_RAW:       Path = DATA_DIR / "raw"
DATA_INTERIM:   Path = DATA_DIR / "interim"
DATA_PROCESSED: Path = DATA_DIR / "processed"

# Specific raw-data sources
USGS_DIR: Path = DATA_RAW / "usgs"
USGS_LEGACY_DIR: Path = DATA_RAW / "usgs_nwis"
if USGS_LEGACY_DIR.exists() and not USGS_DIR.exists():
    USGS_DIR = USGS_LEGACY_DIR
if USGS_LEGACY_DIR.exists() and USGS_DIR.exists():
    USGS_DIR = USGS_LEGACY_DIR  # Prefer legacy dir if both exist
ERA5_DIR:      Path = DATA_RAW / "era5"       # reanalysis NetCDFs
ARS_DIR:       Path = DATA_RAW / "ars"         # USDA-ARS DAP CSVs
OPENMETEO_DIR: Path = DATA_RAW / "openmeteo"    # Open-Meteo forcing parquet

# ============================================================================
# Output subdirectories
# ============================================================================
FIGURES_DIR: Path = OUTPUTS_DIR / "figures"
LOGS_DIR:    Path = OUTPUTS_DIR / "logs"

# ============================================================================
# Config files
# ============================================================================
TASK2_CONFIG: Path = CONFIG_DIR / "task2.yaml"


def ensure_dirs() -> None:
    """
    Create all standard directories if they don't exist.

    Call this once at the start of any script that writes files.
    Safe to call repeatedly — Path.mkdir(exist_ok=True) is idempotent.

    WHY: New developers cloning the repo won't have data/raw/ etc.
    Better to auto-create than to crash with FileNotFoundError.
    """
    for d in [
        DATA_RAW, DATA_INTERIM, DATA_PROCESSED,
        USGS_DIR, ERA5_DIR, ARS_DIR, OPENMETEO_DIR,
        MODELS_DIR, FIGURES_DIR, LOGS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # Sanity check: print all paths and verify root is correct
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"  exists: {PROJECT_ROOT.exists()}")
    print(f"DATA_RAW:     {DATA_RAW}")
    print(f"MODELS_DIR:   {MODELS_DIR}")
    ensure_dirs()
    print("✓ All directories created/verified.")
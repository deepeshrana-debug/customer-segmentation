import subprocess
import sys
from pathlib import Path

EXPECTED_FILES = [
    "segments.csv",
    "segment_profile.csv",
    "k_selection.csv",
    "elbow_plot.png",
    "segments_plot.png",
    "segment_sizes.png",
]

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_writes_all_files(tmp_path):
    data_file = tmp_path / "transactions.csv"
    gen = subprocess.run(
        [sys.executable, "src/generate_data.py",
         "--customers", "50", "--out", str(data_file)],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert gen.returncode == 0, gen.stderr
    assert data_file.exists()

    out_dir = tmp_path / "out"
    run = subprocess.run(
        [sys.executable, "src/main.py",
         "--data", str(data_file), "--out", str(out_dir), "--k", "3"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert run.returncode == 0, run.stderr

    for name in EXPECTED_FILES:
        assert (out_dir / name).exists(), f"missing {name}"

    assert (out_dir / "rfm_scores.csv").exists()
    assert (out_dir / "churn_summary.csv").exists()

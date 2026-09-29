"""Generate the Sprint 3 batch artefacts for Task 59.

Runs every approved scenario against the MILP v1.0 schema, then copies the
run manifest and comparison into samples/sprint3/ under the names Task 59
asks for. runs/ is gitignored, so the deliverables need a tracked home.

Defaults to mock mode against the solved v1 fixture, because Optimisation's
real output files are not available yet. Point it at them with --ingest-dir
once they are, and the same command regenerates all three files.

    python build_sprint3_run.py
    python build_sprint3_run.py --ingest-dir path/to/milp_outputs
"""

import argparse
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from batch_runner import (  # noqa: E402
    INGEST,
    MOCK,
    V1_FIXTURE,
    run_batch,
    write_run,
)
from comparison_report import build_comparison, write_comparison  # noqa: E402

SCENARIOS = HERE.parent / "scenarios"
SAMPLES = HERE / "samples" / "sprint3"

DELIVERABLES = {
    "run_manifest.json": "run_manifest_sprint3.json",
    "comparison.json": "comparison_report_sprint3.json",
    "comparison.csv": "comparison_report_sprint3.csv",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ingest-dir",
        help="Folder of real MILP v1.0 output files. Omit to use the solved fixture.",
    )
    args = parser.parse_args()

    if args.ingest_dir:
        batch = run_batch(SCENARIOS, INGEST, ingest_dir=Path(args.ingest_dir))
    else:
        batch = run_batch(SCENARIOS, MOCK, fixture_path=V1_FIXTURE)

    run_dir = write_run(batch, output_root=HERE / "runs")
    write_comparison(build_comparison(batch), run_dir)

    SAMPLES.mkdir(parents=True, exist_ok=True)
    for produced, deliverable in DELIVERABLES.items():
        shutil.copy(run_dir / produced, SAMPLES / deliverable)

    print(f"run: {run_dir}")
    print(f"mode: {batch['mode']}")
    print(f"scenarios: {batch['succeeded']} ok, {batch['failed']} failed")
    for deliverable in DELIVERABLES.values():
        print(f"wrote {SAMPLES / deliverable}")


if __name__ == "__main__":
    main()
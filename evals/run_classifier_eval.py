"""Score the classifier against a hand-labeled CSV.

Reports overall accuracy plus per-class precision and recall, logs the prompt
version + model, writes a timestamped JSON report to evals/results/, and inserts
a row into the eval_runs table.

    uv run python -m evals.run_classifier_eval [labels.csv]
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from cost_engine.classify.classifier import classify
from cost_engine.classify.taxonomy import TAXONOMY_VALUES, is_valid
from cost_engine.config import CONFIG
from cost_engine.db import get_initialized_connection
from cost_engine.llm.prompts import CLASSIFIER_PROMPT_VERSION

RESULTS_DIR = Path(__file__).with_name("results")
DEFAULT_LABELS = Path(__file__).with_name("labels") / "classifier_labels.csv"


def _read_rows(path: Path) -> list[dict[str, str]]:
    """Read the labels CSV, skipping leading comment lines (starting with #)."""
    lines = [ln for ln in path.read_text().splitlines() if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(lines)
    return [row for row in reader if (row.get("work_description") or "").strip()]


def _per_class_metrics(pairs: list[tuple[str, str]]) -> dict[str, dict[str, float | int]]:
    """pairs = list of (gold, predicted)."""
    metrics: dict[str, dict[str, float | int]] = {}
    for cls in TAXONOMY_VALUES:
        tp = sum(1 for g, p in pairs if g == cls and p == cls)
        fp = sum(1 for g, p in pairs if p == cls and g != cls)
        fn = sum(1 for g, p in pairs if g == cls and p != cls)
        support = sum(1 for g, _ in pairs if g == cls)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        metrics[cls] = {
            "support": support,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        }
    return metrics


def run(labels_path: Path = DEFAULT_LABELS) -> int:
    if not labels_path.exists():
        print(
            f"Labels file not found: {labels_path}\n"
            "Copy evals/labels/classifier_labels_template.csv to "
            "evals/labels/classifier_labels.csv and hand-label ~100 rows."
        )
        return 1

    conn = get_initialized_connection()
    rows = _read_rows(labels_path)
    pairs: list[tuple[str, str]] = []
    bad_gold: list[str] = []

    print(
        f"Evaluating classifier (model={CONFIG.classifier_model}, "
        f"prompt={CLASSIFIER_PROMPT_VERSION}) over {len(rows)} labeled rows ..."
    )
    for row in rows:
        gold = (row.get("gold_job_type") or "").strip()
        if not is_valid(gold):
            bad_gold.append(gold)
            continue
        pred = classify(row["work_description"], conn=conn).job_type.value
        pairs.append((gold, pred))

    if bad_gold:
        print(f"WARNING: {len(bad_gold)} rows had invalid gold labels and were skipped: "
              f"{sorted(set(bad_gold))}")
    if not pairs:
        print("No valid labeled rows to score.")
        return 1

    correct = sum(1 for g, p in pairs if g == p)
    accuracy = correct / len(pairs)
    per_class = _per_class_metrics(pairs)

    report = {
        "prompt_version": CLASSIFIER_PROMPT_VERSION,
        "model": CONFIG.classifier_model,
        "n_examples": len(pairs),
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist: JSON report (committed) + eval_runs row.
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"classifier_{CLASSIFIER_PROMPT_VERSION}_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2))
    conn.execute(
        "INSERT INTO eval_runs (prompt_version, model, n_examples, accuracy, report_json, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (
            CLASSIFIER_PROMPT_VERSION,
            CONFIG.classifier_model,
            len(pairs),
            accuracy,
            json.dumps(report),
            report["created_at"],
        ),
    )
    conn.commit()

    # Print summary.
    print(f"\nAccuracy: {accuracy:.1%}  ({correct}/{len(pairs)})")
    print(f"{'class':35s} {'support':>7s} {'prec':>6s} {'recall':>7s}")
    print("-" * 60)
    for cls, m in per_class.items():
        print(f"{cls:35s} {m['support']:>7d} {m['precision']:>6.2f} {m['recall']:>7.2f}")
    print(f"\nReport written to {out_path}")
    return 0


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LABELS
    sys.exit(run(path))

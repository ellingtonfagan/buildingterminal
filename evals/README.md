# Evals

Stage 2 classifier evaluation.

## Hand-labeling

1. After ingesting (Stage 1) and classifying (Stage 2), export ~100 filings you
   will hand-label. A starter template is `labels/classifier_labels_template.csv`.
2. Copy it to `labels/classifier_labels.csv` and fill in the `gold_job_type`
   column with the correct taxonomy value (see the valid values printed at the
   top of the template). Leave `predicted_job_type` blank — the harness fills it
   from the classifier at run time.

Each row needs at least: `work_description`, `gold_job_type`.

## Run

```bash
uv run python -m evals.run_classifier_eval
# or point at a specific labels file:
uv run python -m evals.run_classifier_eval labels/classifier_labels.csv
```

The harness:

- runs the current classifier over each `work_description`,
- computes overall accuracy plus **per-class precision and recall**,
- **logs the prompt version and model** with the run,
- writes a timestamped JSON report to `results/` (committed) and a row to the
  `eval_runs` table.

This makes prompt versions comparable over time: change the prompt, bump
`CLASSIFIER_PROMPT_VERSION`, re-run, and diff the reports in `results/`.

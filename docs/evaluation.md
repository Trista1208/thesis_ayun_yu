# Reproducing the Evaluation

This document describes how to reproduce the technical evaluation of the rule engine
reported in the accompanying thesis.

## 1. Rule-engine boundary tests

The suite in [`backend/tests/test_rule_engine.py`](../backend/tests/test_rule_engine.py)
evaluates the rule engine against synthetic member profiles. It covers:

- **Threshold cases.** Values at, just below and just above rating cut-points (for example
  VO2max, grip strength, LDL, HbA1c), checking the resulting rating band.
- **Priority assignment.** That a triggered recommendation's priority follows the
  deviation of the rating (below average leads to Medium, poor to High).
- **Missing-value guards.** That zero or blank inputs are treated as not measured rather
  than rated as poor.

Expected values are derived from `knowledge/sports_health_recommendations.yml` (version 2.2).
Tests marked `xfail` document known defects and fail the suite if they are unexpectedly fixed.

### Procedure

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest backend/tests -v
```

No API keys, network access or database are required. The suite is deterministic.

## 2. Recorded thesis runs

The scripts and saved results cited in the thesis are kept in [`evaluation/`](../evaluation/) under those file names:

- `eval_threshold_suite_v2.py`, `eval_threshold_results_v2.json`
- `eval_joule_scripts.py`, `eval_joule_scores.json`
- `eval_joule_answers_gemini.jsonl`, `eval_joule_answers_qwen.jsonl`

## 3. Scope and limitations

The automated suite tests the decision layer only. The appropriateness of the
recommendations was assessed through expert review, and the behaviour of
the LLM layer is not covered by automated tests. The fictional cases in `database/demo/`
can be loaded to reproduce the qualitative walkthroughs of the member and expert
workflows (see [`database/README.md`](../database/README.md)).

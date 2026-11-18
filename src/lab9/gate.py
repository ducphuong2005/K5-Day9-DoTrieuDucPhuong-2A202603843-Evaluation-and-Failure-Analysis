"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    import math
    problems: list[str] = []

    # 1. NaN or inf in metrics
    for mid, val in pr.get("metrics", {}).items():
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            problems.append(f"metric {mid!r} is {val} (NaN/inf)")

    # 2. Row count must equal manifest items × seeds
    mf = pr.get("manifest", {})
    expected_rows = mf.get("items", 0) * len(mf.get("seeds", []))
    actual_rows = len(pr.get("rows", []))
    if actual_rows != expected_rows:
        problems.append(
            f"row count {actual_rows} != manifest items {mf.get('items')} × seeds {len(mf.get('seeds', []))} = {expected_rows}"
        )

    # 3. (item_id, seed) set must match baseline's
    pr_pairs = {(r["item_id"], r["seed"]) for r in pr.get("rows", [])}
    base_pairs = {(r["item_id"], r["seed"]) for r in base.get("rows", [])}
    if pr_pairs != base_pairs:
        only_pr = pr_pairs - base_pairs
        only_base = base_pairs - pr_pairs
        if only_pr:
            problems.append(f"PR has {len(only_pr)} (item,seed) pair(s) not in baseline (cherry-pick?)")
        if only_base:
            problems.append(f"PR is missing {len(only_base)} (item,seed) pair(s) from baseline (dropped?)")

    # 4. Evaluator failures or None-valued graded metrics
    if pr.get("evaluator_failures"):
        problems.append(f"{len(pr['evaluator_failures'])} evaluator_failure(s) in PR")
    graded_ids = {m["id"] for m in spec.get("metrics", []) if m.get("grader") == "code" or m.get("kind") in ("safety", "capability")}
    for r in pr.get("rows", []):
        for mid in graded_ids:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')}: grader {mid!r} returned None")
                break  # one problem per row is enough

    # 5. Ratchet: spec thresholds must not be looser than base_spec
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        base_metrics = {m["id"]: m for m in base_spec.get("metrics", [])}
        for m in spec.get("metrics", []):
            mid = m["id"]
            if mid not in base_metrics:
                continue  # new metric is fine
            bm = base_metrics[mid]
            bth, th = bm.get("threshold", {}), m.get("threshold", {})
            if "max" in bth and "max" in th and th["max"] > bth["max"]:
                problems.append(f"ratchet: {mid} max raised {bth['max']} → {th['max']}")
            if "min" in bth and "min" in th and th["min"] < bth["min"]:
                problems.append(f"ratchet: {mid} min lowered {bth['min']} → {th['min']}")
            if bm.get("blocking") and not m.get("blocking"):
                problems.append(f"ratchet: {mid} blocking → non-blocking")
            if bth.get("no_significant_drop") and not th.get("no_significant_drop"):
                problems.append(f"ratchet: {mid} no_significant_drop removed")
        # Disappeared metrics
        spec_ids = {m["id"] for m in spec.get("metrics", [])}
        for mid in base_metrics:
            if mid not in spec_ids:
                problems.append(f"ratchet: metric {mid!r} disappeared from spec")
        # Slices: must not be dropped or loosened
        base_slices = {s["name"]: s for s in base_spec.get("slices", [])}
        spec_slices = {s["name"]: s for s in spec.get("slices", [])}
        for sname, bs in base_slices.items():
            if sname not in spec_slices:
                problems.append(f"ratchet: slice {sname!r} dropped")
                continue
            ss = spec_slices[sname]
            if "min" in bs and "min" in ss and ss["min"] < bs["min"]:
                problems.append(f"ratchet: slice {sname} min lowered {bs['min']} → {ss['min']}")
            if bs.get("no_significant_drop") and not ss.get("no_significant_drop"):
                problems.append(f"ratchet: slice {sname} no_significant_drop removed")
            if bs.get("blocking") and not ss.get("blocking"):
                problems.append(f"ratchet: slice {sname} blocking → non-blocking")

    # 6. Slice tags in PR rows must match baseline's
    base_slices_by_item: dict[str, set] = {}
    for r in base.get("rows", []):
        base_slices_by_item[r["item_id"]] = set(r.get("slices") or [])
    for r in pr.get("rows", []):
        iid = r["item_id"]
        if iid in base_slices_by_item:
            pr_slices = set(r.get("slices") or [])
            if pr_slices != base_slices_by_item[iid]:
                problems.append(f"item {iid}: slice tags changed {base_slices_by_item[iid]} → {pr_slices}")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for sl in spec.get("slices", []):
        name, metric = sl["name"], sl["metric"]
        sid = f"slice:{name}/{metric}"
        pr_items = per_item(pr, metric, slice_name=name)
        base_items = per_item(base, metric, slice_name=name)
        if not pr_items:
            lines.append(f"  {sid:<30} (no items in slice)")
            continue
        val = round(sum(pr_items.values()) / len(pr_items), 4)
        verdict, note = "ok", ""
        min_th = sl.get("min")
        if min_th is not None and val < min_th:
            verdict = "fail"
        if sl.get("no_significant_drop"):
            keys = sorted(set(pr_items) & set(base_items))
            if keys:
                a_vals = [pr_items[k] for k in keys]
                b_vals = [base_items[k] for k in keys]
                d, lo, hi = stats.paired_bootstrap(a_vals, b_vals,
                                                    n_resamples=bs.get("n_resamples", 1000),
                                                    rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and sl.get("blocking"):
            blocked.append(sid)
        label = "BLOCK" if verdict != "ok" and sl.get("blocking") else ("warn" if verdict != "ok" else "ok")
        min_str = f"min={min_th}" if min_th is not None else ""
        lines.append(f"  {sid:<30} {val!s:<8} {min_str:<10} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                                   n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

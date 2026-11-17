"""Gold-set sampling: stratified annotation sheets from a `relief extract` run (see docs/annotation-guidelines.md).

    relief gold sample --run-id pilot-r1r4-v3 --n 1000 --overlap 300 --calibration 30

Writes <run>/gold/: calibration.csv (both annotators), annotator_A.csv, annotator_B.csv, key.csv (hidden from
annotators: strata, original-GT flag, QIDs), and sample.json (counts per stratum).
"""
from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

SHEET_COLUMNS = ["item_id", "root_label", "subject_label", "predicate_label", "object_label", "predicate_description",
                 "evidence_type", "evidence", "context", "mention", "found_by", "wikipedia_url",
                 "label", "reason", "note"]


def stratum(instance: dict) -> tuple:
    return (instance["evidence_type"], "link" if instance["mention_source"] == "link" else "unlinked",
            "multi" if instance["multi_predicate"] else "single", "naming" if instance["naming"] else "relation")


def allocate(sizes: dict, total: int, minimum: int) -> dict:
    """Every stratum gets min(size, minimum); the rest is shared in proportion to size."""
    share = {s: min(n, minimum) for s, n in sizes.items()}
    rest = total - sum(share.values())
    spare = {s: n - share[s] for s, n in sizes.items()}
    weight = sum(spare.values()) or 1
    for s in sorted(spare, key=spare.get, reverse=True):
        extra = min(spare[s], round(rest * spare[s] / weight))
        share[s] += extra
    overshoot = sum(share.values()) - total
    for s in sorted(share, key=share.get, reverse=True):
        if overshoot <= 0:
            break
        cut = min(overshoot, share[s] - min(sizes[s], minimum))
        share[s] -= cut
        overshoot -= cut
    return share


def sample(instances: list[dict], n: int, minimum: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    groups = defaultdict(list)
    for instance in instances:
        groups[stratum(instance)].append(instance)
    quota = allocate({s: len(v) for s, v in groups.items()}, min(n, len(instances)), minimum)
    chosen = []
    for s in sorted(groups):
        pool = list(groups[s])
        rng.shuffle(pool)
        chosen += pool[:quota[s]]
    rng.shuffle(chosen)
    return chosen


def write_sheets(run_dir: Path, instances: list[dict], labels: dict, predicates: dict, pages: dict,
                 n: int = 1000, overlap: int = 300, calibration: int = 30, minimum: int = 30, seed: int = 2026) -> dict:
    chosen = sample(instances, n + calibration, minimum, seed)
    out = run_dir / "gold"
    out.mkdir(parents=True, exist_ok=True)

    def row(i: int, inst: dict) -> dict:
        p_label, p_desc = predicates.get(inst["predicate"], (inst["predicate"], ""))
        return {"item_id": f"G{i:04d}", "root_label": labels.get(inst["root"], inst["root"]),
                "subject_label": labels.get(inst["subject"], inst["subject"]), "predicate_label": p_label,
                "object_label": labels.get(inst["object"], inst["object"]), "predicate_description": p_desc or "",
                "evidence_type": inst["evidence_type"], "evidence": inst["evidence"], "context": inst["context"],
                "mention": inst["mention"], "found_by": inst["mention_source"],
                "wikipedia_url": f"https://en.wikipedia.org/?curid={pages.get(inst['root'], '')}",
                "label": "", "reason": "", "note": ""}

    rows = [row(i, inst) for i, inst in enumerate(chosen, 1)]
    calib, main = rows[:calibration], rows[calibration:]
    both, rest = main[:overlap], main[overlap:]
    sheets = {"calibration": calib, "annotator_A": both + rest[::2], "annotator_B": both + rest[1::2]}
    for name, sheet in sheets.items():
        sheet = sorted(sheet, key=lambda r: r["item_id"])
        with open(out / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(sheet)
    with open(out / "key.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item_id", "set", "root", "subject", "predicate", "object", "unit", "stratum",
                         "mention_rule", "in_original_gt"])
        overlap_ids = {r["item_id"] for r in both}
        calib_ids = {r["item_id"] for r in calib}
        for r, inst in zip(rows, chosen):
            group = "calibration" if r["item_id"] in calib_ids else "overlap" if r["item_id"] in overlap_ids else "single"
            writer.writerow([r["item_id"], group, inst["root"], inst["subject"], inst["predicate"], inst["object"],
                             inst["unit"], "/".join(stratum(inst)), inst["mention_rule"], inst["in_original_gt"]])
    counts = defaultdict(int)
    for inst in chosen:
        counts["/".join(stratum(inst))] += 1
    summary = {"instances_in_run": len(instances), "sampled": len(chosen), "calibration": len(calib),
               "overlap": len(both), "single_A": len(rest[::2]), "single_B": len(rest[1::2]),
               "per_stratum": dict(sorted(counts.items())), "seed": seed}
    (out / "sample.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

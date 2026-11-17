"""Pilot seed selection: a small, stratified, reproducible sample of the WikES seed sets."""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

# WikES seed set number -> dataset name (wiki-entity-summarization/data/seed_nodes/<n>/<n>.csv)
SEED_SETS = {1: "WikiLitArt", 2: "WikiCinema", 3: "WikiPro", 4: "WikiProFem"}


def read_seed_set(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [{"qid": r["wikidata_code"].strip(), "name": r["name"], "category": r["level3_main_occ"]}
                for r in csv.DictReader(f)]


def allocate(sizes: dict[str, int], total: int) -> dict[str, int]:
    """At least one per category, the rest in proportion to size (largest remainder)."""
    if total < len(sizes):
        raise ValueError(f"cannot give each of {len(sizes)} categories a seed with only {total}")
    share = {c: 1 for c in sizes}
    rest = total - len(sizes)
    weight = sum(sizes.values())
    exact = {c: rest * n / weight for c, n in sizes.items()}
    for c in sizes:
        share[c] += int(exact[c])
    leftover = total - sum(share.values())
    for c in sorted(sizes, key=lambda c: (exact[c] - int(exact[c]), sizes[c]), reverse=True)[:leftover]:
        share[c] += 1
    return share


def select_pilot(seed_sets: dict[str, list[dict]], per_set: dict[str, int], rng_seed: int = 2026) -> list[dict]:
    rng = random.Random(rng_seed)
    chosen: list[dict] = []
    taken: set[str] = set()
    for set_name, rows in seed_sets.items():
        by_category: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_category[row["category"]].append(row)
        quota = allocate({c: len(v) for c, v in by_category.items()}, per_set[set_name])
        for category in sorted(by_category):
            pool = [r for r in by_category[category] if r["qid"] not in taken]
            rng.shuffle(pool)
            for row in pool[:quota[category]]:
                taken.add(row["qid"])
                chosen.append({**row, "seed_set": set_name})
    return chosen


def write_pilot(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["qid", "name", "seed_set", "category"])
        writer.writeheader()
        writer.writerows({k: r[k] for k in writer.fieldnames} for r in rows)

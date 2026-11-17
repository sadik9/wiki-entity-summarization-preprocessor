"""R4: candidate instances, one per (candidate edge, evidence unit that mentions its neighbour); plus `relief extract`."""
from __future__ import annotations

import csv
import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import relief
from relief.candidates import KnowledgeBase, RootContext
from relief.mentions import AliasIndex, MentionStats, build_alias_index, find_mentions
from relief.policy import NAMING_PROPERTIES, POLICY_VERSION
from relief.text import Lead, page_links, prepare

MENTION_PRIORITY = ["link", "name", "label", "title", "redirect", "anchor"]


@dataclass
class Instance:
    root: str
    subject: str
    predicate: str
    object: str
    neighbour: str
    root_is_subject: bool
    unit: str                 # s<id> or ib:<template>|<param>
    evidence_type: str        # prose | infobox
    evidence: str             # the sentence, or the whole infobox field ("Instruments: Vocals; guitar; piano")
    context: str              # the previous sentence (prose), else ""
    mention: str
    mention_source: str
    mention_rule: str
    naming: bool
    multi_predicate: bool     # the pair (root, neighbour) has several candidate edges
    in_original_gt: bool      # the triple is a SUMMARY edge of the root in WikES 1.0.x


def align(ctx: RootContext, lead: Lead, mentions, original_gt: set) -> list[Instance]:
    by_neighbour = defaultdict(list)
    for mention in mentions:
        by_neighbour[mention.qid].append(mention)
    live = [c for c in ctx.candidates if c.excluded is None]
    per_pair = Counter(c.neighbour for c in live)
    sentences = {f"s{s.id}": s for s in lead.sentences}
    fields = {f"ib:{f.template}|{f.param}": f for f in lead.infobox}
    instances = []
    for candidate in live:
        best_per_unit = {}
        for mention in by_neighbour.get(candidate.neighbour, []):
            if (mention.source == "name") != (candidate.predicate in NAMING_PROPERTIES):
                continue          # naming mentions only support naming edges, and naming edges only those
            current = best_per_unit.get(mention.unit)
            if current is None or MENTION_PRIORITY.index(mention.source) < MENTION_PRIORITY.index(current.source):
                best_per_unit[mention.unit] = mention
        for unit, mention in best_per_unit.items():
            if unit.startswith("s"):
                sentence = sentences[unit]
                previous = sentences.get(f"s{sentence.id - 1}")
                evidence, context, kind = sentence.text, previous.text if previous else "", "prose"
            else:
                field_ = fields[unit]
                evidence, context, kind = f"{field_.param.replace('_', ' ')}: {field_.text}", "", "infobox"
            instances.append(Instance(
                ctx.root.qid, candidate.subject, candidate.predicate, candidate.object, candidate.neighbour,
                candidate.root_is_subject, unit, kind, evidence, context, mention.surface, mention.source,
                mention.rule, candidate.predicate in NAMING_PROPERTIES, per_pair[candidate.neighbour] > 1,
                (candidate.subject, candidate.predicate, candidate.object) in original_gt))
    return instances


def extract_root(kb: KnowledgeBase, qid: str, use_anchors: bool) -> tuple[list[Instance], dict]:
    ctx = kb.root_context(qid)
    if not ctx.wikitext:
        return [], {"root": qid, "error": "no English Wikipedia article in the database"}
    lead = prepare(ctx.wikitext)
    links = page_links(ctx.wikitext)
    lead_targets = {l.target for s in lead.sentences for l in s.links} | \
                   {l.target for f in lead.infobox for _, ls in f.items for l in ls}
    title_to_qid = kb.resolve_titles(lead_targets | {t for _, t in links})
    live = [c for c in ctx.candidates if c.excluded is None]
    neighbour_ids = {c.neighbour for c in live}
    neighbours = {q: ctx.entities[q] for q in neighbour_ids}
    anchors = kb.anchors_for(neighbour_ids) if use_anchors else {}
    totals = kb.anchor_totals({s for v in anchors.values() for s, _ in v}) if use_anchors else {}
    index: AliasIndex = build_alias_index(ctx.root, neighbours, anchors, totals)
    naming = {c.neighbour for c in live if c.predicate in NAMING_PROPERTIES}
    mentions, stats = find_mentions(lead, ctx.entities, neighbour_ids, title_to_qid, links, index, naming)
    original = kb.summaries(qid)
    instances = align(ctx, lead, mentions, original)
    aligned = {(i.subject, i.predicate, i.object) for i in instances}
    report = {
        "root": qid, "label": ctx.root.label, "page_id": ctx.page_id,
        "sentences": len(lead.sentences), "infobox_fields": len(lead.infobox),
        "candidates": len(ctx.candidates), "excluded": dict(Counter(c.excluded for c in ctx.candidates if c.excluded)),
        "neighbours": len(neighbour_ids), "aliases": len(index.surfaces),
        "mentions": dict(Counter(m.source for m in mentions)), "rules": dict(Counter(m.rule for m in mentions)),
        "instances": len(instances), "triples_with_evidence": len(aligned),
        "original_gt": len(original), "original_gt_with_evidence": len(original & aligned),
        "original_gt_without_evidence": sorted(map(list, original - aligned)),
        "stats": {k: v for k, v in asdict(stats).items() if k != "dropped_ambiguous"},
        "dropped_ambiguous": stats.dropped_ambiguous[:50],
        "neighbour_classes": dict(Counter(c for q in neighbour_ids for c in ctx.entities[q].classes)),
        "excluded_examples": [[c.subject, c.predicate, c.object, c.excluded, ctx.entities[c.neighbour].label]
                              for c in ctx.candidates if c.excluded][:40],
    }
    return instances, report


def read_seeds(path: Path) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return [row["qid"] for row in csv.DictReader(f)]


def run_extract(kb: KnowledgeBase, seeds: list[str], out_dir: Path, git_commit: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    anchors_meta = kb.anchors_available()
    use_anchors = bool(anchors_meta and anchors_meta.get("complete") == "True")
    start = time.time()
    totals = Counter()
    with open(out_dir / "instances.jsonl", "w", encoding="utf-8") as inst, \
            open(out_dir / "roots.jsonl", "w", encoding="utf-8") as roots:
        for n, qid in enumerate(seeds, 1):
            t0 = time.time()
            instances, report = extract_root(kb, qid, use_anchors)
            report["seconds"] = round(time.time() - t0, 1)
            for instance in instances:
                inst.write(json.dumps(asdict(instance), ensure_ascii=False) + "\n")
            roots.write(json.dumps(report, ensure_ascii=False) + "\n")
            totals.update(instances=len(instances), roots=1)
            print(f"[{n}/{len(seeds)}] {qid} {report.get('label')}: {len(instances)} instances, "
                  f"{report.get('original_gt_with_evidence')}/{report.get('original_gt')} original GT with evidence, "
                  f"{report['seconds']}s", flush=True)
    manifest = {"relief": relief.__version__, "git_commit": git_commit, "policy": POLICY_VERSION,
                "anchors": anchors_meta, "anchors_used": use_anchors, "seeds": len(seeds),
                "instances": totals["instances"], "seconds": round(time.time() - start),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

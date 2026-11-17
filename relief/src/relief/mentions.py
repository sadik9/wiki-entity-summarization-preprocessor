"""R3: where in the evidence each candidate neighbour is mentioned.

Sources, in order of confidence:
  link      a wikilink whose target (article or redirect title) resolves to the neighbour
  label     the neighbour's Wikidata English label
  title     its article title without the disambiguation suffix ("Jailhouse Rock (film)" -> "Jailhouse Rock")
  redirect  a redirect title, accepted only when it's also used as link text for the neighbour (anchor-confirmed)
  anchor    a link text frequently used for the neighbour across all articles (e.g. "American" -> United States)
  name      naming properties only, matched in the first sentence and the infobox name fields (policy §6)

Unlinked matches are disambiguated (R3d): type cue > one sense per page > unique > commonness > dropped.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

import ahocorasick

from relief.candidates import Entity, strip_disambiguation
from relief.policy import NAMING_PROPERTIES
from relief.text import NAME_FIELDS, Lead, Link

# R3d type cues: words near a mention -> P31 classes they point to (QIDs verified against the 2023 subjects table)
TYPE_CUES = {
    "film": {"Q11424", "Q24862", "Q506240", "Q202866", "Q226730", "Q24869"},
    "song": {"Q7366", "Q134556", "Q105543609"},
    "album": {"Q482994", "Q208569", "Q209939", "Q222910", "Q4176708", "Q169930"},
    "band": {"Q215380", "Q5741069", "Q2088357"},
    "series": {"Q5398426", "Q1259759", "Q21191270"},
    "book": {"Q7725634", "Q8261", "Q571", "Q47461344"},
    "painting": {"Q3305213"},
}
CUE_WORDS = {
    "film": "film", "films": "film", "movie": "film", "movies": "film",
    "song": "song", "songs": "song", "single": "song", "singles": "song", "track": "song",
    "album": "album", "albums": "album", "lp": "album", "ep": "album", "soundtrack": "album",
    "band": "band", "group": "band", "quartet": "band", "trio": "band",
    "series": "series", "sitcom": "series", "miniseries": "series", "show": "series",
    "novel": "book", "novels": "book", "book": "book", "books": "book", "novella": "book", "memoir": "book",
    "painting": "painting", "paintings": "painting", "portrait": "painting",
}
CUE_WINDOW = 4            # words on each side
STOP_SURFACES = {"the", "a", "an", "he", "she", "it", "his", "her", "this", "that", "here", "there", "one", "two",
                 "first", "second", "new", "now", "also", "see", "and", "or", "of", "in", "on", "at", "by"}


@dataclass(frozen=True)
class Mention:
    unit: str             # "s<id>" for a prose sentence, "ib:<template>|<param>" for an infobox field
    start: int            # offsets in the unit's text (for infobox fields: in the item's text)
    end: int
    surface: str
    qid: str
    source: str           # link | label | title | redirect | anchor | name
    rule: str             # link | unique | type_cue | one_sense | commonness | naming
    item: int = 0         # infobox item index (0 for prose)


@dataclass
class MentionStats:
    links: int = 0
    links_unresolved: int = 0
    links_to_non_neighbours: int = 0
    lexical_matches: int = 0
    ambiguous: int = 0                          # matches with more than one candidate neighbour
    dropped_ambiguous: list = field(default_factory=list)
    root_name_skipped: int = 0


@dataclass
class AliasIndex:
    """Surface forms of the root's neighbours, plus what's needed to disambiguate them."""
    surfaces: dict[str, set[tuple[str, str]]]     # alias (as written) -> {(qid, source)}
    root_names: set[str]                           # lower-cased names of the root: never matched (R3c)
    anchor_counts: dict[tuple[str, str], int]      # (surface, qid) -> links with that text pointing there
    automaton: object = None

    def build(self):
        # one key per lower-cased form, keeping every spelling: "guitar" (label) and "Guitar" (title) both survive
        spellings: dict[str, list[str]] = defaultdict(list)
        for alias in self.surfaces:
            spellings[fold(alias)].append(alias)
        automaton = ahocorasick.Automaton()
        for key, aliases in spellings.items():
            automaton.add_word(key, (len(key), tuple(aliases)))
        automaton.make_automaton()
        self.automaton = automaton
        return self


def fold(text: str) -> str:
    """Lower case, character by character, so the length never changes and offsets stay valid."""
    return "".join(c.lower() if len(c.lower()) == 1 else c for c in text)


def root_names(root: Entity) -> set[str]:
    """Every contiguous run of words of the root's label and title, plus its redirect titles (lower-cased)."""
    names = set()
    for name in filter(None, [root.label, root.article_title and strip_disambiguation(root.article_title)]):
        words = name.split()
        names.update(" ".join(words[i:j]).casefold() for i in range(len(words)) for j in range(i + 1, len(words) + 1))
    names.update(strip_disambiguation(t).casefold() for t in root.redirect_titles)
    return names


def build_alias_index(root: Entity, neighbours: dict[str, Entity], anchors: dict[str, list[tuple[str, int]]],
                      anchor_totals: dict[str, int], min_anchor: int = 2, min_share: float = 0.1,
                      max_anchor_surfaces: int = 50) -> AliasIndex:
    """anchors: qid -> [(surface, n)] for the neighbours; anchor_totals: surface -> links with that text overall."""
    surfaces: dict[str, set[tuple[str, str]]] = defaultdict(set)
    counts: dict[tuple[str, str], int] = {}
    for qid, entity in neighbours.items():
        confirmed = {s: n for s, n in anchors.get(qid, [])}
        for surface, n in confirmed.items():
            counts[(surface, qid)] = n
        candidates = [(entity.label, "label")]
        if entity.article_title:
            candidates.append((strip_disambiguation(entity.article_title), "title"))
        candidates += [(strip_disambiguation(t), "redirect") for t in entity.redirect_titles
                       if strip_disambiguation(t) in confirmed]
        top = sorted(confirmed.items(), key=lambda x: -x[1])[:max_anchor_surfaces]
        candidates += [(s, "anchor") for s, n in top
                       if n >= min_anchor and n / max(anchor_totals.get(s, n), 1) >= min_share]
        for surface, source in candidates:
            if surface and len(surface) >= 3 and surface.casefold() not in STOP_SURFACES and re.search(r"[^\W\d]", surface):
                surfaces[surface].add((qid, source))
    return AliasIndex(dict(surfaces), root_names(root), counts).build()


def _boundary(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else " "
    after = text[end] if end < len(text) else " "
    return not before.isalnum() and not after.isalnum()


def _case_ok(alias: str, found: str) -> bool:
    """Capitalised aliases (proper names) must match exactly; lower-case ones (common nouns) in any case."""
    return found == alias if any(c.isupper() for c in alias) else True


def lexical_matches(text: str, index: AliasIndex, taken: list[tuple[int, int]]) -> list[tuple[int, int, tuple]]:
    """Longest non-overlapping alias matches outside the already-linked spans: (start, end, matching aliases)."""
    found = []
    for end_index, (key_length, aliases) in index.automaton.iter(fold(text)):
        end = end_index + 1
        start = end - key_length
        if start < 0 or not _boundary(text, start, end):
            continue
        accepted = tuple(a for a in aliases if _case_ok(a, text[start:end]))
        if accepted:
            found.append((start, end, accepted))
    found.sort(key=lambda m: (-(m[1] - m[0]), m[0]))
    chosen, occupied = [], list(taken)
    for start, end, aliases in found:
        if all(end <= a or start >= b for a, b in occupied):
            chosen.append((start, end, aliases))
            occupied.append((start, end))
    return sorted(chosen)


def _cue_classes(text: str, start: int, end: int) -> set[str]:
    before = re.findall(r"\w+", text[:start].casefold())[-CUE_WINDOW:]
    after = re.findall(r"\w+", text[end:].casefold())[:CUE_WINDOW]
    classes = set()
    for word in before + after:
        if word in CUE_WORDS:
            classes |= TYPE_CUES[CUE_WORDS[word]]
    return classes


def disambiguate(surface: str, candidates: set[str], text: str, start: int, end: int,
                 entities: dict[str, Entity], linked_on_page: dict[str, set[str]],
                 index: AliasIndex) -> tuple[str | None, str]:
    if len(candidates) == 1:
        return next(iter(candidates)), "unique"
    cue = _cue_classes(text, start, end)
    if cue:
        typed = {q for q in candidates if entities[q].classes & cue}
        if len(typed) == 1:
            return next(iter(typed)), "type_cue"
    by_surface = linked_on_page.get(surface, set()) & candidates
    if len(by_surface) == 1:
        return next(iter(by_surface)), "one_sense"
    linked_anywhere = linked_on_page.get("", set()) & candidates
    if len(linked_anywhere) == 1:
        return next(iter(linked_anywhere)), "one_sense"
    counts = {q: index.anchor_counts.get((surface, q), 0) for q in candidates}
    total = sum(counts.values())
    if total >= 2:
        best = max(counts, key=counts.get)
        if counts[best] / total >= 0.7:
            return best, "commonness"
    return None, "ambiguous"


def find_mentions(lead: Lead, entities: dict[str, Entity], neighbour_ids: set[str], title_to_qid: dict[str, str],
                  page_links: list[tuple[str, str]], index: AliasIndex,
                  naming_targets: set[str]) -> tuple[list[Mention], MentionStats]:
    """All mentions of neighbours in the prose sentences and infobox fields."""
    stats = MentionStats()
    linked_on_page: dict[str, set[str]] = defaultdict(set)    # surface -> linked qids; "" -> every linked qid
    for anchor, target in page_links:
        qid = title_to_qid.get(target)
        if qid in neighbour_ids:
            linked_on_page[anchor].add(qid)
            linked_on_page[""].add(qid)

    mentions: list[Mention] = []

    def scan(unit: str, text: str, links: list[Link], item: int = 0):
        taken = []
        for link in links:
            stats.links += 1
            qid = title_to_qid.get(link.target)
            if qid is None:
                stats.links_unresolved += 1
            elif qid not in neighbour_ids:
                stats.links_to_non_neighbours += 1
            else:
                mentions.append(Mention(unit, link.start, link.end, link.anchor, qid, "link", "link", item))
            taken.append((link.start, link.end))
        for start, end, aliases in lexical_matches(text, index, taken):
            surface = text[start:end]
            if surface.casefold() in index.root_names:
                stats.root_name_skipped += 1
                continue
            stats.lexical_matches += 1
            options = set().union(*(index.surfaces[a] for a in aliases))
            candidates = {q for q, _ in options}
            if len(candidates) > 1:
                stats.ambiguous += 1
            qid, rule = disambiguate(surface, candidates, text, start, end, entities, linked_on_page, index)
            if qid is None:
                stats.dropped_ambiguous.append((unit, surface, sorted(candidates)))
                continue
            source = min((s for q, s in options if q == qid), key=["label", "title", "redirect", "anchor"].index)
            mentions.append(Mention(unit, start, end, surface, qid, source, rule, item))

    for sentence in lead.sentences:
        scan(f"s{sentence.id}", sentence.text, sentence.links)
    for field_ in lead.infobox:
        for item, (text, links) in enumerate(field_.items):
            scan(f"ib:{field_.template}|{field_.param}", text, links, item)

    # R3f: naming properties, in the first sentence and the infobox name fields, root-name exclusion not applied
    name_units = []
    if lead.sentences:
        name_units.append(("s0", lead.sentences[0].text, 0))
    for field_ in lead.infobox:
        if field_.param in NAME_FIELDS:
            name_units += [(f"ib:{field_.template}|{field_.param}", text, i) for i, (text, _) in enumerate(field_.items)]
    for qid in naming_targets:
        label = entities[qid].label
        if not label:
            continue
        for unit, text, item in name_units:
            for match in re.finditer(r"(?<!\w)" + re.escape(label) + r"(?!\w)", text):
                mentions.append(Mention(unit, match.start(), match.end(), label, qid, "name", "naming", item))
    return mentions, stats

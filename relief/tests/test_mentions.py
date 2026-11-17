from relief.candidates import Candidate, Entity, RootContext
from relief.align import align
from relief.mentions import build_alias_index, find_mentions, fold, lexical_matches, root_names
from relief.text import prepare

ROOT = Entity("Q303", "Elvis Presley", None, {"Q5"}, "Elvis_Presley", ["Elvis", "Elvis_Aaron_Presley"])
NEIGHBOURS = {
    "Q6607": Entity("Q6607", "guitar", None, set(), "Guitar"),
    "Q3415083": Entity("Q3415083", "RCA Victor", None, set(), None),
    "Q536342": Entity("Q536342", "Jailhouse Rock", None, {"Q11424"}, "Jailhouse_Rock_(film)"),
    "Q739731": Entity("Q739731", "Jailhouse Rock", None, {"Q134556"}, "Jailhouse_Rock_(song)"),
    "Q1174817": Entity("Q1174817", "Elvis", None, {"Q12308941"}, None),             # given name
    "Q30": Entity("Q30", "United States", None, {"Q6256"}, "United_States"),
}
ENTITIES = {**NEIGHBOURS, "Q303": ROOT}


def index(anchors=None, totals=None):
    return build_alias_index(ROOT, NEIGHBOURS, anchors or {}, totals or {})


def surfaces(text, idx):
    return [text[s:e] for s, e, _ in lexical_matches(text, idx, [])]


def test_label_and_title_spellings_both_survive():
    # regression: "guitar" (label) and "Guitar" (title) share a lower-case key; neither may replace the other
    idx = index()
    assert surfaces("Vocals, guitar and piano", idx) == ["guitar"]
    assert surfaces("Guitar was his instrument", idx) == ["Guitar"]


def test_capitalised_aliases_match_exactly_and_on_word_boundaries():
    idx = index()
    assert surfaces("signed with RCA Victor in 1955", idx) == ["RCA Victor"]
    assert surfaces("signed with rca victor", idx) == []
    assert surfaces("guitarist", idx) == []


def test_longest_match_wins_and_links_are_not_rematched():
    idx = build_alias_index(ROOT, {**NEIGHBOURS, "Q1": Entity("Q1", "Jailhouse", None, set(), None)}, {}, {})
    assert surfaces("the film Jailhouse Rock", idx) == ["Jailhouse Rock"]
    assert lexical_matches("Jailhouse Rock", idx, [(0, 14)]) == []


def test_root_names_are_every_word_run_of_label_and_title_plus_redirects():
    names = root_names(ROOT)
    assert {"elvis", "presley", "elvis presley", "elvis aaron presley"} <= names


def test_fold_keeps_the_length():
    assert len(fold("Straße İstanbul")) == len("Straße İstanbul")


def mentions_for(wikitext, page_links=(), anchors=None):
    lead = prepare(wikitext)
    title_to_qid = {"Jailhouse_Rock_(film)": "Q536342", "Jailhouse_Rock_(song)": "Q739731", "RCA_Victor": "Q3415083"}
    found, stats = find_mentions(lead, ENTITIES, set(NEIGHBOURS), title_to_qid, list(page_links),
                                 index(anchors), naming_targets={"Q1174817"})
    return lead, found, stats


def by_surface(found):
    return {(m.surface, m.qid, m.rule) for m in found}


def test_type_cue_picks_the_song():
    _, found, _ = mentions_for("He released the single Jailhouse Rock.")
    assert ("Jailhouse Rock", "Q739731", "type_cue") in by_surface(found)


def test_one_sense_per_page_follows_the_link():
    _, found, _ = mentions_for("He starred in Jailhouse Rock.",
                               page_links=[("Jailhouse Rock", "Jailhouse_Rock_(film)")])
    assert ("Jailhouse Rock", "Q536342", "one_sense") in by_surface(found)


def test_ambiguous_mentions_are_dropped_not_guessed():
    _, found, stats = mentions_for("Jailhouse Rock was big.")
    assert not any(m.surface == "Jailhouse Rock" for m in found)
    assert stats.dropped_ambiguous == [("s0", "Jailhouse Rock", ["Q536342", "Q739731"])]


def test_commonness_decides_when_one_sense_dominates():
    anchors = {"Q536342": [("Jailhouse Rock", 90)], "Q739731": [("Jailhouse Rock", 10)]}
    _, found, _ = mentions_for("Jailhouse Rock was big.", anchors=anchors)
    assert ("Jailhouse Rock", "Q536342", "commonness") in by_surface(found)


def test_root_names_are_skipped_but_naming_edges_use_the_first_sentence():
    lead, found, stats = mentions_for("'''Elvis Aaron Presley''' was an American singer. Elvis was famous.")
    lexical = [m for m in found if m.rule != "naming"]
    assert not any(m.surface == "Elvis" for m in lexical) and stats.root_name_skipped >= 1
    naming = [m for m in found if m.rule == "naming"]
    assert {(m.unit, m.surface) for m in naming} == {("s0", "Elvis")}


def test_alignment_builds_one_instance_per_edge_and_evidence_unit():
    lead, found, _ = mentions_for("He played [[guitar]] and guitar again. He signed with [[RCA Victor]].")
    ctx = RootContext(ROOT, 1, "", [
        Candidate("Q303", "P1303", "Q6607", "Q6607", True, None),
        Candidate("Q303", "P264", "Q3415083", "Q3415083", True, None),
        Candidate("Q303", "P735", "Q1174817", "Q1174817", True, None),
        Candidate("Q30", "P1", "Q303", "Q30", False, "list_like"),
    ], ENTITIES, {})
    instances = align(ctx, lead, found, original_gt={("Q303", "P264", "Q3415083")})
    assert sorted((i.predicate, i.unit, i.mention_source) for i in instances) == [
        ("P1303", "s0", "label"), ("P264", "s1", "link")]
    assert next(i for i in instances if i.predicate == "P264").in_original_gt
    assert next(i for i in instances if i.predicate == "P264").context == "He played guitar and guitar again."

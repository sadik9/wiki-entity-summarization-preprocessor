from relief.anchors import page_anchor_counts
from relief.policy import exclusion_reason
from relief.seeds import allocate, select_pilot


def test_anchor_counts_keep_the_visible_text():
    counts = page_anchor_counts(
        "[[Tupelo, Mississippi|''Tupelo'']] and [[guitar]]s, [[Graceland]] and [[Graceland]], "
        "[[File:x.jpg|thumb|caption]], [[wikt:legend|legend]], [[Elvis Presley#Career|his career]]")
    assert counts == {("Tupelo,_Mississippi", "Tupelo"): 1, ("Guitar", "guitar"): 1, ("Graceland", "Graceland"): 2,
                      ("Elvis_Presley", "his career"): 1}


def test_allocation_gives_every_category_a_seed_and_respects_the_total():
    share = allocate({"actor": 411, "film": 89}, 12)
    assert sum(share.values()) == 12 and share["film"] >= 1 and share["actor"] > share["film"]
    assert sum(allocate({c: 10 for c in "abcdefghij"}, 13).values()) == 13


def test_pilot_selection_is_reproducible_and_unique():
    sets = {"A": [{"qid": f"Q{i}", "name": str(i), "category": "x" if i % 2 else "y"} for i in range(40)],
            "B": [{"qid": f"Q{i}", "name": str(i), "category": "z"} for i in range(20, 60)]}
    first = select_pilot(sets, {"A": 6, "B": 6})
    assert first == select_pilot(sets, {"A": 6, "B": 6})
    assert len({r["qid"] for r in first}) == 12


def test_policy_exclusions():
    assert exclusion_reason("Elvis Presley", "P1269", "death of Elvis Presley", set(), False) == "aspect_article"
    assert exclusion_reason("Elvis Presley", "P19", "Tupelo", {"Q515"}, False) is None
    assert exclusion_reason("Elvis Presley", "P921", "x", {"Q1371849"}, False) == "list_like"
    assert exclusion_reason("Elvis Presley", "P971", "Category:x", {"Q4167836"}, False) == "wikimedia_internal"
    assert exclusion_reason("Elvis Presley", "P26", "Q303", set(), True) == "self_loop"


def test_repair_title_undoes_utf8_read_as_latin1_and_leaves_good_titles_alone():
    from relief.anchors import repair_title
    assert repair_title("AssociaÃ§Ã£o_Desportiva_SÃ£o_Caetano") == "Associação_Desportiva_São_Caetano"
    assert repair_title("Danuta_WaÅ\x82Ä\x99sa") == "Danuta_Wałęsa"
    assert repair_title("AD_São_Caetano") == "AD_São_Caetano"
    assert repair_title("Elvis_Presley") == "Elvis_Presley"


def test_gold_allocation_keeps_rare_strata_and_the_total():
    from relief.gold import allocate
    share = allocate({"big": 2000, "mid": 500, "rare": 12}, 1000, 30)
    assert share["rare"] == 12 and sum(share.values()) == 1000 and share["big"] > share["mid"] >= 30

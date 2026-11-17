from pathlib import Path

import pytest

from relief.text import normalize_title, page_links, prepare, render

FIXTURES = Path(__file__).parent / "fixtures"


def lead(name):
    return prepare((FIXTURES / f"{name}.lead.wiki").read_text(encoding="utf-8"))


def field(lead_, param, template=None):
    return next(f for f in lead_.infobox if f.param == param and (template is None or f.template == template))


@pytest.mark.parametrize("raw, expected", [
    ("Tupelo, Mississippi", "Tupelo,_Mississippi"),
    ("rock and roll", "Rock_and_roll"),
    ("Elvis Presley#Early life", "Elvis_Presley"),
    (":Category:Rock music", None),
    ("File:Elvis.jpg", None),
    ("wikt:legend", None),
    ("Star Wars: A New Hope", "Star_Wars:_A_New_Hope"),
])
def test_normalize_title(raw, expected):
    assert normalize_title(raw) == expected


def test_links_keep_exact_offsets():
    text, links = render("He was born in [[Tupelo, Mississippi|Tupelo]] and moved to [[Memphis, Tennessee]].")
    assert text == "He was born in Tupelo and moved to Memphis, Tennessee."
    assert [(text[l.start:l.end], l.target) for l in links] == [
        ("Tupelo", "Tupelo,_Mississippi"), ("Memphis, Tennessee", "Memphis,_Tennessee")]


def test_citations_comments_and_pronunciation_are_dropped():
    text, links = render("'''Bowie''' ({{IPAc-en|ˈ|b|oʊ|i}})<ref>{{cite web|title=x|publisher=[[BBC]]}}</ref> "
                         "was an <!-- note -->English [[singer]].")
    assert text == "Bowie was an English singer."
    assert [l.target for l in links] == ["Singer"]


def test_file_links_and_their_captions_are_dropped():
    text, links = render("[[File:x.jpg|thumb|A [[guitar]] picture]]He played.")
    assert text == "He played." and links == []


def test_elvis_prose():
    elvis = lead("Elvis_Presley")
    assert elvis.sentences[0].text.startswith("Elvis Aaron Presley (January 8, 1935 – August 16, 1977)")
    assert elvis.sentences[0].text.endswith("was an American singer and actor.")
    # every link span points at its anchor text
    for sentence in elvis.sentences:
        for link in sentence.links:
            assert sentence.text[link.start:link.end] == link.anchor


def test_elvis_infobox_fields_items_and_links():
    elvis = lead("Elvis_Presley")
    assert [t for t, _ in field(elvis, "instruments").items] == ["Vocals", "guitar", "piano"]
    assert [l.target for _, ls in field(elvis, "spouse").items for l in ls] == ["Priscilla_Presley"]
    assert field(elvis, "birth_place").items[0][1][0].target == "Tupelo,_Mississippi"
    assert field(elvis, "birth_name").text == "Elvis Aron Presley"
    # the nested military infobox is read, its display-only fields are not
    assert field(elvis, "branch", "infobox military person").items[0][1][0].target == "United_States_Army"
    assert not any(f.param in {"embed_title", "branch_label"} for f in elvis.infobox)


def test_bowie_nested_module_infobox_and_marriage_templates():
    bowie = lead("David_Bowie")
    assert [l.target for _, ls in field(bowie, "spouse").items for l in ls] == ["Angie_Bowie", "Iman_(model)"]
    assert [t for t, _ in field(bowie, "instruments", "infobox musical artist").items][:2] == ["Vocals", "guitar"]
    assert bowie.sentences[0].text == ("David Robert Jones (8 January 1947 – 10 January 2016), known professionally "
                                       "as David Bowie, was an English singer-songwriter and actor.")


def test_infobox_is_not_part_of_the_prose():
    for name in ["Elvis_Presley", "David_Bowie", "Alfred_Hitchcock", "Oprah_Winfrey"]:
        text = " ".join(s.text for s in lead(name).sentences)
        assert "birth_place" not in text and "{{" not in text and "|" not in text


def test_page_links_cover_the_whole_page():
    links = page_links("Intro [[Graceland]].\n== Life ==\nLater [[Jailhouse Rock (film)|Jailhouse Rock]].")
    assert links == [("Graceland", "Graceland"), ("Jailhouse Rock", "Jailhouse_Rock_(film)")]


def test_infobox_templates_keep_their_links_but_dates_and_notes_do_not():
    text, links = render("{{Medal|Gold|[[2013 World Championships in Athletics|2013 Moscow]]|[[Hammer throw]]}}",
                         infobox=True)
    assert text == "Gold 2013 Moscow Hammer throw"
    assert [l.target for l in links] == ["2013_World_Championships_in_Athletics", "Hammer_throw"]
    text, links = render("{{birth date and age|1985|8|8}} in [[Rawicz]]{{efn|see [[Note]]}}", infobox=True)
    assert text == "in Rawicz" and [l.target for l in links] == ["Rawicz"]
    # in prose, unknown templates stay dropped
    assert render("{{Medal|Gold|[[A]]}} text")[0] == "text"


def test_flag_templates_link_their_country():
    text, links = render("{{flagu|Great Britain}}", infobox=True)
    assert text == "Great Britain" and links[0].target == "Great_Britain"

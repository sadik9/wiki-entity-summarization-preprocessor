"""R2: turn an article's section 0 into evidence units that keep their links.

* prose: the lead text before the first heading, as clean sentences; every wikilink keeps its character span
* infobox: every field of every infobox in section 0 (nested ones included), split into list items, each with links

Only these two parts are evidence (ground-truth policy §3). Templates are dropped unless they carry visible text
(KEEP_TEXT); citations, comments, tables, files and hatnotes are dropped.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import mwparserfromhell as mwp
from mwparserfromhell.nodes import Comment, ExternalLink, Heading, HTMLEntity, Tag, Template, Text, Wikilink

# private-use characters mark link boundaries while the text is cleaned; they never occur in Wikipedia text
_OPEN, _MID, _CLOSE = "", "", ""
_MARKER = re.compile(f"{_OPEN}(\\d+){_MID}|{_CLOSE}")

NON_ARTICLE_PREFIXES = {
    "file", "image", "media", "category", "template", "help", "portal", "special", "draft", "wikipedia", "wp",
    "user", "talk", "module", "mediawiki", "timedtext", "book", "education program", "wikt", "wiktionary", "s",
    "wikisource", "q", "wikiquote", "commons", "c", "n", "wikinews", "b", "wikibooks", "v", "wikiversity", "voy",
    "species", "d", "wikidata", "meta", "m", "mw", "phab", "w", "doi", "imdb",
}
DROP_LINK_PREFIXES = {"file", "image", "media", "category"}      # the whole link (and its caption) is not text

# templates whose output is visible text: name -> how to render it
LIST_TEMPLATES = {"hlist", "flatlist", "flat list", "plainlist", "plain list", "ubl", "unbulleted list",
                  "bulleted list", "bulleted", "indented plainlist", "cslist", "collapsible list", "plainlist/start"}
KEEP_TEXT = {
    "nowrap": 1, "nobr": 1, "nobreak": 1, "small": 1, "smaller": 1, "big": 1, "noitalic": 1, "nobold": 1,
    "sic": 1, "abbr": 1, "visible anchor": 1, "vanchor": 1, "marriage": 1, "married": 1, "transl": -1,
    "lang": 2, "langx": 2, "script": -1, "linktext": 1, "nbsp": " ", "spnd": " – ", "snd": " – ",
    "spaced ndash": " – ", "ndash": "–", "mdash": "—", "en dash": "–", "em dash": "—",
}
FLAG_TEMPLATES = {"flag", "flagu", "flagcountry", "flag country"}
# never visible evidence, even inside an infobox: citations and notes, dates (literals, not graph edges), images
NEVER_TEXT = {"efn", "efn-ua", "efn-lr", "refn", "sfn", "sfnp", "sfnm", "r", "rp", "ref", "notetag", "citation",
              "harvnb", "harvp", "harv", "coord", "flagicon", "flagdeco", "url", "official website", "small image",
              "nbsp", "hidden", "tooltip", "abbr link"}


def _never_text(name: str) -> bool:
    return name in NEVER_TEXT or name.startswith("cite") or "date" in name or name.endswith(" age") or         name.startswith("infobox") or name.startswith("sfn")


INFOBOX_SKIP_FIELDS = {"image", "image_size", "imagesize", "image_upright", "upright", "alt", "caption", "signature",
                       "signature_alt", "signature_size", "website", "url", "module", "embed", "child", "landscape",
                       "background", "logo", "logo_size", "logo_alt", "logo_caption", "honorific_prefix",
                       "honorific_suffix", "pronunciation", "footnotes", "native_name_lang", "image_caption"}
NAME_FIELDS = {"name", "birth_name", "birthname", "birth name", "full_name", "fullname", "native_name",
               "other_names", "othername", "also_known_as", "nickname", "pseudonym"}


@dataclass(frozen=True)
class Link:
    start: int          # character offsets in the text that contains the link
    end: int
    target: str         # normalised Wikipedia title (underscores, first letter upper case), e.g. "Tupelo,_Mississippi"
    anchor: str         # the visible text


@dataclass
class Sentence:
    id: int
    text: str
    links: list[Link] = field(default_factory=list)


@dataclass
class InfoboxField:
    template: str       # e.g. "infobox person"
    param: str          # e.g. "birth_place"
    items: list[tuple[str, list[Link]]]     # (item text, links in that item)

    @property
    def text(self) -> str:
        return "; ".join(text for text, _ in self.items)


@dataclass
class Lead:
    sentences: list[Sentence]
    infobox: list[InfoboxField]


def normalize_title(title: str) -> str | None:
    """Wikipedia link target -> title as stored in the mapping table, or None for non-article links."""
    title = title.split("#", 1)[0].strip().lstrip(":").strip()
    if not title:
        return None
    if ":" in title and title.split(":", 1)[0].strip().lower() in NON_ARTICLE_PREFIXES:
        return None
    title = re.sub(r"[\s_]+", "_", title).strip("_")
    return title[0].upper() + title[1:] if title else None


def _template_name(template: Template) -> str:
    return re.sub(r"[\s_]+", " ", str(template.name)).strip().lower()


def _positional(template: Template) -> list:
    return [p for p in template.params if not p.showkey]


class _Renderer:
    """Renders wikicode to text with link markers; links are collected by id."""

    def __init__(self, infobox: bool = False):
        self.links: list[tuple[str, str]] = []     # (target, anchor) by id
        self.infobox = infobox                      # inside an infobox field: unknown templates keep their text

    def render(self, code) -> str:
        return "".join(self._node(node) for node in code.nodes)

    def _node(self, node) -> str:
        if isinstance(node, Text):
            return str(node.value)
        if isinstance(node, HTMLEntity):
            return node.normalize()
        if isinstance(node, Comment) or isinstance(node, Heading):
            return ""
        if isinstance(node, Wikilink):
            return self._wikilink(node)
        if isinstance(node, ExternalLink):
            return self.render(node.title) if node.title else ""
        if isinstance(node, Tag):
            return self._tag(node)
        if isinstance(node, Template):
            return self._template(node)
        return ""

    def _wikilink(self, link: Wikilink) -> str:
        raw = str(link.title).strip()
        prefix = raw.lstrip(":").split(":", 1)[0].strip().lower() if ":" in raw else ""
        if prefix in DROP_LINK_PREFIXES and not raw.startswith(":"):
            return ""
        anchor = self.render(link.text) if link.text is not None else raw.split("#", 1)[0].lstrip(":")
        target = normalize_title(raw)
        if target is None or not anchor.strip():
            return anchor
        self.links.append((target, anchor))
        return f"{_OPEN}{len(self.links) - 1}{_MID}{anchor}{_CLOSE}"

    def _tag(self, tag: Tag) -> str:
        name = str(tag.tag).strip().lower()
        if name in {"ref", "table", "gallery", "math", "timeline", "graph", "score", "templatestyles", "imagemap"}:
            return ""
        if name == "br":
            return "\n"
        if name in {"li", "dd", "dt"}:
            return "\n" + (self.render(tag.contents) if tag.contents else "")
        return self.render(tag.contents) if tag.contents is not None else ""

    def _template(self, template: Template) -> str:
        name = _template_name(template)
        if name in LIST_TEMPLATES:
            return ", ".join(t for t in (self.render(item).strip() for item in _list_items(template)) if t)
        if name.startswith("lang-"):
            params = _positional(template)
            return self.render(params[0].value) if params else ""
        if name in {"ill", "interlanguage link", "illm"}:
            params = _positional(template)
            if not params:
                return ""
            target = normalize_title(str(params[0].value).strip())
            anchor = str(template.get("lt").value).strip() if template.has("lt") else str(params[0].value).strip()
            if target is None:
                return anchor
            self.links.append((target, anchor))
            return f"{_OPEN}{len(self.links) - 1}{_MID}{anchor}{_CLOSE}"
        if name in FLAG_TEMPLATES:
            params = _positional(template)
            if not params:
                return ""
            country = str(params[0].value).strip()
            target = normalize_title(country)
            if target is None:
                return country
            self.links.append((target, country))
            return f"{_OPEN}{len(self.links) - 1}{_MID}{country}{_CLOSE}"
        if name in {"convert", "cvt"}:
            params = _positional(template)
            return " ".join(str(p.value).strip() for p in params[:2])
        if name in {"circa", "c."}:
            params = _positional(template)
            return "c. " + (self.render(params[0].value) if params else "")
        rule = KEEP_TEXT.get(name)
        if rule is None:
            if self.infobox and not _never_text(name):
                # e.g. {{Medal|Gold|[[2013 World Championships in Athletics|2013 Moscow]]|[[... hammer throw|Hammer throw]]}}
                parts = (self.render(p.value).strip() for p in _positional(template))
                return " ".join(p for p in parts if p)
            return ""
        if isinstance(rule, str):
            return rule
        params = _positional(template)
        if not params:
            return ""
        index = len(params) - 1 if rule == -1 else min(rule, len(params)) - 1
        return self.render(params[index].value)


def _list_items(template: Template) -> list:
    """Items of a list template: positional parameters, or the `*` lines of a flatlist/plainlist body."""
    items = []
    for param in _positional(template):
        value = param.value
        text = str(value)
        if "\n*" in "\n" + text.lstrip():
            for line in re.split(r"\n\s*\*+", "\n" + text):
                if line.strip():
                    items.append(mwp.parse(line))
        else:
            items.append(value)
    return items


def _finish(marked: str, links: list[tuple[str, str]]) -> tuple[str, list[Link]]:
    """Strip the link markers and return the plain text with link offsets."""
    out, result, pos, open_stack = [], [], 0, []
    length = 0
    for match in _MARKER.finditer(marked):
        chunk = marked[pos:match.start()]
        out.append(chunk)
        length += len(chunk)
        if match.group(1) is not None:
            open_stack.append((int(match.group(1)), length))
        elif open_stack:
            link_id, start = open_stack.pop()
            target, _ = links[link_id]
            result.append(Link(start, length, target, "".join(out)[start:length]))
        pos = match.end()
    out.append(marked[pos:])
    return "".join(out), sorted(result, key=lambda l: l.start)


def _clean(marked: str, keep_newlines: bool) -> str:
    """Whitespace and punctuation clean-up that never touches the link markers."""
    marked = marked.replace(" ", " ")
    marked = re.sub(r"'{2,}", "", marked)                               # left-over bold/italic markup
    marked = re.sub(r"\(\s*[,;:]*\s*\)", "", marked)                    # "()" left by dropped templates
    marked = re.sub(r"\(\s*[,;]\s*", "(", marked)
    marked = re.sub(r"[ \t]+", " ", marked)
    if keep_newlines:
        marked = re.sub(r" *\n[\n ]*", "\n", marked)
    else:
        marked = re.sub(r"\s+", " ", marked)
    marked = re.sub(r" +([,.;:!?)])", r"\1", marked)
    return marked.strip()


def render(code, keep_newlines: bool = False, infobox: bool = False) -> tuple[str, list[Link]]:
    renderer = _Renderer(infobox)
    marked = renderer.render(code if hasattr(code, "nodes") else mwp.parse(code))
    return _finish(_clean(marked, keep_newlines), renderer.links)


def section0(wikitext: str):
    """Everything before the first heading, as parsed wikicode."""
    code = mwp.parse(wikitext)
    nodes = []
    for node in code.nodes:
        if isinstance(node, Heading):
            break
        nodes.append(node)
    return mwp.wikicode.Wikicode(nodes)


def _infoboxes(code) -> list[Template]:
    found = []
    for template in code.filter_templates(recursive=False):
        if _template_name(template).startswith("infobox"):
            found.append(template)
    return found


def _infobox_fields(template: Template) -> list[InfoboxField]:
    fields = []
    name = _template_name(template)
    for param in template.params:
        key = re.sub(r"\s+", "_", str(param.name).strip().lower())
        nested = [t for t in param.value.filter_templates(recursive=False) if _template_name(t).startswith("infobox")]
        for child in nested:                                   # e.g. module = {{Infobox musical artist | embed=yes ...}}
            fields.extend(_infobox_fields(child))
        # display-only fields: e.g. embed_title = "Military service", branch_label = "Branch"
        layout = key == "embed_title" or (key.endswith("_label") and key != "label")
        if key in INFOBOX_SKIP_FIELDS or layout or nested or not param.showkey:
            continue
        items = []
        for item_code in _field_items(param.value):
            text, links = render(item_code, infobox=True)
            if text:
                items.append((text, links))
        if items:
            fields.append(InfoboxField(name, key, items))
    return fields


def _field_items(value) -> list:
    """Split a field value into items: list templates, <br>-separated or `*`-bulleted entries, else one item."""
    top = [n for n in value.nodes if not (isinstance(n, Text) and not str(n).strip()) and not isinstance(n, Comment)]
    if len(top) == 1 and isinstance(top[0], Template) and _template_name(top[0]) in LIST_TEMPLATES:
        items = []
        for item in _list_items(top[0]):
            items.extend(_field_items(item) if hasattr(item, "nodes") else [item])
        return items
    marked_parts, current = [], []
    for node in value.nodes:
        is_break = isinstance(node, Tag) and str(node.tag).strip().lower() == "br"
        if is_break:
            marked_parts.append(current)
            current = []
            continue
        if isinstance(node, Text) and "\n*" in "\n" + str(node.value):
            pieces = re.split(r"\n\s*\*+", str(node.value))
            current.append(Text(pieces[0]))
            for piece in pieces[1:]:
                marked_parts.append(current)
                current = [Text(piece)]
            continue
        current.append(node)
    marked_parts.append(current)
    return [mwp.wikicode.Wikicode(part) for part in marked_parts if part]


@lru_cache(maxsize=1)
def _segmenter():
    import pysbd

    return pysbd.Segmenter(language="en", clean=False, char_span=True)


def split_sentences(text: str, links: list[Link]) -> list[Sentence]:
    """Paragraphs (newlines) first, then pysbd within each paragraph; links are re-based onto their sentence."""
    sentences, offset = [], 0
    for paragraph in text.split("\n"):
        if paragraph.strip():
            for span in _segmenter().segment(paragraph):
                start, end = offset + span.start, offset + span.end
                raw = text[start:end]
                stripped = raw.strip()
                if not stripped:
                    continue
                lead = len(raw) - len(raw.lstrip())
                s0, s1 = start + lead, start + lead + len(stripped)
                inside = [Link(l.start - s0, l.end - s0, l.target, l.anchor) for l in links
                          if l.start >= s0 and l.end <= s1]
                sentences.append(Sentence(len(sentences), stripped, inside))
        offset += len(paragraph) + 1
    return sentences


def prepare(wikitext: str) -> Lead:
    """Section 0 of an article -> prose sentences + infobox fields, all with their links."""
    code = section0(wikitext)
    infobox = [f for box in _infoboxes(code) for f in _infobox_fields(box)]
    for box in _infoboxes(code):
        code.remove(box)
    text, links = render(code, keep_newlines=True)
    return Lead(split_sentences(text, links), infobox)


def page_links(wikitext: str) -> list[tuple[str, str]]:
    """(anchor, target) of every article link on the whole page, for one-sense-per-discourse (R3d)."""
    renderer = _Renderer()
    renderer.render(mwp.parse(wikitext))
    return [(re.sub(r"\s+", " ", re.sub(_MARKER, "", anchor)).strip(), target)
            for target, anchor in renderer.links]

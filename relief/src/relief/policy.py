"""Constants of the ground-truth policy (relief/docs/ground-truth-policy.md). Versioned with every run."""

POLICY_VERSION = "2026-11-18"

# §5.1 Wikimedia-internal entities (by P31)
WIKIMEDIA_INTERNAL = {
    "Q13406463",   # Wikimedia list article
    "Q4167410",    # Wikimedia disambiguation page
    "Q22808320",   # Wikimedia human name disambiguation page
    "Q4167836",    # Wikimedia category
    "Q11266439",   # Wikimedia template
    "Q15407973",   # Wikimedia disambiguation category
    "Q14204246",   # Wikimedia project page
    "Q17442446",   # Wikimedia internal item
    "Q17379835",   # Wikimedia page outside the main knowledge tree
}
# §5.2 list-like works about the root (by P31)
LIST_LIKE = {
    "Q1371849",                          # filmography
    "Q273057", "Q4162149",               # discography
    "Q1631107", "Q134995", "Q4086340",   # bibliography
    "Q2662841", "Q17438413",             # videography
    "Q12139612",                         # list
}
# §5.1 also: any class whose English label starts with one of these (Wikidata keeps adding specific list classes,
# e.g. "Wikimedia artist discography", "Wikimedia list of songs by performer")
INTERNAL_LABEL_PREFIXES = ("Wikimedia ", "Wikipedia ")
# §5.3 aspect sub-articles: neighbour label contains the root label and is linked through these properties
ASPECT_PROPERTIES = {"P1269", "P921"}    # facet of, main subject

# §6 item-valued naming properties
NAMING_PROPERTIES = {"P735", "P734", "P1950", "P9139", "P6978", "P8500", "P5056", "P2838"}


def exclusion_reason(root_label: str, predicate: str, neighbour_label: str | None, neighbour_classes: set[str],
                     is_self_loop: bool, internal_classes: set[str] = frozenset()) -> str | None:
    """Why a candidate edge is excluded by policy §5, or None. internal_classes: classes matched by label prefix."""
    if is_self_loop:
        return "self_loop"
    if neighbour_classes & (WIKIMEDIA_INTERNAL | internal_classes):
        return "wikimedia_internal"
    if neighbour_classes & LIST_LIKE:
        return "list_like"
    if (predicate in ASPECT_PROPERTIES and neighbour_label and root_label
            and root_label.casefold() in neighbour_label.casefold()):
        return "aspect_article"
    return None

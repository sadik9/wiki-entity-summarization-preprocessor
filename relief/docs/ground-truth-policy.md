# RELIEF ground-truth policy

Status: **agreed** (Phase 0, 2026-11-17). The meta-entity class lists in §5 are finalised against the pilot data in Phase 1.

This document defines *what* counts as a ground-truth summary triple. The pipeline (R1–R8, see `RELIEF-plan.md`) is how RELIEF approximates it; the gold set (see `annotation-guidelines.md`) is how we measure the approximation.

## 1. Definition
For a root entity *r* with an English Wikipedia article, a Wikidata triple *(s, p, o)* is a **summary triple of r** if and only if:
1. it is an item-valued statement present in the dump-derived graph (`(:WikiEntity)-[:HAS_TYPE {type: p}]->(:WikiEntity)` in Neo4j);
2. *r* is its subject or its object (*r ∈ {s, o}*), and *s ≠ o*;
3. its relation is **expressed** in the *evidence* of *r*'s article (§3), as defined in §4;
4. it isn't excluded by §5.

The summary of *r* is the set of all such triples. RELIEF never adds triples that aren't in the graph.

## 2. Data version
The graph (Neo4j), page↔QID mapping, article text and labels (Postgres) all come from the **same dump date** (2023-05-01 for the development phase). No live Wikidata or Wikipedia data enters a ground-truth decision. Live data may be used only for clearly separated diagnostics.

## 3. Evidence
- **Scope:** section 0 of the root's article: the lead prose before the first heading, **and** the infobox(es) in it. This is the scope of the original WikES annotation, which keeps the two comparable.
- **By design, the summary of a root is exactly the set of its triples expressed in these two parts** (decision of 2026-11-17). Nothing else is evidence: not the article body, other articles, references, categories, navigation boxes, image captions or hatnotes.

## 4. "Expressed"
A relation is expressed when a careful reader, given **only** the evidence, would accept the triple as stated or directly implied:
- **Counts:** explicit statements ("born in Tupelo"); paraphrases ("his hometown, Tupelo"); infobox fields ("Instruments: guitar"); demonyms for nationality ("American singer" → country of citizenship: United States); standard compositional meaning ("his twin brother" → sibling).
- **Doesn't count:**
  - mere co-occurrence ("the Memphis press covered the trial" isn't "resided in Memphis");
  - facts that need outside knowledge;
  - relations about a different entity than the one the triple names;
  - the wrong relation for the right pair (e.g. "lyrics by" when the text only says he performed the song).
- **Direction matters:** *(A, father, B)* and *(B, father, A)* are different claims.
- **Pronouns and short names** ("He", "Presley") in the root's own article refer to the root unless the text clearly says otherwise.

## 5. Exclusions (candidate filter R1)
1. **Wikimedia-internal entities** (by `P31`): list article `Q13406463`, disambiguation page `Q4167410`, human-name disambiguation page `Q22808320`, category `Q4167836`, template `Q11266439`, disambiguation category `Q15407973`, project page `Q14204246`, internal item `Q17442446`, page outside the main knowledge tree `Q17379835`, **and any class whose English label starts with "Wikimedia " or "Wikipedia "** (added 2026-11-18 after the pilot class review: specific list classes such as *Wikimedia artist discography* slipped through the fixed list).
2. **List-like works about the root** (by `P31`): filmography `Q1371849`, discography `Q273057`/`Q4162149`, bibliography `Q1631107`/`Q134995`/`Q4086340`, videography `Q2662841`/`Q17438413`, list `Q12139612`.
3. **Aspect sub-articles of the root:** a neighbour whose label contains the root's label and is linked through `P1269` facet of or `P921` main subject. Examples from the WikES 1.0.5 ground truth: "cultural impact of Elvis Presley" (`P31` cultural impact), "Military career of Elvis Presley" (`P31` military service).
4. **Self-loops** (*s = o*).

The class lists are an initial version. **Phase 1 validates them against the pilot:** it lists the `P31` classes of every pilot neighbour that appears in the original WikES ground truth or in RELIEF candidates, and the list is finalised from that review. The lists are configuration, versioned with each run.

There's **no property blacklist**: every item-valued property is eligible.

## 6. Naming triples
Naming triples count as summaries (decision of 2026-11-13). The item-valued naming properties are `P735` given name, `P734` family name, `P1950` second family name (Spanish), `P9139` first family name (Portuguese), `P6978` Scandinavian middle family name, `P8500` Vietnamese middle name, `P5056` patronym or matronym, `P2838` professional name (Japan).

Their evidence is the first lead sentence and the infobox name fields (`name`, `birth_name`, and similar). Nickname (`P1449`), birth name (`P1477`) and pseudonym (`P742`) are text values in Wikidata, never graph edges, so they're out of scope automatically.

## 7. Decision rule
- **Every candidate goes through NLI**, including infobox evidence (decision of 2026-11-13).
- A triple is accepted when its best evidence reaches P(entailment) ≥ τ and P(contradiction) is below a guard value. **τ and the guard are calibrated on the gold set**, never fixed in advance.
- **Several predicates for the same pair** (decision of 2026-11-17): each predicate is judged separately, and **every entailed predicate is kept**. Example: if the lead says Elvis lived at, died at and is buried at Graceland, *residence*, *place of death* and *place of burial* are three summary triples.
- **Inverse and symmetric duplicates collapse to one triple.** When Wikidata stores the same fact in both directions (*Lisa Marie → father → Elvis* and *Elvis → child → Lisa Marie*; *spouse* in both directions), only one copy becomes ground truth: the one with the root as subject if it exists, otherwise the stored one. The other copy stays in the graph.
- **2023 dump only:** a *best one per pair* variant (comparable to the original's one-predicate-per-pair rule) is also produced, solely for the comparison with WikES 1.0.x. It isn't produced for newer dumps.

## 8. Root eligibility
A root enters a dataset when it has at least `MIN_VALID_SUMMARY_EDGES` (default 5) summary triples, as in the original generator. The rule applies to **every** dataset (decision of 2026-11-17).

The goal is a robust ES benchmark under this policy; comparing with the old ground truth is a secondary analysis. Hence two kinds of dataset, one per dump:
- **2023 dump, variant A ("relabel"):** the published WikES 1.0.5 graphs with their ground truth replaced by RELIEF's. RELIEF summary edges missing from a graph are added (they're incident to the root). Roots with fewer than 5 RELIEF summaries are **dropped** as roots, and the number dropped is reported. This is also where the comparison with the old ground truth is done.
- **Newer dump, variant B ("regenerate"):** datasets generated from scratch with RELIEF as the ground-truth source. No old ground truth is kept or compared.

## 9. Provenance
Every accepted *and* rejected candidate is stored with:
- the evidence text and its location (sentence id or infobox field);
- the mention source and disambiguation rule (link, label, redirect, anchor, name field);
- the template id and template-bank version;
- the NLI model and its three probabilities;
- the git commit and the run id.

Ground truth can then be recomputed for any τ without re-running NLI.

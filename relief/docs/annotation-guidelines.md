# RELIEF gold set: annotation guidelines

Status: **draft for sign-off** (Phase 0). The gold set measures how well RELIEF (and the original WikES annotation) implements the ground-truth policy (`ground-truth-policy.md`), and it calibrates the NLI threshold τ.

## 1. What you label
Each row is one **candidate instance**: a Wikidata triple of the root together with one piece of evidence from the root's article.

| Column | Meaning |
|---|---|
| `item_id` | stable id of the row |
| `root`, `root_label` | the entity whose article is shown |
| `subject_label`, `predicate_label`, `object_label` (+ QIDs) | the triple, with the direction as stored in Wikidata |
| `predicate_description` | the property's Wikidata description |
| `evidence_type` | `prose` or `infobox` |
| `evidence` | the sentence (with the previous sentence for context) or the infobox field and its value |
| `mention` | the text span RELIEF matched to the other entity, and how (`link`, `label`, `redirect`, `anchor`, `name_field`) |
| `wikipedia_url` | the article, for context only (2023 text may differ from today's page) |

What you **don't** see: RELIEF's score, the original WikES decision, or anyone else's label.

## 2. Labels
Answer one question: **does the evidence express this triple, as defined in the policy (§4)?**

| Label | Use when |
|---|---|
| `yes` | The evidence states or directly implies the triple, in this direction, about these entities |
| `no` | It doesn't: co-occurrence only, a different relation, a different entity, wrong direction, or it needs outside knowledge |
| `unsure` | You can't decide; say why in `note` |

When the label is `no`, add one **reason** tag:
- `wrong_entity`: the mention refers to a different entity (e.g. the song, not the film);
- `wrong_relation`: the pair is related in the text, but not by this property;
- `wrong_direction`;
- `not_stated`: the entities co-occur but no relation between them is stated;
- `not_about_root`: the sentence is about someone or something else.

## 3. Rules of thumb
- **Judge only the evidence shown**, plus the article title for "he/she/it". Don't use what you know about the entity.
- **Accept paraphrase and demonyms:** "American singer" expresses *country of citizenship: United States*; "his wife Priscilla" expresses *spouse*.
- **Infobox fields count as statements:** `Instruments: guitar` expresses *instrument: guitar*. `Labels: RCA Victor` expresses *record label: RCA Victor*.
- **Names:** "Elvis Aaron Presley" expresses *given name: Aaron* and *family name: Presley*.
- **Generic predicates** ("instance of", "part of"): only `yes` if the text actually says it ("X is a band" → instance of: musical group).
- **Wrong in reality but stated in the text:** `yes`. We measure *expression*, not truth.

## 4. Examples (Elvis Presley, Q303)
The evidence wording is shortened for illustration; real rows show the full 2023 sentence.

| Triple | Evidence | Label |
|---|---|---|
| Elvis — place of birth → Tupelo | "Presley was born in Tupelo, Mississippi …" | `yes` |
| Elvis — instrument → guitar | infobox `instruments = Vocals, guitar, piano` | `yes` |
| Heartbreak Hotel — lyrics by → Elvis | "… his first RCA Victor single, 'Heartbreak Hotel' …" | `no` (`wrong_relation`: he performed it) |
| Jailhouse Rock (song) — performer → Elvis | "… films such as *Jailhouse Rock* …" | `no` (`wrong_entity`: the film is meant) |
| Elvis — place of death → Memphis | "He died … at Graceland, his estate in Memphis" | `yes` |

## 5. Procedure
1. **Sample:** about 1,000 instances from the ~50 pilot seeds, stratified by evidence type (prose vs infobox), mention source (link vs unlinked), multi-predicate pairs and naming triples, so every case RELIEF handles is measured.
2. **Two annotators:** both label an overlap of at least 300 instances, which gives the agreement measure (Cohen's κ, reported per stratum). The rest is split between them.
3. **Independent labelling,** in the given order (shuffled, not grouped by root), without discussing items.
4. **Adjudication:** disagreements on the overlap are discussed and resolved into the final label. Unresolvable items stay `unsure` and are excluded from τ calibration, but counted and reported.
5. **Calibration batch first:** both annotators label the same 30 items, compare, and settle questions before the main round. Those 30 items aren't part of the agreement figure.

## 6. Output
A CSV per annotator: `item_id, label, reason, note, annotator, timestamp`. It's committed to the repository (it's small), so calibration on the server uses exactly the labels made on the laptop.

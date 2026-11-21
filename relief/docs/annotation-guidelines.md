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

## 4a. Reasons for `no`, in detail
Give **one** reason per `no`. If several fit, use the **first** in this order:
`wrong_entity` → `not_about_root` → `wrong_direction` → `wrong_relation` → `not_stated`.
The examples are shortened for illustration.

### `wrong_entity`: the text means a different entity than the triple names
The mention's words fit, but they refer to something else, usually a namesake.
- **Test:** replace the mention with the triple's entity, *including its description*. Does the sentence still say the same thing?

| Triple | Evidence | Why `no` |
|---|---|---|
| *Jailhouse Rock* (song) — performer → Elvis | "…starred in films such as *Jailhouse Rock*…" | the film is meant, not the song |
| Elvis — record label → Sun Records | "…played at the Sun Valley festival…" | "Sun" here isn't the label |
| David Bowie — member of → Queen (band) | "…performed for Queen Elizabeth II…" | the monarch, not the band |
| Taylor Swift — genre → country music | "…she toured the country…" | "country" means a nation, not the genre |

### `not_about_root`: the sentence states it about someone else
The relation *is* stated, but for a different person or thing than the root.
- **Test:** who is the subject of the verb?

| Triple | Evidence | Why `no` |
|---|---|---|
| Elvis — spouse → Michael Jackson | "His daughter Lisa Marie married Michael Jackson." | Lisa Marie's spouse, not Elvis's |
| Henry Fonda — award received → Academy Award | "His daughter Jane Fonda won two Academy Awards." | Jane's award |
| Prince — place of birth → Minneapolis | "His father was born in Minneapolis…" | the father's birthplace |

### `wrong_direction`: right pair, right relation, reversed
- **Test:** read the triple as a sentence ("A is the father of B") and check it against the text.

| Triple | Evidence | Why `no` |
|---|---|---|
| Elvis — father → Lisa Marie | "…his daughter, Lisa Marie…" | Lisa Marie's father is Elvis, not the other way round |
| Tim Burton — influenced by → Johnny Depp | "Burton's films influenced a generation of actors, including Depp." | Burton influenced Depp |
| Roger Federer — coach → Ivan Ljubičić | "Federer coached the junior team…" | the text has Federer as coach |

### `wrong_relation`: the pair is related in the text, but not by this property
The two entities really are connected in the evidence, but the property in the triple says something different.
- **Test:** would the text support a *different* property for the same pair? If so, use `wrong_relation`.

| Triple | Evidence | Why `no` |
|---|---|---|
| Heartbreak Hotel — lyrics by → Elvis | "…his first RCA single, 'Heartbreak Hotel'…" | he performed it; nothing says he wrote it |
| Elvis — place of death → Memphis | infobox `resting_place: Graceland, Memphis` | the field gives the burial place |
| Whitney Houston — place of birth → New Jersey | "…raised in East Orange, New Jersey…" | raised, not born |
| Kanye West — record label → Def Jam | "…he worked as a producer for Def Jam artists…" | producer for, not signed to |

### `not_stated`: they co-occur, but no relation between them is stated
Both appear in the evidence, but the text doesn't connect them at all, or only by being in the same list or sentence.
- **Test:** delete everything except the two names and the words between them. Is there a relation left?

| Triple | Evidence | Why `no` |
|---|---|---|
| Elvis — instrument → piano | "Elvis recorded with pianist Floyd Cramer." | piano is Cramer's instrument |
| Clint Eastwood — educated at → Oakland | "Born in San Francisco, Eastwood grew up near Oakland." | growing up near isn't education |
| Jane Austen — residence → London | "Her novels were published in London." | publication place, not residence |
| Federer — country for sport → Spain | "He defeated Rafael Nadal of Spain." | Spain belongs to Nadal |

## 4b. `no` vs `unsure`
- **`unsure`** is for real uncertainty: the text is ambiguous, or you can't tell which entity is meant even after opening the article. Always add a `note` saying why, e.g. *"can't tell whether 'Blue Hawaii' is the film or the album"*.
- **Not `unsure`:** "I'm not sure the fact is true". Labels are about **what the text says**, not what's true. A stated fact is `yes` even if you think it's wrong; an unstated fact is `no` even if you know it's true.
- **Implied but not stated:** accept only implications any careful reader would draw without outside knowledge.
  - "his widow Priscilla" → *spouse* is `yes`.
  - "toured with the band for years" → *member of* is `no` (`not_stated`); touring with a band isn't membership.

## 5. Procedure
1. **Sample:** about 1,000 instances from the ~50 pilot seeds, stratified by evidence type (prose vs infobox), mention source (link vs unlinked), multi-predicate pairs and naming triples, so every case RELIEF handles is measured.
2. **Two annotators:** both label an overlap of at least 300 instances, which gives the agreement measure (Cohen's κ, reported per stratum). The rest is split between them.
3. **Independent labelling,** in the given order (shuffled, not grouped by root), without discussing items.
4. **Adjudication:** disagreements on the overlap are discussed and resolved into the final label. Unresolvable items stay `unsure` and are excluded from τ calibration, but counted and reported.
5. **Calibration batch first:** both annotators label the same 30 items, compare, and settle questions before the main round. Those 30 items aren't part of the agreement figure.

## 6. Output
A CSV per annotator: `item_id, label, reason, note, annotator, timestamp`. It's committed to the repository (it's small), so calibration on the server uses exactly the labels made on the laptop.

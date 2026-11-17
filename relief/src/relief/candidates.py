"""R1: a root's candidate edges and everything known about its neighbours, from the dump-derived databases."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from more_itertools import chunked

from relief.policy import INTERNAL_LABEL_PREFIXES, exclusion_reason


@dataclass(frozen=True)
class Candidate:
    subject: str
    predicate: str
    object: str
    neighbour: str          # the end that is not the root
    root_is_subject: bool
    excluded: str | None    # policy §5 reason, or None


@dataclass
class Entity:
    qid: str
    label: str | None = None
    description: str | None = None
    classes: set[str] = field(default_factory=set)      # P31 objects
    article_title: str | None = None                     # its English Wikipedia article, if any
    redirect_titles: list[str] = field(default_factory=list)


@dataclass
class RootContext:
    root: Entity
    page_id: int | None
    wikitext: str | None
    candidates: list[Candidate]
    entities: dict[str, Entity]               # root and every neighbour
    predicate_labels: dict[str, tuple[str | None, str | None]]   # pid -> (label, description)


def strip_disambiguation(title: str) -> str:
    """'Jailhouse_Rock_(film)' -> 'Jailhouse Rock'."""
    return re.sub(r"\s*\([^)]*\)$", "", title.replace("_", " ")).strip()


class KnowledgeBase:
    """Read-only access to the restored Postgres and Neo4j databases."""

    def __init__(self, pg, neo4j_driver, batch: int = 5000):
        self.pg = pg
        self.neo4j = neo4j_driver
        self.batch = batch

    # ---- Neo4j
    def edges(self, qid: str) -> list[tuple[str, str, str]]:
        with self.neo4j.session(database="neo4j") as session:
            return [(r["s"], r["p"], r["o"]) for r in session.run(
                "MATCH (r:WikiEntity {entityName: $q})-[e:HAS_TYPE]-(:WikiEntity) "
                "RETURN startNode(e).entityName AS s, e.type AS p, endNode(e).entityName AS o", q=qid)]

    def classes(self, qids) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        with self.neo4j.session(database="neo4j") as session:
            for batch in chunked(sorted(set(qids)), self.batch):
                for r in session.run(
                        "UNWIND $ids AS id MATCH (n:WikiEntity {entityName: id})-[e:HAS_TYPE]->(c:WikiEntity) "
                        "WHERE e.type = 'P31' RETURN id, collect(c.entityName) AS classes", ids=batch):
                    result[r["id"]] = set(r["classes"])
        return result

    # ---- Postgres
    def _query(self, sql, values):
        rows = []
        with self.pg.cursor() as cursor:
            for batch in chunked(sorted(set(values)), self.batch):
                cursor.execute(sql, (list(batch),))
                rows.extend(cursor.fetchall())
        return rows

    def labels(self, qids) -> dict[str, tuple[str | None, str | None]]:
        return {q: (l, d) for q, l, d in self._query(
            "SELECT name, label, description FROM subjects WHERE name = ANY(%s)", qids)}

    def predicate_labels(self, pids) -> dict[str, tuple[str | None, str | None]]:
        return {p: (l, d) for p, l, d in self._query(
            "SELECT property_id, property_label, description FROM predicates WHERE property_id = ANY(%s)", pids)}

    def titles(self, qids) -> dict[str, tuple[str | None, list[str]]]:
        """qid -> (article title, redirect titles), from relief_titles (see anchors.build_titles)."""
        result: dict[str, tuple[str | None, list[str]]] = {}
        for qid, title, is_article in self._query(
                "SELECT wikidata_id, title, is_article FROM relief_titles WHERE wikidata_id = ANY(%s) "
                "ORDER BY wikidata_id, page_id", qids):
            article, redirects = result.get(qid, (None, []))
            if is_article and article is None:
                article = title
            else:
                redirects.append(title)
            result[qid] = (article, redirects)
        return result

    def resolve_titles(self, titles) -> dict[str, str]:
        """Wikipedia title (article or redirect) -> QID."""
        return {t: q for t, q in self._query(
            "SELECT title, wikidata_id FROM relief_titles WHERE title = ANY(%s) ORDER BY is_article", titles)}

    def anchors_available(self) -> dict | None:
        """Build provenance of the anchor dictionary, or None when it hasn't been built in this database."""
        with self.pg.cursor() as cursor:
            cursor.execute("SELECT to_regclass('relief_anchors') IS NOT NULL AND to_regclass('relief_anchor_meta') IS NOT NULL")
            if not cursor.fetchone()[0]:
                return None
            cursor.execute("SELECT key, value FROM relief_anchor_meta")
            return dict(cursor.fetchall())

    def anchors_for(self, qids, per_entity: int = 200) -> dict[str, list[tuple[str, int]]]:
        """qid -> its most frequent link texts [(surface, n)]."""
        result: dict[str, list[tuple[str, int]]] = {}
        for qid, surface, n in self._query(
                "SELECT wikidata_id, surface, n FROM (SELECT wikidata_id, surface, n, row_number() OVER "
                f"(PARTITION BY wikidata_id ORDER BY n DESC) AS rank FROM relief_anchors WHERE wikidata_id = ANY(%s)) t "
                f"WHERE rank <= {int(per_entity)}", qids):
            result.setdefault(qid, []).append((surface, n))
        return result

    def anchor_totals(self, surfaces) -> dict[str, int]:
        """surface -> how many links use exactly this text, to any entity."""
        return {s: int(n) for s, n in self._query(
            "SELECT surface, sum(n) FROM relief_anchors WHERE surface = ANY(%s) GROUP BY surface", surfaces)}

    def summaries(self, qid: str) -> set[tuple[str, str, str]]:
        """The original WikES (1.0.x) ground truth of a root: its SUMMARY edges in Neo4j."""
        with self.neo4j.session(database="neo4j") as session:
            return {(r["s"], r["p"], r["o"]) for r in session.run(
                "MATCH (s:WikiEntity)-[r:SUMMARY {summary_for: $q}]->(o:WikiEntity) "
                "WHERE s.entityName = $q OR o.entityName = $q "
                "RETURN s.entityName AS s, r.predicate AS p, o.entityName AS o", q=qid)}

    def article(self, qid: str) -> tuple[int | None, str | None]:
        with self.pg.cursor() as cursor:
            cursor.execute(
                "SELECT wp.id, wp.content FROM wiki_page_to_wiki_data_mappings m "
                "JOIN wikipedia_pages wp ON wp.id = m.wikipedia_id WHERE m.wikidata_id = %s ORDER BY wp.id LIMIT 1",
                (qid,))
            row = cursor.fetchone()
        return (row[0], row[1]) if row else (None, None)

    # ---- R1
    def root_context(self, qid: str) -> RootContext:
        edges = self.edges(qid)
        neighbours = {s if o == qid else o for s, _, o in edges} - {qid}
        everyone = neighbours | {qid}
        labels = self.labels(everyone)
        classes = self.classes(everyone)
        titles = self.titles(everyone)
        entities = {}
        for q in everyone:
            label, description = labels.get(q, (None, None))
            article, redirects = titles.get(q, (None, []))
            entities[q] = Entity(q, label, description, classes.get(q, set()), article, redirects)
        root = entities[qid]
        all_classes = {c for e in entities.values() for c in e.classes}
        internal = {c for c, (label, _) in self.labels(all_classes).items()
                    if label and label.startswith(INTERNAL_LABEL_PREFIXES)}
        candidates = []
        for s, p, o in edges:
            neighbour = o if s == qid else s
            reason = exclusion_reason(root.label or "", p, entities[neighbour].label if neighbour in entities else None,
                                      entities[neighbour].classes if neighbour in entities else set(), s == o,
                                      internal)
            candidates.append(Candidate(s, p, o, neighbour, s == qid, reason))
        page_id, wikitext = self.article(qid)
        return RootContext(root, page_id, wikitext, candidates, entities,
                           self.predicate_labels({p for _, p, _ in edges}))

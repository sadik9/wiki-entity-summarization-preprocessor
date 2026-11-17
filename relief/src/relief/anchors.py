"""Anchor-text dictionary: how often each visible link text points at each entity, over all articles of the dump.

Gives aliases Wikidata labels miss (demonyms, short forms), confirms redirect titles as aliases, and supplies the
commonness P(entity | surface) used to disambiguate (R3b, R3d).

    relief anchors build --workers 32

Tables (in the dump's Postgres database; rebuilt from scratch on every run):
    relief_anchors(surface, wikidata_id, n)     one row per (visible text, target entity)
    relief_anchor_meta(key, value)              build provenance
"""
from __future__ import annotations

import io
import re
import time
from collections import Counter
from multiprocessing import Pool

from relief.config import Settings
from relief.db import pg_connect
from relief.text import normalize_title

# [[target]] or [[target|anchor]]; targets can't contain brackets or pipes, anchors can't contain brackets
LINK = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]*?))?\]\]")
MAX_SURFACE = 120


def clean_surface(text: str) -> str:
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def page_anchor_counts(wikitext: str) -> Counter:
    counts: Counter = Counter()
    for match in LINK.finditer(wikitext):
        target = normalize_title(match.group(1))
        if target is None:
            continue
        surface = clean_surface(match.group(2) if match.group(2) is not None else match.group(1).split("#", 1)[0])
        if surface and len(surface) <= MAX_SURFACE:
            counts[(target, surface)] += 1
    return counts


def _tsv(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\t", " ").replace("\n", " ").replace("\r", " ")


def _work(task) -> tuple[int, int]:
    """Count anchors of the pages with id in [first, last] and append them to relief_anchor_raw."""
    first, last = task
    settings = Settings.from_env()
    counts: Counter = Counter()
    pages = 0
    with pg_connect(settings) as pg:
        with pg.cursor(name=f"anchors_{first}") as cursor:      # server-side cursor: pages stream in
            cursor.itersize = 500
            cursor.execute("SELECT content FROM wikipedia_pages WHERE id BETWEEN %s AND %s", (first, last))
            for (content,) in cursor:
                pages += 1
                if content:
                    counts.update(page_anchor_counts(content))
        buffer = io.StringIO()
        for (target, surface), n in counts.items():
            buffer.write(f"{_tsv(target)}\t{_tsv(surface)}\t{n}\n")
        buffer.seek(0)
        with pg.cursor() as cursor:
            cursor.copy_expert("COPY relief_anchor_raw (target_title, surface, n) FROM STDIN", buffer)
        pg.commit()
    return pages, len(counts)


def build(settings: Settings, workers: int = 16, pages_per_task: int = 20_000, max_pages: int | None = None,
          aggregate_workers: int = 0, aggregate_mem: str = "256MB") -> dict:
    """aggregate_workers/aggregate_mem: Postgres parallel workers and work_mem for the final GROUP BY. Each
    parallel worker uses shared memory (/dev/shm of the Postgres container), so keep
    aggregate_workers x aggregate_mem below its shm_size (laptop 1g: serial; sol 8g: e.g. 8 x 512MB)."""
    start = time.time()
    with pg_connect(settings) as pg, pg.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS relief_anchor_raw")
        cursor.execute("CREATE UNLOGGED TABLE relief_anchor_raw (target_title text, surface text, n integer)")
        cursor.execute("SELECT id FROM wikipedia_pages ORDER BY id")
        ids = [row[0] for row in cursor.fetchall()][:max_pages]      # max_pages: smoke tests only
        pg.commit()
    tasks = [(ids[i], ids[min(i + pages_per_task, len(ids)) - 1]) for i in range(0, len(ids), pages_per_task)]
    print(f"{len(ids):,} pages in {len(tasks)} tasks, {workers} workers", flush=True)

    pages = 0
    with Pool(workers) as pool:
        for done, (n_pages, _) in enumerate(pool.imap_unordered(_work, tasks), 1):
            pages += n_pages
            if done % 20 == 0 or done == len(tasks):
                print(f"  {done}/{len(tasks)} tasks, {pages:,} pages, {time.time() - start:.0f}s", flush=True)

    with pg_connect(settings) as pg, pg.cursor() as cursor:
        print("aggregating ...", flush=True)
        cursor.execute("SET work_mem = %s", (aggregate_mem,))
        cursor.execute("SET max_parallel_workers_per_gather = %s", (aggregate_workers,))
        cursor.execute("DROP TABLE IF EXISTS relief_anchors")
        cursor.execute(
            "CREATE TABLE relief_anchors AS "
            "SELECT r.surface, m.wikidata_id, sum(r.n)::bigint AS n "
            "FROM relief_anchor_raw r JOIN wiki_page_to_wiki_data_mappings m ON m.wikipedia_title = r.target_title "
            "WHERE m.wikidata_id IS NOT NULL GROUP BY r.surface, m.wikidata_id")
        cursor.execute("CREATE INDEX relief_anchors_surface ON relief_anchors (surface)")
        cursor.execute("CREATE INDEX relief_anchors_surface_lower ON relief_anchors (lower(surface))")
        cursor.execute("CREATE INDEX relief_anchors_qid ON relief_anchors (wikidata_id)")
        cursor.execute("SELECT count(*), coalesce(sum(n), 0) FROM relief_anchors")
        rows, links = cursor.fetchone()
        cursor.execute("DROP TABLE relief_anchor_raw")
        stats = {"pages": pages, "rows": rows, "links": int(links), "seconds": round(time.time() - start),
                 "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git_commit": settings.git_commit,
                 "complete": max_pages is None}
        cursor.execute("CREATE TABLE IF NOT EXISTS relief_anchor_meta (key text PRIMARY KEY, value text)")
        cursor.execute("TRUNCATE relief_anchor_meta")
        for key, value in stats.items():
            cursor.execute("INSERT INTO relief_anchor_meta VALUES (%s, %s)", (key, str(value)))
        cursor.execute("ANALYZE relief_anchors")
        pg.commit()
    return stats

"""
Upsert the labels and descriptions of every Wikidata property into the `predicates` table.

The TSV files loaded by the Flyway migrations stop at P12688 (2023), and edges with newer properties used to make the
summary annotation of the whole page fail. Run it after the first wdgb/wppe start (Flyway creates the table).

    poetry run python scripts/refresh_predicates.py
"""
from __future__ import annotations

import json
import urllib.parse

from psycopg2.extras import execute_values

from common import http_get, pg_connection

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
QUERY = """
SELECT ?property ?label ?description WHERE {
  ?property a wikibase:Property .
  OPTIONAL { ?property rdfs:label ?label . FILTER(LANG(?label) = "en") }
  OPTIONAL { ?property schema:description ?description . FILTER(LANG(?description) = "en") }
}
"""


def main():
    body = urllib.parse.urlencode({"query": QUERY}).encode()
    with http_get(SPARQL_ENDPOINT, data=body, headers={"Accept": "application/sparql-results+json"}) as response:
        bindings = json.load(response)["results"]["bindings"]
    rows = {}
    for binding in bindings:
        property_id = binding["property"]["value"].rsplit("/", 1)[-1]
        rows[property_id] = (
            property_id,
            binding.get("label", {}).get("value"),
            binding.get("description", {}).get("value"),
        )
    with pg_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM predicates")
        before = cursor.fetchone()[0]
        execute_values(
            cursor,
            """
            INSERT INTO predicates (property_id, property_label, description) VALUES %s
            ON CONFLICT (property_id) DO UPDATE SET
                property_label = COALESCE(EXCLUDED.property_label, predicates.property_label),
                description = COALESCE(EXCLUDED.description, predicates.description)
            """,
            list(rows.values()),
        )
        cursor.execute("SELECT count(*) FROM predicates")
        after = cursor.fetchone()[0]
    print(f"Fetched {len(rows)} properties; predicates table grew from {before} to {after} rows")


if __name__ == "__main__":
    main()

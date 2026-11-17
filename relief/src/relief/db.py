"""Connections to the WikES Postgres and Neo4j databases."""
from __future__ import annotations

from relief.config import Settings


def pg_connect(settings: Settings):
    import psycopg2

    # The restored database is UTF-8; say so explicitly so no client default can decode text as ASCII.
    return psycopg2.connect(
        host=settings.db_host, port=settings.db_port, dbname=settings.db_name,
        user=settings.db_user, password=settings.db_password,
        options="-c client_encoding=UTF8", application_name="relief",
    )


def neo4j_driver(settings: Settings):
    from neo4j import GraphDatabase

    return GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

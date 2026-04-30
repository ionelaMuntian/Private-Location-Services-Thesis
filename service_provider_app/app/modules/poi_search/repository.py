# service_provider_app/app/modules/poi_search/repository.py
from typing import Any

from psycopg.rows import dict_row

from ...core.config import settings
from ...infrastructure.db import get_connection

class PoiRepository:
    def __init__(self):
        self.schema = settings.db_schema
        self.table = settings.db_table

    def get_candidates_by_category(
        self,
        category: str,
        latitude_m: float,
        longitude_m: float,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        sql = f"""
        WITH query_point AS (
            SELECT
                ST_SetSRID(ST_MakePoint(%(longitude_m)s, %(latitude_m)s), 3857) AS q_geom_3857,
                ST_Transform(
                    ST_SetSRID(ST_MakePoint(%(longitude_m)s, %(latitude_m)s), 3857),
                    4326
                )::geography AS q_geog
        )
        SELECT
            p.id::bigint AS id,
            p.name AS name,
            p.category AS category,
            p.lat::double precision AS latitude,
            p.lon::double precision AS longitude,
            p.lat_m::double precision AS lat_m,
            p.lon_m::double precision AS lon_m,
            ST_Distance(
                ST_Transform(p.geom, 4326)::geography,
                q.q_geog
            )::double precision AS distance_m
        FROM {self.schema}.{self.table} p
        CROSS JOIN query_point q
        WHERE lower(p.category) = lower(%(category)s)
        ORDER BY p.geom <-> q.q_geom_3857
        LIMIT %(limit)s;
        """

        params = {
            "category": category,
            "latitude_m": latitude_m,
            "longitude_m": longitude_m,
            "limit": limit,
        }

        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def get_by_category_nearest_k_plaintext(
        self,
        category: str,
        k: int,
        latitude_m: float,
        longitude_m: float,
    ) -> list[dict[str, Any]]:
        sql = f"""
        WITH query_point AS (
            SELECT
                ST_SetSRID(ST_MakePoint(%(longitude_m)s, %(latitude_m)s), 3857) AS q_geom_3857,
                ST_Transform(
                    ST_SetSRID(ST_MakePoint(%(longitude_m)s, %(latitude_m)s), 3857),
                    4326
                )::geography AS q_geog
        )
        SELECT
            p.id::bigint AS id,
            p.name AS name,
            p.category AS category,
            p.lat::double precision AS latitude,
            p.lon::double precision AS longitude,
            ROUND(
                (
                    ST_Distance(
                        ST_Transform(p.geom, 4326)::geography,
                        q.q_geog
                    ) / 1000.0
                )::numeric,
                4
            )::double precision AS distance_km
        FROM {self.schema}.{self.table} p
        CROSS JOIN query_point q
        WHERE lower(p.category) = lower(%(category)s)
        ORDER BY p.geom <-> q.q_geom_3857
        LIMIT %(k)s;
        """

        params = {
            "category": category,
            "k": k,
            "latitude_m": latitude_m,
            "longitude_m": longitude_m,
        }

        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def search_by_name(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        sql = f"""
        SELECT
            p.id::bigint AS id,
            p.name AS name,
            p.category AS category,
            p.lat::double precision AS latitude,
            p.lon::double precision AS longitude
        FROM {self.schema}.{self.table} p
        WHERE p.name IS NOT NULL
          AND btrim(p.name) <> ''
          AND p.name ILIKE %(pattern)s
        ORDER BY
            CASE
                WHEN lower(p.name) = lower(%(exact_query)s) THEN 0
                WHEN lower(p.name) LIKE lower(%(prefix_query)s) THEN 1
                ELSE 2
            END,
            length(p.name),
            p.name
        LIMIT %(limit)s;
        """

        params = {
            "pattern": f"%{query}%",
            "exact_query": query,
            "prefix_query": f"{query}%",
            "limit": limit,
        }

        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def list_categories(self) -> list[str]:
        sql = f"""
        SELECT DISTINCT category
        FROM {self.schema}.{self.table}
        WHERE category IS NOT NULL
          AND btrim(category) <> ''
        ORDER BY category;
        """

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        return [row[0] for row in rows]
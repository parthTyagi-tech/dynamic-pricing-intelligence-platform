import logging
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

_SCHEMA_PATCHED = False


def auto_patch_database_schema(db):
    """
    Idempotently ensures all v2 columns and tables exist in the database.
    Automatically resolves psycopg2.errors.UndefinedColumn errors on existing cloud databases
    without requiring manual SQL execution in production.
    """
    global _SCHEMA_PATCHED
    if _SCHEMA_PATCHED:
        return

    try:
        engine = db.engine
        inspector = inspect(engine)
        dialect_name = engine.dialect.name
        table_names = inspector.get_table_names()

        # 1. Create missing tables (price_histories, scraper_reliabilities, etc.)
        db.create_all()

        # 2. Check and patch pricing_recommendations columns
        if "pricing_recommendations" in table_names:
            cols = {c["name"] for c in inspector.get_columns("pricing_recommendations")}
            json_type = "JSON" if dialect_name != "sqlite" else "TEXT"
            dt_type = "TIMESTAMP" if dialect_name != "sqlite" else "DATETIME"
            bool_type = "BOOLEAN" if dialect_name != "sqlite" else "INTEGER"

            statements = []
            if "task_id" not in cols:
                statements.append("ALTER TABLE pricing_recommendations ADD COLUMN task_id VARCHAR(64)")
            if "platform_prices_snapshot" not in cols:
                statements.append(f"ALTER TABLE pricing_recommendations ADD COLUMN platform_prices_snapshot {json_type}")
            if "margin_floor_applied" not in cols:
                if dialect_name == "sqlite":
                    statements.append("ALTER TABLE pricing_recommendations ADD COLUMN margin_floor_applied INTEGER DEFAULT 0")
                else:
                    statements.append("ALTER TABLE pricing_recommendations ADD COLUMN margin_floor_applied BOOLEAN DEFAULT FALSE")
            if "margin_floor_value" not in cols:
                statements.append("ALTER TABLE pricing_recommendations ADD COLUMN margin_floor_value FLOAT")
            if "sanity_bound_flagged" not in cols:
                if dialect_name == "sqlite":
                    statements.append("ALTER TABLE pricing_recommendations ADD COLUMN sanity_bound_flagged INTEGER DEFAULT 0")
                else:
                    statements.append("ALTER TABLE pricing_recommendations ADD COLUMN sanity_bound_flagged BOOLEAN DEFAULT FALSE")
            if "decided_at" not in cols:
                statements.append(f"ALTER TABLE pricing_recommendations ADD COLUMN decided_at {dt_type}")
            if "decided_by" not in cols:
                statements.append("ALTER TABLE pricing_recommendations ADD COLUMN decided_by VARCHAR(36)")

            if statements:
                with engine.connect() as conn:
                    for stmt in statements:
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            logger.warning(f"[AutoPatch] Error running '{stmt}': {e}")
                    conn.commit()

        # 3. Check and patch audit_logs columns
        if "audit_logs" in table_names:
            audit_cols = {c["name"] for c in inspector.get_columns("audit_logs")}
            json_type = "JSON" if dialect_name != "sqlite" else "TEXT"
            statements = []
            if "before_value" not in audit_cols:
                statements.append(f"ALTER TABLE audit_logs ADD COLUMN before_value {json_type}")
            if "after_value" not in audit_cols:
                statements.append(f"ALTER TABLE audit_logs ADD COLUMN after_value {json_type}")

            if statements:
                with engine.connect() as conn:
                    for stmt in statements:
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            logger.warning(f"[AutoPatch] Error running '{stmt}': {e}")
                    conn.commit()

        _SCHEMA_PATCHED = True
        logger.info("[AutoPatch] Database schema verified and patched successfully.")
    except Exception as exc:
        logger.warning(f"[AutoPatch] Schema sync encountered an error (will retry): {exc}")

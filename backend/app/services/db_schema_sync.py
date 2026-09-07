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

        # 4. Check and patch scraper_reliability columns
        if "scraper_reliability" in table_names:
            rel_cols = {c["name"] for c in inspector.get_columns("scraper_reliability")}
            dt_type = "TIMESTAMP" if dialect_name != "sqlite" else "DATETIME"
            statements = []
            if "circuit_opened_at" not in rel_cols:
                statements.append(f"ALTER TABLE scraper_reliability ADD COLUMN circuit_opened_at {dt_type}")
            if "backoff_minutes" not in rel_cols:
                statements.append("ALTER TABLE scraper_reliability ADD COLUMN backoff_minutes INTEGER DEFAULT 15")
            if "last_successful_scrape_at" not in rel_cols:
                statements.append(f"ALTER TABLE scraper_reliability ADD COLUMN last_successful_scrape_at {dt_type}")

            if statements:
                with engine.connect() as conn:
                    for stmt in statements:
                        try:
                            conn.execute(text(stmt))
                        except Exception as e:
                            logger.warning(f"[AutoPatch] Error running '{stmt}': {e}")
                    conn.commit()

        # 5. One-time backfill of legacy competitor_prices to price_history and drop legacy tables
        if "competitor_prices" in table_names:
            try:
                with engine.connect() as conn:
                    rows = conn.execute(text("SELECT product_id, organization_id, competitor_name, competitor_price FROM competitor_prices")).fetchall()
                    if rows:
                        import uuid
                        import json
                        from datetime import datetime, timezone
                        grouped = {}
                        for pid, oid, cname, cprice in rows:
                            key = (pid, oid)
                            if key not in grouped:
                                grouped[key] = {}
                            if cprice is not None:
                                grouped[key][cname] = float(cprice)
                        for (pid, oid), pprices in grouped.items():
                            hist_id = str(uuid.uuid4())
                            now_str = datetime.now(timezone.utc).isoformat()
                            pp_json = json.dumps(pprices)
                            conn.execute(
                                text("INSERT INTO price_history (id, product_id, organization_id, old_price, new_price, platform_prices, created_at) VALUES (:id, :pid, :oid, :old_p, :new_p, :pp, :created_at)"),
                                {"id": hist_id, "pid": pid, "oid": oid, "old_p": 0.0, "new_p": 0.0, "pp": pp_json, "created_at": now_str}
                            )
                    conn.execute(text("DROP TABLE competitor_prices"))
                    conn.commit()
                    logger.info("[AutoPatch] Legacy competitor_prices migrated to price_history and dropped.")
            except Exception as e:
                logger.warning(f"[AutoPatch] Error during legacy competitor_prices backfill: {e}")

        if "price_alerts" in table_names:
            try:
                with engine.connect() as conn:
                    conn.execute(text("DROP TABLE price_alerts"))
                    conn.commit()
                    logger.info("[AutoPatch] Legacy price_alerts table dropped.")
            except Exception as e:
                logger.warning(f"[AutoPatch] Error dropping price_alerts table: {e}")

        _SCHEMA_PATCHED = True
        logger.info("[AutoPatch] Database schema verified and patched successfully.")
    except Exception as exc:
        logger.warning(f"[AutoPatch] Schema sync encountered an error (will retry): {exc}")

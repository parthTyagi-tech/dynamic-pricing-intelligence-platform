import csv
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.product import Product

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (SEC-4)
DANGEROUS_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize_csv_injection(cell_value: str) -> str:
    """
    SEC-4: Neutralizes CSV/Spreadsheet formula injection.
    Any cell beginning with '=', '+', '-', '@', tab, or carriage return
    is prepended with a single quote to force spreadsheets to treat it as plain text.
    """
    if not cell_value:
        return ""
    str_val = str(cell_value).strip()
    if str_val.startswith(DANGEROUS_FORMULA_PREFIXES):
        # Prepend single quote to neutralize formula execution in Excel/Sheets
        logger.warning(f"[SEC-4 CSV Injection Neutralized] Neutralized cell formula: {str_val[:20]}")
        return f"'{str_val}"
    return str_val


def parse_and_ingest_catalog_csv(
    file_bytes: bytes,
    filename: str,
    organization_id: str,
    user_id: str
) -> Tuple[int, int, List[str]]:
    """
    SEC-4: Validates size, neutralizes CSV injection, and ingests products into catalog.
    Returns: (imported_count, updated_count, errors)
    """
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"File size exceeds 10MB limit (SEC-4). Received: {len(file_bytes)} bytes.")

    if not filename.lower().endswith(".csv"):
        raise ValueError("Invalid file format. Only .csv files are supported.")

    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = file_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(decoded))
    imported_count = 0
    updated_count = 0
    errors = []

    for row_idx, row in enumerate(reader, start=2):
        try:
            name = neutralize_csv_injection(row.get("name") or row.get("product_name") or "")
            sku = neutralize_csv_injection(row.get("sku") or row.get("sku_id") or "")

            if not name or not sku:
                errors.append(f"Row {row_idx}: Missing required 'name' or 'sku'.")
                continue

            category = neutralize_csv_injection(row.get("category") or "general").lower()
            description = neutralize_csv_injection(row.get("description") or "")
            brand = neutralize_csv_injection(row.get("brand") or "")
            barcode = neutralize_csv_injection(row.get("barcode") or "")

            try:
                current_price = float(re.sub(r"[^\d.]", "", str(row.get("current_price", 0))))
            except ValueError:
                current_price = 0.0

            try:
                cost_price = float(re.sub(r"[^\d.]", "", str(row.get("cost_price", 0))))
            except ValueError:
                cost_price = 0.0

            try:
                inventory = int(re.sub(r"[^\d]", "", str(row.get("inventory_quantity", 0))))
            except ValueError:
                inventory = 0

            # Check if SKU already exists in this organization
            existing = Product.query.filter_by(sku=sku, organization_id=organization_id).first()
            if existing:
                existing.name = name
                existing.category = category
                existing.description = description
                existing.brand = brand
                existing.barcode = barcode
                existing.current_price = current_price
                existing.cost_price = cost_price
                existing.inventory_quantity = inventory
                updated_count += 1
            else:
                new_prod = Product(
                    id=str(uuid.uuid4()),
                    sku=sku,
                    name=name,
                    category=category,
                    description=description,
                    brand=brand,
                    barcode=barcode,
                    current_price=current_price,
                    cost_price=cost_price,
                    inventory_quantity=inventory,
                    organization_id=organization_id,
                )
                db.session.add(new_prod)
                imported_count += 1

        except Exception as e:
            errors.append(f"Row {row_idx}: {str(e)}")

    # SEC-8: Audit log CSV upload
    audit_entry = AuditLog(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        actor_user_id=user_id,
        action="csv_catalog_uploaded",
        entity_type="catalog",
        entity_id=filename,
        metadata_json={
            "filename": filename,
            "imported_count": imported_count,
            "updated_count": updated_count,
            "error_count": len(errors),
        }
    )
    db.session.add(audit_entry)
    db.session.commit()

    return imported_count, updated_count, errors

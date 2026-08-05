import re
from datetime import datetime, timezone


def normalize_query(value: str) -> str:
    if not value:
        return ""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_product_record(product: dict) -> dict:
    if not isinstance(product, dict):
        product = {}

    name = str(product.get("name") or "").strip()
    brand = str(product.get("brand") or "").strip()
    category_hint = str(product.get("category") or product.get("category_hint") or "").strip() or "general"
    attributes = product.get("attributes") or {}
    if not isinstance(attributes, dict):
        attributes = {}

    normalized_attrs = {}
    for key, value in attributes.items():
        normalized_attrs[str(key).strip()] = value

    normalized_name = normalize_query(name)
    normalized_brand = normalize_query(brand)
    normalized_tokens = []
    for token in [normalized_brand, normalized_name]:
        if token:
            normalized_tokens.extend(token.split())

    # Preserve the design's flexible product layout
    normalized = {
        "product_id": product.get("id") or product.get("product_id"),
        "seller_id": product.get("seller_id"),
        "catalog_name": name,
        "brand": brand,
        "category_hint": category_hint,
        "normalized_query": " ".join(dict.fromkeys(normalized_tokens)),
        "base_price": product.get("current_price") or product.get("base_price") or 0,
        "currency": product.get("currency") or "INR",
        "inventory_status": product.get("inventory_status") or "in_stock",
        "attributes": normalized_attrs,
        "updated_at": product.get("updated_at") or datetime.now(timezone.utc).isoformat(),
    }

    if not normalized["normalized_query"]:
        normalized["normalized_query"] = normalize_query(name)

    return normalized


def normalize_marketplace_result(result: dict) -> dict:
    if not isinstance(result, dict):
        return {}

    source = str(result.get("source") or "unknown").lower()
    title = str(result.get("title") or result.get("name") or "").strip()
    attributes = result.get("attributes") or {}
    if not isinstance(attributes, dict):
        attributes = {}

    normalized_attrs = {}
    for key, value in attributes.items():
        normalized_attrs[str(key).strip()] = value

    return {
        "source": source,
        "title": title,
        "price": float(result.get("price") or 0),
        "currency": str(result.get("currency") or "INR").upper(),
        "availability": str(result.get("availability") or result.get("in_stock") or "in_stock").lower(),
        "url": result.get("url") or "",
        "fetched_at": result.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "category_hint": str(result.get("category_hint") or result.get("category") or "general").lower(),
        "attributes": normalized_attrs,
    }

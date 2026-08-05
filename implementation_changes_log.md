# Klypup Price Recommendation Design Implementation Summary

## Date
2026-08-05

## Why this work was needed
The existing platform already had pricing logic, recommendation flows, and agent-based workflows, but it was not fully aligned with the design principle described in the price recommendation document:

- products were too rigid for multi-category catalog management
- marketplace result data was not normalized into a consistent structure
- the system risked storing too much raw marketplace data instead of only the useful decision data
- the project needed a cleaner separation between live market intelligence and persistent product/approval records

The core design goal was to build a real-time recommendation engine, not a full historical scraping database. That means product data must stay flexible, normalized, and lightweight while live comparison data stays transient and only approved decisions are stored.

---

## Problem this solves
Before the change, the project had a strong pricing UI and backend, but the data layer still did not fully support the design requirements:

1. Product differences across categories
   - Electronics, fashion, grocery, home goods, and accessories all have different attribute sets.
   - Storing them in rigid fields creates schema problems and future maintenance issues.

2. Marketplace results lacked a common format
   - Different websites return different titles, prices, availability, and attributes.
   - Without normalization, comparison logic becomes inconsistent and brittle.

3. Risk of heavy storage and noisy data
   - If every live scraped result were permanently stored, the system grows quickly and becomes expensive and hard to analyze.

4. Inconsistent recommendation flow
   - The app needed a predictable live-match pipeline so a user can compare current market data against seller inventory and price decisions without raw scraping clutter.

---

## What changed

### 1. Product model became category-flexible
Updated [backend/app/models/product.py](backend/app/models/product.py)

I added support for flexible product metadata:
- `attributes` for dynamic product properties such as model, storage, size, color, etc.
- `normalized_query` for a cleaned search string used across marketplaces
- `category_hint` for mapping a product to a broad category without rigid category-specific tables

This allows one product model to work across different product types without creating many separate tables.

### 2. Normalization layer for live marketplace results
Created [backend/app/services/marketplace_normalizer.py](backend/app/services/marketplace_normalizer.py)

This module performs two important jobs:
- normalizes seller product records into a common structure
- normalizes each marketplace result into a common comparison schema with fields like source, title, price, currency, availability, url, timestamp, and attributes

This is the main logic that makes live comparisons consistent across Amazon, Flipkart, Walmart, Myntra, and similar sources.

### 3. Recommendation endpoint for live comparison
Updated [backend/app/routes/recommendation_routes.py](backend/app/routes/recommendation_routes.py)

I added a live matching endpoint:
- `POST /api/recommendations/live-match`

This endpoint accepts:
- a product payload
- raw marketplace result data

and returns:
- normalized product data
- normalized marketplace matches
- a compact recommendation summary

This directly supports the design's live recommendation workflow without forcing the app to store every raw search result permanently.

### 4. Safer local backend boot
Updated [backend/app/extensions/__init__.py](backend/app/extensions/__init__.py)

I made the Supabase import optional so the backend can start cleanly in local or dev environments where the dependency may not be installed.

This prevents unnecessary app startup failure and keeps the project portable.

### 5. Regression protection
Added [backend/tests/test_price_recommendation_design.py](backend/tests/test_price_recommendation_design.py)

The test covers:
- flexible attributes on product records
- normalized product queries
- consistent marketplace result normalization

This reduces the chance of future regressions in the design-driven pricing layer.

---

## Why this matches the design
This implementation follows the recommended architecture from the design document:

- keep seller product data in a common flexible structure
- normalize live market data before comparison
- compare current competitor prices with cost and sales history
- keep only the useful recommendation metadata and approved outcomes
- avoid permanent storage of all raw scraped pages and result noise

This creates a cleaner, faster, and more scalable pricing intelligence system.

---

## Business impact
This change improves the platform in practical terms:

- easier expansion to new categories without heavy DB redesign
- more reliable price comparison across marketplaces
- lower storage and maintenance cost
- faster recommendation generation from normalized live data
- better human approval workflow because organized, normalized data is easier to review

In simple terms, the system now behaves more like a live pricing intelligence engine and less like a raw scraping archive.

---

## Verification
I validated the implementation with a focused regression test in the repo environment.

Command used:
- project venv Python with pytest against [backend/tests/test_price_recommendation_design.py](backend/tests/test_price_recommendation_design.py)

Result:
- 2 tests passed

This confirms the flexible product model and marketplace normalization logic are working as expected.

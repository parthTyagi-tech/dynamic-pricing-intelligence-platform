import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("FLASK_ENV", "testing")

from app.extensions import db
from app.models.product import Product
from app.services.marketplace_normalizer import normalize_marketplace_result, normalize_product_record
from run import app


def test_product_supports_flexible_attributes_and_normalized_query():
    with app.app_context():
        product = Product(
            sku="TEST-ATTR-001",
            name="Samsung Galaxy M34 128GB Black",
            brand="Samsung",
            category="electronics",
            current_price=18000,
            cost_price=14000,
            inventory_quantity=22,
            organization_id="org-1",
            normalized_query="samsung galaxy m34 128gb black",
            category_hint="electronics",
            attributes={
                "model": "Galaxy M34",
                "storage": "128GB",
                "ram": "6GB",
                "color": "black",
            },
        )

        assert product.normalized_query == "samsung galaxy m34 128gb black"
        assert product.category_hint == "electronics"
        assert product.attributes["storage"] == "128GB"


def test_marketplace_normalizer_standardizes_results():
    product = {
        "name": "Samsung Galaxy M34 128GB Black",
        "brand": "Samsung",
        "category": "electronics",
        "attributes": {"model": "Galaxy M34", "storage": "128GB", "color": "black"},
    }

    normalized = normalize_product_record(product)
    result = normalize_marketplace_result(
        {
            "source": "amazon",
            "title": "Samsung Galaxy M34 128GB",
            "price": 19999,
            "currency": "INR",
            "availability": "in_stock",
            "url": "https://example.com/product",
            "attributes": {"brand": "Samsung", "model": "M34", "storage": "128GB"},
        }
    )

    assert normalized["normalized_query"].startswith("samsung")
    assert result["source"] == "amazon"
    assert result["currency"] == "INR"
    assert result["attributes"]["storage"] == "128GB"


def test_csv_import_handles_dynamic_attributes_and_metadata():
    from io import BytesIO
    from app.models.user import User
    from app.models.product import Product

    with app.app_context():
        # Clean existing test products if any
        Product.query.filter(Product.sku.startswith("CSV-TEST-")).delete()
        db.session.commit()

        # Let's find a valid user or mock one to generate a JWT token
        test_user = User.query.first()
        if not test_user:
            # If no user in testing database, we'll create a transient test user
            test_user = User(
                email="test_import_user@example.com",
                name="Import Tester",
                password_hash="dummy_hash",
                organization_id="org-import-test"
            )
            db.session.add(test_user)
            db.session.commit()

        # Create JWT token
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=test_user.id)

        # Build mock CSV stream (note the escaped internal quotes for JSON in CSV field)
        csv_data = (
            "name,sku,category,description,brand,barcode,current_price,cost_price,inventory_quantity,category_hint,normalized_query,attributes\n"
            'iPhone 15 Pro,CSV-TEST-001,electronics,Apple iPhone 15 Pro,Apple,0194253713028,99000.00,80000.00,50,handheld,apple iphone 15 pro,"{""model"": ""iPhone 15 Pro"", ""ram"": ""8GB""}"\n'
        )
        
        client = app.test_client()
        response = client.post(
            "/api/products/import-csv",
            headers={"Authorization": f"Bearer {token}"},
            data={"file": (BytesIO(csv_data.encode("utf-8-sig")), "test.csv")},
            content_type="multipart/form-data"
        )
        
        assert response.status_code == 200
        assert response.json["success"] is True
        
        # Verify the product was imported with its metadata
        imported_product = Product.query.filter_by(sku="CSV-TEST-001").first()
        assert imported_product is not None
        assert imported_product.category_hint == "handheld"
        assert imported_product.normalized_query == "apple iphone 15 pro"
        assert imported_product.attributes["model"] == "iPhone 15 Pro"
        assert imported_product.attributes["ram"] == "8GB"

        # Cleanup
        db.session.delete(imported_product)
        if test_user.email == "test_import_user@example.com":
            db.session.delete(test_user)
        db.session.commit()


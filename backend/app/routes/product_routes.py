from flask import Blueprint, request

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)

from app.extensions import db

from app.models.user import User
from app.models.product import Product


product_bp = Blueprint(
    "products",
    __name__
)


# =====================================
# CREATE PRODUCT
# =====================================

@product_bp.route(
    "",
    methods=["POST"]
)
@jwt_required()
def create_product():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(current_user_id)

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    if not current_user.is_admin():

        return {
            "success": False,
            "message": "Only admins can create products"
        }, 403

    data = request.get_json()

    required_fields = [
        "sku",
        "name",
        "category",
        "current_price",
        "cost_price"
    ]

    for field in required_fields:

        if field not in data:

            return {
                "success": False,
                "message": f"{field} is required"
            }, 400

    existing_product = Product.query.filter_by(
        sku=data["sku"]
    ).first()

    if existing_product:

        return {
            "success": False,
            "message": "SKU already exists"
        }, 400

    product = Product(
        sku=data["sku"],
        name=data["name"],
        category=data["category"],
        description=data.get("description"),
        current_price=data["current_price"],
        cost_price=data["cost_price"],
        inventory_quantity=data.get(
            "inventory_quantity",
            0
        ),
        organization_id=current_user.organization_id
    )

    db.session.add(product)

    db.session.commit()

    return {
        "success": True,
        "message": "Product created successfully",
        "product": product.to_dict()
    }, 201


# =====================================
# GET ALL PRODUCTS
# =====================================

@product_bp.route(
    "",
    methods=["GET"]
)
@jwt_required()
def get_products():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(current_user_id)

    products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).all()

    return {
        "success": True,
        "count": len(products),
        "products": [
            product.to_dict()
            for product in products
        ]
    }, 200


# =====================================
# GET SINGLE PRODUCT
# =====================================

@product_bp.route(
    "/<product_id>",
    methods=["GET"]
)
@jwt_required()
def get_product(product_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(current_user_id)

    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:

        return {
            "success": False,
            "message": "Product not found"
        }, 404

    return {
        "success": True,
        "product": product.to_dict()
    }, 200


# =====================================
# UPDATE PRODUCT
# =====================================

@product_bp.route(
    "/<product_id>",
    methods=["PUT"]
)
@jwt_required()
def update_product(product_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(current_user_id)

    if not current_user.is_admin():

        return {
            "success": False,
            "message": "Only admins can update products"
        }, 403

    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:

        return {
            "success": False,
            "message": "Product not found"
        }, 404

    data = request.get_json()

    product.name = data.get(
        "name",
        product.name
    )

    product.category = data.get(
        "category",
        product.category
    )

    product.description = data.get(
        "description",
        product.description
    )

    product.current_price = data.get(
        "current_price",
        product.current_price
    )

    product.cost_price = data.get(
        "cost_price",
        product.cost_price
    )

    product.inventory_quantity = data.get(
        "inventory_quantity",
        product.inventory_quantity
    )

    db.session.commit()

    return {
        "success": True,
        "message": "Product updated successfully",
        "product": product.to_dict()
    }, 200


# =====================================
# DELETE PRODUCT
# =====================================

@product_bp.route(
    "/<product_id>",
    methods=["DELETE"]
)
@jwt_required()
def delete_product(product_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(current_user_id)

    if not current_user.is_admin():

        return {
            "success": False,
            "message": "Only admins can delete products"
        }, 403

    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:

        return {
            "success": False,
            "message": "Product not found"
        }, 404

    db.session.delete(product)

    db.session.commit()

    return {
        "success": True,
        "message": "Product deleted successfully"
    }, 200
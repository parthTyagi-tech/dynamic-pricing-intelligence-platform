from flask import Blueprint

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)

from app.extensions import db

from app.models.user import User

from app.models.recommendation import (
    PricingRecommendation,
    ApprovalAction,
    RecommendationStatus,
    ApprovalActionType
)

from app.models.product import Product


approval_bp = Blueprint(
    "approvals",
    __name__
)


# =====================================
# APPROVE RECOMMENDATION
# =====================================

@approval_bp.route(
    "/approve/<recommendation_id>",
    methods=["POST"]
)
@jwt_required()
def approve_recommendation(recommendation_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    if not current_user.is_admin():

        return {
            "success": False,
            "message": "Only admins can approve recommendations"
        }, 403

    recommendation = PricingRecommendation.query.filter_by(
        id=recommendation_id,
        organization_id=current_user.organization_id
    ).first()

    if not recommendation:

        return {
            "success": False,
            "message": "Recommendation not found"
        }, 404

    if recommendation.status != RecommendationStatus.PENDING:

        return {
            "success": False,
            "message": "Recommendation already processed"
        }, 400

    product = Product.query.get(
        recommendation.product_id
    )

    previous_price = product.current_price

    # =====================================
    # UPDATE PRODUCT PRICE
    # =====================================

    product.current_price = recommendation.recommended_price

    # =====================================
    # UPDATE RECOMMENDATION STATUS
    # =====================================

    recommendation.status = RecommendationStatus.APPROVED

    # =====================================
    # CREATE AUDIT LOG
    # =====================================

    approval_action = ApprovalAction(

        recommendation_id=recommendation.id,

        action_type=ApprovalActionType.APPROVE,

        previous_price=previous_price,

        executed_price=recommendation.recommended_price,

        approved_by=current_user.id
    )

    db.session.add(approval_action)

    db.session.commit()

    return {

        "success": True,

        "message":
        "Recommendation approved successfully",

        "product":
        product.to_dict(),

        "recommendation":
        recommendation.to_dict()

    }, 200


# =====================================
# REJECT RECOMMENDATION
# =====================================

@approval_bp.route(
    "/reject/<recommendation_id>",
    methods=["POST"]
)
@jwt_required()
def reject_recommendation(recommendation_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    recommendation = PricingRecommendation.query.filter_by(
        id=recommendation_id,
        organization_id=current_user.organization_id
    ).first()

    if not recommendation:

        return {
            "success": False,
            "message": "Recommendation not found"
        }, 404

    if recommendation.status != RecommendationStatus.PENDING:

        return {
            "success": False,
            "message": "Recommendation already processed"
        }, 400

    product = Product.query.get(
        recommendation.product_id
    )

    # =====================================
    # UPDATE STATUS
    # =====================================

    recommendation.status = RecommendationStatus.REJECTED

    # =====================================
    # CREATE AUDIT LOG
    # =====================================

    rejection_action = ApprovalAction(

        recommendation_id=recommendation.id,

        action_type=ApprovalActionType.REJECT,

        previous_price=product.current_price,

        executed_price=recommendation.recommended_price,

        approved_by=current_user.id,

        rejection_reason="Rejected by admin"
    )

    db.session.add(rejection_action)

    db.session.commit()

    return {

        "success": True,

        "message":
        "Recommendation rejected successfully",

        "recommendation":
        recommendation.to_dict()

    }, 200


# =====================================
# GET APPROVAL HISTORY
# =====================================

@approval_bp.route(
    "/history",
    methods=["GET"]
)
@jwt_required()
def get_approval_history():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    # =====================================
    # MULTI-TENANT FILTERING
    # =====================================

    approval_actions = ApprovalAction.query.join(
        PricingRecommendation
    ).filter(
        PricingRecommendation.organization_id
        == current_user.organization_id
    ).order_by(
        ApprovalAction.timestamp.desc()
    ).all()

    return {

        "success": True,

        "count":
        len(approval_actions),

        "history": [

            action.to_dict()

            for action in approval_actions
        ]

    }, 200
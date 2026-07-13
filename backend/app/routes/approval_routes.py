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
from app.models.market_data import CompetitorPrice
from app.services.email_service import send_recommendation_action_email
from app.services.whatsapp_service import send_whatsapp_recommendation_action

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

    try:
        competitor_records = CompetitorPrice.query.filter_by(
            product_id=product.id,
            organization_id=current_user.organization_id
        ).all()
        comp_prices = [c.to_dict() for c in competitor_records]
        
        product_details = {
            "name": product.name,
            "sku": product.sku
        }
        rec_details = {
            "id": recommendation.id,
            "previous_price": previous_price,
            "executed_price": recommendation.recommended_price,
            "rationale": recommendation.rationale,
            "confidence_score": recommendation.confidence_score
        }
        send_recommendation_action_email(
            user_email=current_user.email,
            action_type="approve",
            product_details=product_details,
            recommendation_details=rec_details,
            competitor_prices=comp_prices
        )
    except Exception as e:
        print(f"[Approval Route] Failed to send approval email: {e}")

    # Send WhatsApp notification if user has phone number
    if current_user.phone_number:
        try:
            send_whatsapp_recommendation_action(
                phone_number=current_user.phone_number,
                action_type="approve",
                product_details=product_details,
                recommendation_details=rec_details,
                competitor_prices=comp_prices,
            )
        except Exception as e:
            print(f"[Approval Route] Failed to send approval WhatsApp: {e}")

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

    try:
        competitor_records = CompetitorPrice.query.filter_by(
            product_id=product.id,
            organization_id=current_user.organization_id
        ).all()
        comp_prices = [c.to_dict() for c in competitor_records]
        
        product_details = {
            "name": product.name,
            "sku": product.sku
        }
        rec_details = {
            "id": recommendation.id,
            "previous_price": product.current_price,
            "executed_price": recommendation.recommended_price,
            "rationale": recommendation.rationale,
            "confidence_score": recommendation.confidence_score
        }
        send_recommendation_action_email(
            user_email=current_user.email,
            action_type="reject",
            product_details=product_details,
            recommendation_details=rec_details,
            competitor_prices=comp_prices
        )
    except Exception as e:
        print(f"[Approval Route] Failed to send rejection email: {e}")

    # Send WhatsApp notification if user has phone number
    if current_user.phone_number:
        try:
            send_whatsapp_recommendation_action(
                phone_number=current_user.phone_number,
                action_type="reject",
                product_details=product_details,
                recommendation_details=rec_details,
                competitor_prices=comp_prices,
            )
        except Exception as e:
            print(f"[Approval Route] Failed to send rejection WhatsApp: {e}")

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


# =====================================
# ROLLBACK APPROVAL
# =====================================

@approval_bp.route("/rollback/<action_id>", methods=["POST"])
@jwt_required()
def rollback_approval(action_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    if not current_user.is_admin():
        return {"success": False, "message": "Only admins can rollback approvals"}, 403

    target_action = ApprovalAction.query.get(action_id)
    if not target_action:
        return {"success": False, "message": "Audit log action not found"}, 404

    recommendation = target_action.recommendation
    if not recommendation or recommendation.organization_id != current_user.organization_id:
        return {"success": False, "message": "Access denied / Invalid recommendation"}, 403

    if target_action.action_type != ApprovalActionType.APPROVE:
        return {"success": False, "message": "Only approved actions can be rolled back"}, 400

    already_rolled_back = ApprovalAction.query.filter_by(
        recommendation_id=recommendation.id,
        action_type="rollback"
    ).first()
    if already_rolled_back:
        return {"success": False, "message": "This approval has already been rolled back"}, 400

    product = Product.query.get(recommendation.product_id)
    if not product:
        return {"success": False, "message": "Associated product not found"}, 404

    original_price = product.current_price
    restored_price = target_action.previous_price
    product.current_price = restored_price

    rollback_action = ApprovalAction(
        recommendation_id=recommendation.id,
        action_type="rollback",
        previous_price=original_price,
        executed_price=restored_price,
        approved_by=current_user.id
    )
    db.session.add(rollback_action)
    db.session.commit()

    try:
        competitor_records = CompetitorPrice.query.filter_by(
            product_id=product.id,
            organization_id=current_user.organization_id
        ).all()
        comp_prices = [c.to_dict() for c in competitor_records]
        
        product_details = {
            "name": product.name,
            "sku": product.sku
        }
        rec_details = {
            "id": recommendation.id,
            "previous_price": original_price,
            "executed_price": restored_price,
            "rationale": f"Reverted price back to pre-approval value of \u20b9{restored_price:.2f} via audit history rollback control.",
            "confidence_score": 1.0
        }
        send_recommendation_action_email(
            user_email=current_user.email,
            action_type="rollback",
            product_details=product_details,
            recommendation_details=rec_details,
            competitor_prices=comp_prices
        )
    except Exception as e:
        print(f"[Approval Route] Failed to send rollback email: {e}")

    # Send WhatsApp notification if user has phone number
    if current_user.phone_number:
        try:
            send_whatsapp_recommendation_action(
                phone_number=current_user.phone_number,
                action_type="rollback",
                product_details=product_details,
                recommendation_details=rec_details,
                competitor_prices=comp_prices,
            )
        except Exception as e:
            print(f"[Approval Route] Failed to send rollback WhatsApp: {e}")

    return {
        "success": True,
        "message": "Price successfully rolled back",
        "product": product.to_dict(),
        "action": rollback_action.to_dict()
    }, 200
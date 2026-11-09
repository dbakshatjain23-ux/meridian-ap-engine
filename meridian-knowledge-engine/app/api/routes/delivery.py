# app/api/routes/delivery.py
"""Delivery Routes - ERP Embed, Teams Bot, Browser Extension, Webhooks."""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_session
from app.middleware.auth import get_tenant, require_auth
from app.store.facts import FactRepository
from app.core.answer.router import CalculatorRouter
from app.core.answer.builder import AnswerBuilder
from app.gateways.llm import llm_gateway
from app.gateways.embeddings import embedding_gateway
from app.models.user import User

router = APIRouter()


# ============================================================
# ERP Embed
# ============================================================

class ERPEmbedRequest(BaseModel):
    invoice_id: str
    vendor_id: str
    client_desk: str
    exception_codes: List[str] = []
    context: dict = {}


class ERPEmbedResponse(BaseModel):
    widget_html: str
    answer_id: str
    actions: List[dict]


@router.post("/delivery/erp/embed", response_model=ERPEmbedResponse)
async def erp_embed(
    request: ERPEmbedRequest,
    tenant_slug: str = Depends(get_tenant),
    session: AsyncSession = Depends(get_session),
):
    """
    ERP Embed endpoint - returns contextual widget HTML for current invoice.
    Called by ERP iframe.
    """
    fact_repo = FactRepository(session)
    builder = AnswerBuilder(fact_repo, embedding_gateway, llm_gateway)
    router = CalculatorRouter()

    # Build composite query from exception codes
    query_parts = []
    for code in request.exception_codes:
        if code == "PRICE_VAR":
            query_parts.append("price variance exception")
        elif code == "NO_GRN":
            query_parts.append("missing GRN")
        elif code == "TDS_SECTION_UNCLEAR":
            query_parts.append("TDS section unclear")
        # Add more mappings

    query_text = f"Invoice {request.invoice_id}: " + "; ".join(query_parts)

    # Route and answer
    route_type, extracted = router.route(query_text, request.client_desk, "2026-08-01")
    extracted.update(request.context)
    extracted["client_desk"] = request.client_desk
    extracted["tenant_id"] = tenant_slug

    # Execute based on route (simplified)
    answer_data = await builder.build_lookup_answer(
        query_text, request.client_desk, None
    )

    # Generate widget HTML
    widget_html = f"""
    <div class="meridian-widget" style="font-family: Inter, sans-serif; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; max-width: 400px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <span style="font-weight: 600; color: #1a1a1a;">Meridian Knowledge Engine</span>
            <span style="font-size: 12px; color: #666;">v0.1.0</span>
        </div>
        <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.5; color: #333;">
            {answer_data['answer_markdown']}
        </div>
        <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #e0e0e0; display: flex; gap: 8px;">
            <button class="meridian-action" data-action="accept" style="background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Accept & Post</button>
            <button class="meridian-action" data-action="exception" style="background: #dc2626; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer;">Raise Exception</button>
        </div>
    </div>
    """

    return ERPEmbedResponse(
        widget_html=widget_html,
        answer_id=f"ans_{request.invoice_id}",
        actions=[
            {"label": "Accept & Post", "type": "erp_action", "payload": {"action": "post"}},
            {"label": "Raise Exception", "type": "erp_action", "payload": {"code": request.exception_codes[0] if request.exception_codes else "UNKNOWN"}},
        ]
    )


# ============================================================
# Teams Bot Proactive Message
# ============================================================

class TeamsMessageRequest(BaseModel):
    user_id: str
    message: str
    card_json: Optional[dict] = None


@router.post("/delivery/teams/message")
async def send_teams_message(
    request: TeamsMessageRequest,
    tenant_slug: str = Depends(get_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Send proactive message via Teams Bot."""
    # Would integrate with Microsoft Teams Bot Framework
    return {
        "status": "sent",
        "message": "Teams message queued for delivery",
        "user_id": request.user_id,
    }


# ============================================================
# Change Notification Webhooks
# ============================================================

class WebhookRegistration(BaseModel):
    url: str
    events: List[str]  # fact.created | fact.superseded | conflict.detected | sop.sync
    filter: Optional[dict] = None
    secret: str


class WebhookRegistrationResponse(BaseModel):
    webhook_id: str
    url: str
    events: List[str]
    status: str


@router.post("/delivery/webhook/change", response_model=WebhookRegistrationResponse)
async def register_webhook(
    request: WebhookRegistration,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """Register webhook for graph change notifications."""
    import uuid as uuid_lib
    webhook_id = f"wh_{uuid_lib.uuid4().hex[:8]}"

    # Store webhook registration (would need webhook table)
    return WebhookRegistrationResponse(
        webhook_id=webhook_id,
        url=request.url,
        events=request.events,
        status="registered",
    )
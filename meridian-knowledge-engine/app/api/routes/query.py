# app/api/routes/query.py
"""Query Routes - Main Processor Query Endpoint."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import time

from app.database import get_session
from app.middleware.auth import get_tenant, get_current_user, require_auth
from app.store.facts import FactRepository
from app.store.answers import AnswerLogRepository
from app.core.answer.router import CalculatorRouter
from app.core.answer.builder import AnswerBuilder
from app.core.answer.verifier import AnswerVerifier
from app.core.answer.escalation import EscalationService
from app.core.calculators import get_calculator
from app.gateways.llm import llm_gateway
from app.gateways.embeddings import embedding_gateway
from app.models.user import User

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

class InvoiceContext(BaseModel):
    po_line_val: Optional[float] = None
    po_unit_price: Optional[float] = None
    inv_unit_price: Optional[float] = None
    inv_qty: Optional[float] = None


class QueryRequest(BaseModel):
    query_text: str = Field(..., min_length=1, max_length=5000)
    client_desk: str = "ALL"
    vendor_id: Optional[str] = None
    invoice_date: Optional[str] = None
    as_of_date: Optional[str] = None
    invoice_context: Optional[InvoiceContext] = None
    stream: bool = False


class CitationResponse(BaseModel):
    block_id: str
    source: str
    section: Optional[str] = None
    valid_from: Optional[str] = None
    quote: str
    fact_ids: list[str] = []


class QueryResponse(BaseModel):
    execution_lane: str
    status: str
    answer_markdown: str
    math_result: Optional[dict] = None
    citations: list[CitationResponse] = []
    practice_notes: list[dict] = []
    older_sources: list[dict] = []
    verifier_result: dict
    escalation: Optional[dict] = None
    refusal_reason: Optional[str] = None
    response_time_ms: int


# ============================================================
# Main Query Endpoint
# ============================================================

@router.post("/query/ask", response_model=QueryResponse)
async def ask_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    tenant_slug: str = Depends(get_tenant),
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(get_session),
):
    """
    Main processor query endpoint - executes 3-Lane pipeline.
    """
    start_time = time.time()

    # Repositories
    fact_repo = FactRepository(session)
    answer_log_repo = AnswerLogRepository(session)

    # Parse as_of_date
    as_of_date = None
    if request.as_of_date:
        from datetime import date
        as_of_date = date.fromisoformat(request.as_of_date)

    # Route query
    router = CalculatorRouter()
    route_type, extracted_inputs = router.route(
        request.query_text,
        request.client_desk,
        request.as_of_date or "2026-08-01",
    )

    # Add invoice context to inputs
    if request.invoice_context:
        extracted_inputs.update(request.invoice_context.model_dump(exclude_none=True))
    if request.vendor_id:
        extracted_inputs["vendor_id"] = request.vendor_id
    if request.invoice_date:
        extracted_inputs["invoice_date"] = request.invoice_date
    if request.as_of_date:
        extracted_inputs["as_of_date"] = request.as_of_date
    extracted_inputs["client_desk"] = request.client_desk
    extracted_inputs["tenant_id"] = tenant_slug

    # Execute based on route
    math_result = None
    citations = []
    practice_notes = []
    older_sources = []
    answer_markdown = ""
    status = "SUCCESS"
    escalation = None
    refusal_reason = None

    try:
        if route_type == "computable":
            # Lane 1: Calculator
            calc_name = extracted_inputs.pop("calculator")
            calculator = get_calculator(calc_name)
            from app.core.calculators.base import CalculatorContext
            ctx = CalculatorContext(
                tenant_id=tenant_slug,
                client_desk=request.client_desk,
                as_of_date=request.as_of_date or "2026-08-01",
                vendor_id=request.vendor_id,
            )
            math_result = await calculator.calculate(ctx, extracted_inputs)
            status = math_result.get("status", "SUCCESS")

            # Build answer
            builder = AnswerBuilder(fact_repo, embedding_gateway, llm_gateway)
            answer_data = await builder.build_calculator_answer(
                calc_name, math_result, request.client_desk, as_of_date
            )
            answer_markdown = answer_data["answer_markdown"]
            citations = answer_data["citations"]
            older_sources = answer_data["older_sources"]
            practice_notes = answer_data["practice_notes"]

        elif route_type == "lookup":
            # Lane 2: Retrieval
            builder = AnswerBuilder(fact_repo, embedding_gateway, llm_gateway)
            answer_data = await builder.build_lookup_answer(
                request.query_text, request.client_desk, as_of_date
            )
            answer_markdown = answer_data["answer_markdown"]
            citations = answer_data["citations"]
            older_sources = answer_data["older_sources"]
            practice_notes = answer_data["practice_notes"]
            status = answer_data.get("status", "SUCCESS")

        elif route_type == "judgment":
            # Lane 3: TDS Classification / Judgment
            builder = AnswerBuilder(fact_repo, embedding_gateway, llm_gateway)
            answer_data = await builder.build_judgment_answer(
                request.query_text, request.client_desk, as_of_date, extracted_inputs
            )
            answer_markdown = answer_data["answer_markdown"]
            citations = answer_data["citations"]
            older_sources = answer_data["older_sources"]
            practice_notes = answer_data["practice_notes"]
            status = answer_data.get("status", "SUCCESS")

        elif route_type == "refused":
            # Out of scope
            status = "REFUSED"
            refusal_reason = "SCOPE_GUARD: Query outside knowledge base scope"
            answer_markdown = "I cannot answer this question as it falls outside the scope of the knowledge base. Please contact your Process Owner."

        else:
            # Default to lookup
            builder = AnswerBuilder(fact_repo, embedding_gateway, llm_gateway)
            answer_data = await builder.build_lookup_answer(
                request.query_text, request.client_desk, as_of_date
            )
            answer_markdown = answer_data["answer_markdown"]
            citations = answer_data["citations"]
            older_sources = answer_data["older_sources"]
            practice_notes = answer_data["practice_notes"]

    except Exception as e:
        # On error, escalate
        status = "ESCALATED"
        escalation = {
            "reason": "PROCESSING_ERROR",
            "detail": str(e),
            "escalated_to": "Process Owner",
        }
        answer_markdown = "An error occurred while processing your query. This has been escalated to the Process Owner."

    # Verify answer
    verifier = AnswerVerifier()
    verifier_result = verifier.verify(
        answer_markdown, citations, math_result, older_sources
    )

    # If verification fails, escalate
    if not verifier_result["passed"] and status not in ("ESCALATED", "REFUSED"):
        escalation_service = EscalationService(session)
        ticket = await escalation_service.create_escalation(
            tenant_slug=tenant_slug,
            query_text=request.query_text,
            client_desk=request.client_desk,
            draft_answer=answer_markdown,
            citations=citations,
            failure_reason=verifier_result["checks"],
        )
        escalation = {
            "reason": "VERIFIER_FAILED",
            "detail": verifier_result["checks"],
            "escalated_to": "Process Owner",
            "ticket_id": str(ticket.id),
        }
        status = "ESCALATED"
        answer_markdown = "I cannot confidently answer this question. It has been escalated to the Process Owner for review."

    response_time_ms = int((time.time() - start_time) * 1000)

    # Log answer (background)
    background_tasks.add_task(
        answer_log_repo.log_answer,
        tenant_id=UUID(tenant_slug) if tenant_slug != "meridian" else UUID("00000000-0000-0000-0000-000000000000"),
        query_text=request.query_text,
        client_desk=request.client_desk,
        as_of_date=as_of_date,
        route=route_type,
        answer_markdown=answer_markdown,
        citations=[c.model_dump() for c in citations] if citations else None,
        calculator_outputs=math_result,
        verifier_result=verifier_result,
        escalated=bool(escalation),
        escalation_reason=escalation.get("reason") if escalation else None,
        response_time_ms=response_time_ms,
    )

    return QueryResponse(
        execution_lane=route_type.upper(),
        status=status,
        answer_markdown=answer_markdown,
        math_result=math_result,
        citations=[CitationResponse(**c) for c in citations],
        practice_notes=practice_notes,
        older_sources=older_sources,
        verifier_result=verifier_result,
        escalation=escalation,
        refusal_reason=refusal_reason,
        response_time_ms=response_time_ms,
    )


@router.get("/query/ask/stream")
async def stream_query(
    # WebSocket endpoint - implement with FastAPI WebSocket
    pass
)
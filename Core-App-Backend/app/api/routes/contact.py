"""
app/api/routes/contact.py
-----------------------------------------------
Public (unauthenticated) endpoints backing the marketing site's
"Contact us" section and "Request a demo" page.
"""
from fastapi import APIRouter, HTTPException

from app.schemas.contact import ContactMessageRequest, DemoRequestRequest, FormSubmitResponse
from app.services.contact_service import submit_contact_message, submit_demo_request

router = APIRouter(prefix="/contact", tags=["Contact"])


@router.post("/message", response_model=FormSubmitResponse)
async def contact_message_endpoint(payload: ContactMessageRequest):
    """Store a 'Contact us' submission and email it to the team."""
    try:
        return submit_contact_message(payload.full_name, payload.email, payload.company_name, payload.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to submit your message. Please try again later.") from exc


@router.post("/request-demo", response_model=FormSubmitResponse)
async def request_demo_endpoint(payload: DemoRequestRequest):
    """Store a 'Request a demo' submission and email it to the team."""
    try:
        return submit_demo_request(payload.full_name, payload.email, payload.company_name, payload.message)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to submit your request. Please try again later.") from exc

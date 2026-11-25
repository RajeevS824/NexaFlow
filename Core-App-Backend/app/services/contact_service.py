"""
app/services/contact_service.py
-----------------------------------------------
Business logic for the public "Contact us" and "Request a demo"
forms: persist the submission first (so it's never lost even if
email delivery fails), then email the details to the team.
"""
import logging

from app.core.email_service import (
    EmailSendError,
    send_contact_message_notification,
    send_demo_request_notification,
)
from app.repositories.contact_repository import (
    insert_contact_message,
    insert_demo_request,
    mark_contact_message_email_sent,
    mark_demo_request_email_sent,
)

logger = logging.getLogger("uvicorn")


def submit_contact_message(full_name: str, email: str, company_name: str, message: str) -> dict:
    """Store a contact-form submission and email it to the team.

    The submission is always saved. A failure to send the notification
    email is logged but does not fail the request - the person's message
    has already been recorded either way.
    """
    contact_message_id = insert_contact_message(full_name, email, company_name, message)

    try:
        send_contact_message_notification(full_name, email, company_name, message)
        mark_contact_message_email_sent(contact_message_id)
    except EmailSendError as exc:
        logger.error("submit_contact_message: notification email failed: %s", exc)

    return {"message": "Thanks for reaching out! We'll get back to you within one business day."}


def submit_demo_request(full_name: str, email: str, company_name: str, message: str) -> dict:
    """Store a request-demo submission and email it to the team."""
    demo_request_id = insert_demo_request(full_name, email, company_name, message)

    try:
        send_demo_request_notification(full_name, email, company_name, message)
        mark_demo_request_email_sent(demo_request_id)
    except EmailSendError as exc:
        logger.error("submit_demo_request: notification email failed: %s", exc)

    return {"message": "Thanks! A member of our team will reach out to schedule your demo shortly."}

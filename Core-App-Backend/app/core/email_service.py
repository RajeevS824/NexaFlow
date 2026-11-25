"""
app/core/email_service.py
-----------------------------------------------
Minimal SMTP email sender (stdlib smtplib only - no extra
dependency) used to deliver the "reset your password" email.
"""
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import (
    MAIL_FROM_EMAIL,
    MAIL_FROM_NAME,
    NOTIFY_EMAIL,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_SECURE,
    SMTP_USER,
)

logger = logging.getLogger("uvicorn")


class EmailSendError(Exception):
    """Raised when the reset email could not be delivered."""


def _build_reset_email(to_email: str, to_name: str, reset_link: str, expire_minutes: int) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Reset your OneNextGen Automation password"
    msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>"
    msg["To"] = to_email

    greeting_name = to_name or "there"

    msg.set_content(
        f"""Hi {greeting_name},

We received a request to reset the password for your OneNextGen Automation account.

Reset your password using the link below. This link expires in {expire_minutes} minutes:

{reset_link}

If you didn't request this, you can safely ignore this email - your password will remain unchanged.

- OneNextGen Automation
"""
    )

    msg.add_alternative(
        f"""\
<html>
  <body style="font-family: Arial, Helvetica, sans-serif; background:#F7F8FA; padding:24px;">
    <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:14px;padding:32px;border:1px solid #e6e9ef;">
      <h2 style="color:#10202B;margin-top:0;">Reset your password</h2>
      <p style="color:#425466;font-size:14px;line-height:1.6;">
        Hi {greeting_name},<br/><br/>
        We received a request to reset the password for your OneNextGen Automation account.
        This link is valid for <strong>{expire_minutes} minutes</strong>.
      </p>
      <p style="text-align:center;margin:28px 0;">
        <a href="{reset_link}"
           style="background:#E8A33D;color:#10202B;text-decoration:none;font-weight:700;
                  padding:12px 28px;border-radius:8px;display:inline-block;">
          Reset Password
        </a>
      </p>
      <p style="color:#8a97ab;font-size:12.5px;line-height:1.6;">
        If the button above doesn't work, copy and paste this link into your browser:<br/>
        <a href="{reset_link}" style="color:#2C5566;">{reset_link}</a>
      </p>
      <p style="color:#8a97ab;font-size:12.5px;">
        If you didn't request this, you can safely ignore this email - your password will remain unchanged.
      </p>
    </div>
  </body>
</html>
""",
        subtype="html",
    )

    return msg


def _send(message: EmailMessage, to_email_for_log: str) -> None:
    """Shared SMTP delivery used by every outbound email in this module."""
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP is not configured (SMTP_HOST/SMTP_USER/SMTP_PASS missing).")
        raise EmailSendError("Email service is not configured.")

    try:
        if SMTP_SECURE:
            # Implicit TLS (typically port 465)
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(message)
        else:
            # STARTTLS (typically port 587)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(message)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email_for_log, exc)
        raise EmailSendError("Failed to send the email. Please try again later.") from exc


def send_password_reset_email(to_email: str, to_name: str, reset_link: str, expire_minutes: int) -> None:
    """Send the password-reset email via SMTP. Raises EmailSendError on failure."""
    message = _build_reset_email(to_email, to_name, reset_link, expire_minutes)
    _send(message, to_email)


# ============================================================
# Contact us / Request a demo notifications
# ------------------------------------------------------------
# Both forward the submitted details, by email, to NOTIFY_EMAIL
# (the same Gmail account configured above for password resets)
# so the team sees new leads without needing to check the DB.
# ============================================================

def _build_lead_notification_email(
    subject: str,
    heading: str,
    to_email: str,
    fields: list[tuple[str, str]],
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{MAIL_FROM_NAME} <{MAIL_FROM_EMAIL}>"
    msg["To"] = to_email

    text_lines = [f"{label}: {value}" for label, value in fields]
    msg.set_content("New submission from the OneNextGen Automation website.\n\n" + "\n".join(text_lines))

    rows_html = "".join(
        f"""
        <tr>
          <td style="padding:8px 12px;color:#8a97ab;font-size:12.5px;white-space:nowrap;vertical-align:top;">{label}</td>
          <td style="padding:8px 12px;color:#10202B;font-size:14px;">{value}</td>
        </tr>
        """
        for label, value in fields
    )

    msg.add_alternative(
        f"""\
<html>
  <body style="font-family: Arial, Helvetica, sans-serif; background:#F7F8FA; padding:24px;">
    <div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:14px;padding:32px;border:1px solid #e6e9ef;">
      <h2 style="color:#10202B;margin-top:0;">{heading}</h2>
      <table style="width:100%;border-collapse:collapse;">
        {rows_html}
      </table>
    </div>
  </body>
</html>
""",
        subtype="html",
    )

    return msg


def send_contact_message_notification(full_name: str, email: str, company_name: str, message: str) -> None:
    """Email the submitted 'Contact us' details to NOTIFY_EMAIL."""
    fields = [
        ("Name", full_name),
        ("Email", email),
        ("Company", company_name or "-"),
        ("Message", message.replace("\n", "<br/>")),
    ]
    email_message = _build_lead_notification_email(
        subject=f"New contact form submission from {full_name}",
        heading="New contact form submission",
        to_email=NOTIFY_EMAIL,
        fields=fields,
    )
    _send(email_message, NOTIFY_EMAIL)


def send_demo_request_notification(full_name: str, email: str, company_name: str, message: str) -> None:
    """Email the submitted 'Request a demo' details to NOTIFY_EMAIL."""
    fields = [
        ("Name", full_name),
        ("Email", email),
        ("Company", company_name),
        ("What they'd like to automate", (message or "-").replace("\n", "<br/>")),
    ]
    email_message = _build_lead_notification_email(
        subject=f"New demo request from {full_name} ({company_name})",
        heading="New demo request",
        to_email=NOTIFY_EMAIL,
        fields=fields,
    )
    _send(email_message, NOTIFY_EMAIL)

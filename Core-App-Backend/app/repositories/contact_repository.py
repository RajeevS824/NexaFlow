"""
app/repositories/contact_repository.py
-----------------------------------------------
Database access for the public "Contact us" and "Request a demo"
forms: insert submissions and flag whether the notification email
for each one was delivered.
"""
from app.database.connection import get_connection


def insert_contact_message(full_name: str, email: str, company_name: str, message: str) -> int:
    """Insert a ContactMessage row. Returns the new ContactMessageID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ContactMessage (FullName, Email, CompanyName, Message, EmailSent)
            VALUES (%s, %s, %s, %s, FALSE)
            RETURNING ContactMessageID
            """,
            (full_name, email, company_name or None, message),
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


def insert_demo_request(full_name: str, email: str, company_name: str, message: str) -> int:
    """Insert a DemoRequest row. Returns the new DemoRequestID."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO DemoRequest (FullName, Email, CompanyName, Message, EmailSent)
            VALUES (%s, %s, %s, %s, FALSE)
            RETURNING DemoRequestID
            """,
            (full_name, email, company_name, message or None),
        )
        row = cursor.fetchone()
        conn.commit()
        return int(row[0])
    finally:
        conn.close()


def mark_contact_message_email_sent(contact_message_id: int) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ContactMessage SET EmailSent = TRUE WHERE ContactMessageID = %s",
            (contact_message_id,),
        )
        conn.commit()
    finally:
        conn.close()


def mark_demo_request_email_sent(demo_request_id: int) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE DemoRequest SET EmailSent = TRUE WHERE DemoRequestID = %s",
            (demo_request_id,),
        )
        conn.commit()
    finally:
        conn.close()

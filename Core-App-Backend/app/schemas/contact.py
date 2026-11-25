"""
app/schemas/contact.py
-----------------------------------------------
Pydantic models for the public "Contact us" and "Request a demo"
forms on the marketing site. Both are unauthenticated endpoints.
"""
from pydantic import BaseModel, EmailStr, Field


class ContactMessageRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    company_name: str = Field(default="", max_length=200)
    message: str = Field(min_length=1)


class DemoRequestRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    company_name: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=4000)


class FormSubmitResponse(BaseModel):
    message: str

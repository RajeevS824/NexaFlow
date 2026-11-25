"""
app/services/analytics_service.py
-----------------------------------------------
Assembles the Admin Panel dashboard's analytics payload: real numbers
only, and only for products the organization has actually purchased
(licensed). A product with no license simply isn't included in the
response at all - never shown with fabricated or zeroed-out data.

There is deliberately no "Nextflow" / automations / AI-agent section
here: this codebase has no automation-execution or AI-agent engine
behind that product, so there is no real data source to report on.
Inventing numbers for it would violate the "real values only" goal,
so it's left out entirely rather than faked.
"""
from app.repositories.analytics_repository import (
    get_active_user_count,
    get_business_map_stats,
    get_document_parser_stats,
)
from app.repositories.auth_repository import get_org_licensed_products


def get_admin_dashboard_analytics(org_id: int) -> dict:
    """Return real, live-queried analytics for the admin's organization,
    scoped to only the products that organization currently licenses.
    """
    licensed_products = get_org_licensed_products(org_id)
    licensed_slugs = {p["slug"] for p in licensed_products}

    products: dict = {}

    if "document-parser" in licensed_slugs:
        stats = get_document_parser_stats(org_id)
        products["document-parser"] = {
            "available": stats is not None,
            **(stats or {}),
        }

    if "business-process-mapper" in licensed_slugs:
        stats = get_business_map_stats(org_id)
        products["business-process-mapper"] = {
            "available": stats is not None,
            **(stats or {}),
        }

    return {
        "active_users": get_active_user_count(org_id),
        "licensed_product_count": len(licensed_products),
        "licensed_products": [{"slug": p["slug"], "name": p["name"]} for p in licensed_products],
        "products": products,
    }

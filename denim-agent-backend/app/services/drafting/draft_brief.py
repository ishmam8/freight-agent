from typing import Dict, Any, Optional

from app.models.domain import Lead, EnrichedLead, SelectedContact


def choose_draft_mode(selected: SelectedContact) -> str:
    contact_type = (selected.selected_contact_type or "").lower()

    if contact_type == "founder":
        return "founder_outreach"
    if contact_type in {"senior_human", "human"}:
        return "relevant_contact_outreach"
    return "generic_inbox_outreach"


def get_cta_for_mode(draft_mode: str) -> str:
    if draft_mode == "founder_outreach":
        return "Would you be open to a quick conversation?"
    if draft_mode == "relevant_contact_outreach":
        return "Would you be open to a quick conversation?"
    return "If this is not the right inbox, could you point me to the best person to contact?"


def build_outreach_brief(
    lead: Lead,
    enriched: EnrichedLead,
    selected: SelectedContact,
    campaign_brief_dict: Dict[str, Any],
) -> Dict[str, Any]:
    draft_mode = choose_draft_mode(selected)
    
    # FIXED: Matching the exact keys from your CampaignBriefSchema
    category_hint = campaign_brief_dict.get("target_audience", "target companies")
    value_proposition = campaign_brief_dict.get("value_proposition", "our core offering")
    cta = get_cta_for_mode(draft_mode)

    # Safely grab the scraped context so the AI can write the personalized hook
    scraped_text = getattr(lead, "scraped_context", "")
    scraped_context_clean = scraped_text[:3000] if scraped_text else "No specific website data available."

    return {
        "recipient": {
            "name": selected.selected_contact_name,
            "title": selected.selected_contact_title,
            "email": selected.selected_email,
            "contact_type": selected.selected_contact_type,
        },
        "company": {
            "name": enriched.company_name,
            "website_url": enriched.website_url,
            "category_hint": category_hint,
            # THE MAGIC INGREDIENT:
            "scraped_website_context": scraped_context_clean
        },
        "campaign": {
            "value_proposition": value_proposition,
            "cta": cta,
            "tone": "casual, peer-to-peer, ultra-short",
        },
        "draft_mode": draft_mode,
        "rules": {
            "max_words": 75,
            "one_cta_only": True,
            "no_invented_facts": True,
            "no_pleasantries": True
        }
    }
[TECH] mailchimp-1
[OBJ] Email marketing + automation reference (2026). Closed-source SaaS ESP. Use via official API/SDK — do NOT vendor core code (proprietary). Free-first alternative in aiZee: Brevo / listmonk.
[DATA]
- Version/License: Proprietary SaaS. No OSS license. Free tier: 500 contacts, 1,000 sends/month (daily cap 500), single audience, no automation/advanced segmentation on free.
- Core Data Model: Audience (list) → Contact (member, with merge_fields/merge_tags) → Campaign (email/automation) → Template → Automation (Customer Journey) → Report (opens/clicks/unsubscribes). Tags + Segments (static/saved) for targeting.
- Free-tier/Limits: 500 contacts max; 1,000 emails/month; 500/day send cap; no A/B testing, no multivariate, no advanced segmentation, no phone/priority support. Paid from ~$13/mo (Essentials) for 500 contacts, unlocks journeys/segmentation.
[API]
- Base: `https://<dc>.api.mailchimp.com/3.0/` (dc = data center from API key). Auth: API key in basic auth (`anystring:<apikey>`).
- Key endpoints: `GET/POST /lists`, `POST /lists/{id}/members` (subscribe, status=pending|subscribed), `POST /campaigns`, `POST /campaigns/{id}/actions/send`, `GET /reports/{id}`, `POST /automations`.
- SDK: `mailchimp-marketing` (Node/Python). Official.
[CTX] Context7 ID: `websites/mailchimp_developer_marketing_api` 
[RTL]
- RTL note: Mailchimp editor supports `dir="rtl"` in custom HTML templates. Arabic content must set `<html dir="rtl" lang="ar">` + RTL-safe font (e.g. Cairo/Tajawal). Preview in inbox clients (Gmail iOS renders RTL well; Outlook needs explicit direction). Always right-align CTA for Arabic audiences. Subject/From must be UTF-8.
[PROHIBIT] ⛔ Never send without double opt-in / CAN-SPAM unsubscribe footer. ⛔ Do not vendor Mailchimp proprietary code. ⛔ No purchased lists (violates ToS + aiZee marketing-compliance gate).

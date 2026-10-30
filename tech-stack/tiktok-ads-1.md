[TECH] tiktok-ads-1
[OBJ] TikTok Ads (Marketing/BC) API (2026). Closed-source platform. Use via official API/SDK only. Free API; ad spend required + app approval.
[DATA]
- Version/License: Proprietary. Access via TikTok Business Center + developer app (scope `ads.manage`). Free API; ads need spend.
- Core Data Model: Advertiser → Campaign (objective: awareness/traffic/conversions) → AdGroup (audience/placement/budget/schedule) → Ad (video creative) → Creative → Report (metrics via async `report/task`).
- Free-tier/Limits: No free credits typically. API rate ~1,000 req/min per app. Sandbox advertiser for testing. Async reporting (task-based) for large pulls.
[API]
- Endpoint: `https://business-api.tiktok.com/open_api/v1.3/`. Auth: Bearer `<ACCESS_TOKEN>`. SDK: `tiktok-business-sdk` (Python/Node official).
- Key endpoints: `POST /campaign/create`, `POST /adgroup/create`, `POST /ad/create`, `POST /report/task/create` + `/report/task/download`.
[CTX] Context7 ID: `tiktok/tiktok-business-api-sdk` 
[RTL]
- RTL note: TikTok supports Arabic captions/creatives (RTL). Audience for MENA (Saudi/Egypt/UAE) growing fast. Creative must be vertical 9:16, <60s. Arabic voiceover/subtitles boost CTR. Set `locale` Arabic in dashboard; API reporting locale limited.
[PROHIBIT] ⛔ No ad launch without aiZee approval gate. ⛔ Creative policy strict (no misleading). ⛔ Don't vendor SDK.

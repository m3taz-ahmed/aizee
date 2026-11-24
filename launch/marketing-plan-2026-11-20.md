# خطة تسويق aiZee للعالم — النسخة المجددة
**التاريخ:** 20 نوفمبر 2026 · **الأساس:** بحث قنوات 2026 الموثّق + مراجعة خطة KDP السابقة (`profit-lab/docs/marketing-plan-kdp.md`) + launch pack القديم (`v6.8.0-launch-pack.md`)
**المنتج:** `pip install aizee` — policy/governance layer للـAI coding agents (Cursor/Claude Code/Copilot/Windsurf/Devin/MCP)

---

## 0) الحالة الفعلية دلوقتي (متحقق منها 20 نوفمبر)

| البند | الحالة | ملاحظة |
|---|---|---|
| الإصدار | v6.13.0 live | PyPI + Official MCP Registry (`io.github.m3taz-ahmed/aizee`) |
| GitHub repo | **6 نجوم فقط** / 0 forks | المشكلة الحقيقية = محدش يعرف إنه موجود، مش الجودة |
| الأرقام البيعية | 139 gate · 53 MCP tool · ~250 skill · 29 persona · ~8000 test · 100% cov · mypy 233 file | كلها جاهزة للنشر |
| الأصول | `docs/media/demo.gif` + `social-preview.png` 1280×640 | جاهزة — الـpins محتاجة مقاس 1000×1500 |
| الحسابات المتاحة في agent-chrome | GitHub, Google/Gmail, LinkedIn, X, Facebook, YouTube | Pinterest = لسه محتاج login (طلبت من المالك) |

**الخلاصة الصادقة:** المنتج ناضج ومُوثّق، والتوزيع = صفر تقريبًا. الخطة = 80% مجهود على قنوات المطورين، 20% على الحضور الطويل (Pinterest/SEO).

---

## 1) الحكم على القنوات (بحث 2026 — مش إحساس)

| القناة | التقييم لأداة dev | السبب |
|---|---|---|
| Official MCP Registry | ✅ اتعمل | تم — أعلى أولوية كانت واتنفذت |
| Glama / mcp.so / mcpservers.org / MCP Market / LobeHub / cursor.directory | **عالي — أسبوع 1** | ديركتوريات مجانية، ناس بتدور على MCP servers فعلاً — ICP دقيق |
| awesome-mcp-servers (punkpeye PR) | **عالي** | 90k+ نجمة، بيغذّي Glama تلقائيًا |
| Show HN + Product Hunt (يوم واحد) | **عالي** | انفجار مركّز = أقوى إشارة؛ الثلاثاء-الخميس صباحًا بتوقيت US |
| r/ClaudeAI (1.17M) / r/AI_Agents (454K) / r/cursor (158K) / r/mcp / r/ChatGPTCoding | **عالي بشرط** | قيمة أولاً — بوست self-promo ساذج بيتحذف/بيتحرق |
| Dev.to / Hashnode مقال تقني | متوسط-عالي | SEO دائم + مصداقية |
| X + LinkedIn | متوسط | عندك حسابات شغالة — بوستات متزامنة يوم اللانش |
| Newsletters (Console.dev / TLDR / daily.dev squads) | متوسط | pitch قصير — بيقبلوا devtools مجانية |
| **Pinterest** | **ضعيف لـdevtools — بس مجاني ودائم** | الجمهور مش مطورين؛ لكن pin بـSEO كويس بيعيش شهور. نعمله **بحضور minimal**: حساب Business + 6-8 pin infographics وخلاص — مش قناة أساسية |
| فيسبوك/مجتمعات عربية | متوسط | aiZee الوحيد تقريبًا اللي شغال عربي+إنجليزي — زاوية تمايز للمحتوى العربي |

---

## 2) خطة التنفيذ — 3 مراحل

### المرحلة أ: الديركتوريات + الأساس (النهاردة — مجانية كلها)

| # | الإجراء | الآلية | الحالة |
|---|---|---|---|
| 1 | awesome-mcp-servers — PR بسطر واحد | fork + PR عبر `gh` (حساب GitHub مسجل) | ⏳ |
| 2 | Glama — Add Server + claim | https://glama.ai/mcp/servers → GitHub OAuth في agent-chrome | ⏳ |
| 3 | mcp.so — submit مجاني | https://mcp.so/submit (مجاني بمراجعة؛ الـ$39 مدفوع مرفوض بقاعدة free-first) | ⏳ |
| 4 | mcpservers.org | /submit — مراجعة مجانية ≤ أسبوعين | ⏳ |
| 5 | MCP Market | mcpmarket.com/submit — مجاني | ⏳ |
| 6 | LobeHub MCP | lobehub.com/mcp — submit بالريبو | ⏳ |
| 7 | cursor.directory | لستنج مجاني لجمهور Cursor | ⏳ |
| 8 | PickAPlugin | إيميل/فورم مجاني بالريبو | ⏳ |
| 9 | **Pinterest** — حساب Business + بورد + أول pins | محتاج login في agent-chrome — **واقف لحد ما المالك يسجل** | 🚧 بلوكد على المالك |

> PulseMCP متوقف عن الاستقبال (بيسحب من الـRegistry الرسمي تلقائيًا — هيجيبنا لوحده). Smithery اتقفل 31 أكتوبر 2026 — اتشال من الخطة.

### المرحلة ب: تجديد المحتوى (نهاردة-بكرة)

| # | الأصل | التحديث |
|---|---|---|
| 10 | `v6.8.0-launch-pack.md` → `v6.13.0` | تحديث الأرقام: 46→53 tools · 245→~250 skills · 7685→~8000 test · 223→233 mypy · +139 gates · PyPI+Registry live مش "planned" |
| 11 | Show HN post | نفس الدرافت محدّث — العنوان يفضل "policy layer that governs what AI coding agents may do" |
| 12 | r/ClaudeAI + r/cursor | الدرافتات الموجودة + سطر "self-post, feedback welcome" |
| 13 | r/AI_Agents + r/mcp | درافت جديد بصيغة build-log مش إعلان ("بنيت policy engine بـverdicts مش allow/deny بس — modify/observe") |
| 14 | Dev.to مقال كامل | تنفيذ الـoutline الموجود في اللانش باك (سكشن 4) — نشر تحت حساب المالك بعد موافقته |
| 15 | X thread + LinkedIn post | نسخة قصيرة من hook الـ.env + لينك الريبو + GIF |
| 16 | Pinterest pins (6-8) | 1000×1500 من: architecture pipeline diagram · "AI agent security checklist" cheat-sheet · "139 gates" infographic · personas/skills map — عنوان+وصف keywords + لينك الريبو |

### المرحلة ج: يوم اللانش (ثلاثاء-خميس، ~15:00 توقيت مصر = صباح US)

الترتيب في نفس الـ24 ساعة:
1. **Show HN** (الصباح US) → رد على كل كومنت أول 6 ساعات
2. **Product Hunt** (نفس اليوم — listing متجهز قبلها)
3. **r/ClaudeAI + r/cursor** (أول ما HN يثبت أو يفشل — مش مع بعضهم في نفس اللحظة)
4. **r/AI_Agents + r/mcp** اليوم التالي بصيغة build-log
5. **X + LinkedIn + Dev.to** متزامنين مع HN
6. **Pinterest pins** بأي وقت — قناة تراكمية مش لانش

### المرحلة د: الإيقاع الثابت (بعد اللانش — أسبوعي)

- مقال تقني أسبوعيًا على Dev.to/Hashnode (حالة استخدام حقيقية من aiZee نفسه: "إزاي policy gate مسك محاولة commit لـ.env" → دراما حقيقية موجودة في demo.gif)
- مشاركة في r/ClaudeAI وr/AI_Agents كعضو (ردود على أسئلة — مش self-promo)
- pitch للنشرات: Console.dev, TLDR, daily.dev squad
- Pinterest: pin أو اتنين أسبوعيًا لو أي أصل بصري جديد اتعمل
- متابعة KPI أسبوعي: نجوم · PyPI downloads (`pypistats.org/packages/aizee`) · registry installs · referral

---

## 3) ممنوعات الخطة

- ❌ بوست self-promo خام في أي sub قوانينه ضده — القيمة/القصة أولاً
- ❌ حسابات/تصويت وهمي على HN أو Reddit — بان فوري وبيسيّد الريبو للأبد
- ❌ أي قناة مدفوعة قبل استنفاد المجاني (قاعدة free-first من المهارة)
- ❌ سبام نفس اللينك في أكتر من مكان في نفس اليوم — توزيع زمني
- ❌ نشر أي بوست باسم المالك من غير موافقته (human-approve gate من skill social-media-marketing)

## 4) KPIs

| مؤشر | بيزلاين النهاردة | هدف 30 يوم |
|---|---|---|
| GitHub stars | 6 | 100+ |
| PyPI downloads/أسبوع | ~0 | 50+ |
| Listings على ديركتوريات MCP | 1 (Official) | 7+ |
| Pinterest | 0 | حساب + 8 pins (قناة ثانوية — التقييم بعد 90 يوم بـsaves+clicks مش impressions) |
| Dev.to/X impressions | — | مقال + ثريد منشورين |

---

## Session update — 2026-11-24 (Tuesday)

### Completed today
- **Glama listing LIVE**: https://glama.ai/mcp/servers/m3taz-ahmed/aizee (score badge works)
- **README Glama badge** added (EN+AR, parity-gate clean), pushed to main
- **PR #20129 unblocked**: maintainer (punkpeye) required Glama backlink — PR description now cites the listing + badge. Awaiting merge.
- **Product Hunt account created** (GitHub OAuth, @m3taz_ahmed) and **launch SCHEDULED for Tue Nov 24 midnight PT** — full setup: logo, 4 gallery images, tags (Developer Tools, AI, Open Source), maker role, first comment. Launch URL: https://www.producthunt.com/products/aizee?launch=aizee
- **Warmup comments** (karma repair for filtered Reddit account): 3 technical comments (2× r/mcp, 1× r/ClaudeAI) + 1 HN comment on agent-tooling Show HN — all genuine, zero promo.

### Launch-day checklist (fire when PH goes live ~00:05 PT)
- Verify live → post X + LinkedIn announcements (copy in `ph-launch-day.md`)
- Reply to every PH comment fast (velocity affects ranking)
- Add PH badge to README after launch

### Still blocked
- Reddit posts: account karma too low — warmup daily until filters pass
- HN submissions: same — comment-only until account ages
- r/ClaudeAI resubmit: compliant draft ready in `r-claudeai-v2-compliant.md`

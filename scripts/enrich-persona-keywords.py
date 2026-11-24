#!/usr/bin/env python3
"""Enrich persona keywords in ``runtime/personas.yaml``.

Thin personas (~15-20 keywords) miss obvious prompts; broader multilingual
coverage (Arabic MSA + dialect + transliteration, plus high-signal
French/Spanish/German/Turkish/Russian/Chinese domain terms) shrinks the
``low_confidence`` gap before the semantic-override escalation has to fire.

Text-based insertion (NOT a yaml round-trip): the file's comments and
formatting are preserved — new ``- keyword`` lines are appended inside each
persona's existing ``keywords:`` block. Dedup is Arabic-normalized (reuses
``runtime.persona._normalize_arabic``). Idempotent: re-running adds nothing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from runtime.persona import _normalize_arabic  # noqa: E402

YAML = ROOT / "runtime" / "personas.yaml"

# New keywords per persona code. Curated: English synonyms, Arabic
# MSA/dialect/transliteration, and safe non-Latin-script multilingual terms.
# Deliberately avoids ultra-short generic words and bare cross-domain terms
# (e.g. "تطبيق" alone) that would blur persona boundaries.
EXPANSION: dict[str, list[str]] = {
    "ARCH": [
        "software architecture", "system architect", "tech lead", "technical lead",
        "clean architecture", "solid principles", "hexagonal architecture",
        "enterprise architecture", "architecture decision", "adr",
        "معماري برمجيات", "هندسة برمجيات", "تصميم معماري", "معماري النظم",
        "هيكل النظام", "بنية نظيفة", "كبير مهندسين", "مهندس رئيسي",
        "architecture logicielle", "Softwarearchitektur",
    ],
    "QA": [
        "test case", "test cases", "smoke test", "acceptance test", "test automation",
        "selenium", "playwright", "cypress", "vitest", "bug", "bugs",
        "assertion", "mock", "fixture", "verification", "validation",
        "فحص", "اختبارات", "اختبار برمجيات", "اختبار تلقائي", "حالة اختبار",
        "تاكد", "جودة", "دقة", "بج", "اتست", "اتشيك",
    ],
    "UX": [
        "user interface", "ui/ux", "ui design", "ux design", "design system",
        "web design", "website design", "responsive design", "css", "tailwind",
        "typography", "layout", "ui kit", "designer", "graphic design",
        "ديزاين", "ديزاينر", "مصمم", "مصمم واجهات", "واجهة", "واجهات",
        "واجهة مستخدم", "واجهه", "تجربة مستخدم", "يو اكس", "صفحة", "شاشة",
        "ألوان", "تايبوغرافي", "تخطيط", "نظام تصميم", "جرافيك", "تصميم جرافيك",
        "conception", "diseño", "tasarım", "entwurf", "дизайн", "设计",  # noqa: RUF001
    ],
    "DEV": [
        "developer", "development", "coding", "code", "programming", "programmer",
        "implementation", "fullstack", "backend development", "feature development",
        "build feature", "write code", "laravel", "php", "python", "javascript",
        "typescript", "كودينج", "برمجة", "مبرمج", "مطور", "تطوير", "باكند",
        "باك إند", "فرونت اند", "فرونت إند", "ديفيلوبر", "فول ستاك", "ديف",
        "وظيفة", "ديفيلوبمنت", "développeur", "desarrollador", "entwickler",
    ],
    "SRE": [
        "site reliability", "load balancer", "high availability", "datacenter",
        "infra", "cloud server", "linux server", "downtime", "deployment server",
        "cloudflare", "cdn", "سحابة", "كلاود", "داتا سنتر", "موازن تحميل",
        "توفر عالي", "انفراستراكشر", "انفرا", "سيرفر لينكس", "دونتايم",
        "استضافة مواقع", "وب هوستنج",
    ],
    "SEC": [
        "cybersecurity", "cyber security", "ethical hacking", "bug bounty",
        "vulnerability scan", "owasp", "sql injection", "xss", "csrf", "rce",
        "hardening", "penetration testing", "ssl", "tls", "secrets", "credential",
        "سايبر", "امن المعلومات", "امن سيبراني", "حماية", "اختراق اخلاقي",
        "اختبار اختراق", "جدار ناري", "شهادة ssl", "باونتي", "تقسية", "سكيورتي",
        "sécurité", "seguridad", "Sicherheit", "sicurezza", "güvenlik",
        "безопасность", "安全",
    ],
    "GAME": [
        "game dev", "game development", "game design", "godot", "level",
        "game character", "sprite", "tilemap", "unreal engine", "multiplayer",
        "game mechanic", "تطوير العاب", "تصميم لعبة", "محرك", "مستوى",
        "لعبة موبايل", "شخصية لعبة", "فيزياء لعبة", "العاب اونلاين",
        "لعب جماعي", "جيم", "جيم ديف",
    ],
    "PLAY": [
        "android", "google play store", "app store publish", "apk file",
        "aab file", "signing", "keystore", "app review", "app update",
        "store listing", "متجر", "متجر قوقل", "متجر جوجل", "رفع تطبيق",
        "تطبيق", "اندرويد", "ابليكيشن", "اصدار", "تحديث تطبيق", "مراجعة تطبيق",
        "توقيع تطبيق", "بلاي", "نشر ابك",
    ],
    "MOBILE": [
        "application", "apps", "ios app", "android app", "iphone", "cross platform",
        "native app", "hybrid app", "flutterflow", "swift", "kotlin", "app store",
        "mobile gaming", "تطبيقات", "ابليكيشن", "ايفون", "اندرويد", "جوال",
        "متعدد المنصات", "تطبيق اصلي", "تطبيق هجين", "موبايل جيمنج", "اب ستور",
    ],
    "DATA": [
        "mysql", "postgresql", "mongodb", "redis", "nosql", "data analysis",
        "data engineering", "database design", "business intelligence", "data lake",
        "db admin", "analytics data", "داتا", "ديتا", "داتابيس", "بيانات ضخمة",
        "تحليل بيانات", "تحليلات", "هندسة بيانات", "تصميم قاعدة بيانات",
        "ذكاء أعمال", "بحيرة بيانات", "ادارة قواعد بيانات", "ديبي",
    ],
    "ML": [
        "ai", "artificial intelligence", "transformers", "huggingface",
        "computer vision", "nlp", "neural", "prediction", "reinforcement",
        "ai model", "deep learning model", "ماشين ليرنينج", "تعلم آلي",
        "ارتيفيشيال", "نماذج", "نموذج تعلم آلي", "رؤية حاسوبية",
        "معالجة لغة طبيعية", "شبكات عصبية", "موديل ذكاء", "تنبؤ", "اي اي",
        "ذكاء", "machine intelligence",
    ],
    "DEVOPS": [
        "deploy", "deployment", "ci cd", "devsecops", "docker compose",
        "containers", "kubernetes", "automation", "release pipeline",
        "build automation", "yaml pipelines", "ديبلويمنت", "نشر", "بيبلاين",
        "حاويات", "كومبوز", "اوتوميشن", "بناء تلقائي", "خط نشر", "سيرفرات",
    ],
    "API": [
        "apis", "rest api", "web api", "api design", "http", "json", "endpoints",
        "middleware", "integrations", "sdk", "grpc", "restful", "api spec",
        "واجهة برمجية", "واجهات برمجية", "ايه بي اي", "ابي اي", "تصميم api",
        "تكاملات", "وسيط", "سبيسيفيكيشن",
    ],
    "LEGAL": [
        "law", "contract", "agreement", "terms", "policy", "regulations",
        "intellectual property", "copyright", "trademark", "terms and conditions",
        "legal review", "قانون", "اتفاقية", "عقد", "شروط", "سياسة",
        "سياسة خصوصية", "امتثال", "لوائح", "حقوق", "ملكية فكرية", "حقوق نشر",
        "علامة تجارية", "شروط واحكام", "مراجعة قانونية",
    ],
    "PRODUCT": [
        "product management", "backlog", "user stories", "stakeholder",
        "product owner", "prioritization", "product roadmap", "metrics", "kpi",
        "منتج", "ادارة منتج", "باك لوج", "قصص مستخدم", "اصحاب مصلحة",
        "مالك منتج", "اولويات", "خارطة منتج", "مقاييس", "مؤشرات", "برودكت مانجر",
    ],
    "DOC": [
        "docs", "document", "user guide", "manual", "instructions", "writeup",
        "technical docs", "documentation writer", "doc page", "knowledge base",
        "وثيقة", "دليل مستخدم", "تعليمات", "شرح", "كاتب تقني", "ملف توثيق",
        "تعليقات كود", "قاعدة معرفة", "دوكس", "دليل استخدام",
    ],
    "PERF": [
        "slow", "faster", "speed", "acceleration", "response time", "delay",
        "efficiency", "memory", "cpu usage", "slow query", "performance tuning",
        "بطء", "اداء ضعيف", "سريع", "اسرع", "تسريع", "زمن استجابة", "تأخير",
        "كفاءة", "ذاكرة", "استهلاك", "استعلام بطيء", "ضبط اداء",
    ],
    "CV": [
        "resume cv", "curriculum", "ats", "linkedin", "job", "career cv",
        "job hunting", "ريزيوميه", "سيره ذاتيه", "سيرة", "وظيفة", "تقديم وظيفة",
        "خطاب", "لينكد ان", "لينكدان", "بيانات شخصية", "توظيف", "سي في",
        "ريزومي", "بروفايل وظيفي",
    ],
    "FREELANCE": [
        "freelancing", "remote", "online work", "gig work", "upwork profile",
        "service pricing", "consultation", "freelance profile", "freelance work",
        "فري لانس", "فريلانس", "مستقلين", "عمل عن بعد", "ريموت", "اونلاين",
        "شغل حر", "فرص", "بروفايل فريلانس", "سعر خدمة", "تسعير خدمة",
        "استشارة", "حساب مستقل", "منصة عمل", "شغل اونلاين",
    ],
    "DEVX": [
        "dx tools", "developer tools", "ide", "editor", "plugin", "extension",
        "workflow", "automation tools", "terminal", "command line", "template",
        "dotfiles", "cli tool", "ادوات تطوير", "محرر", "بلجن", "اضافة",
        "سير عمل", "ترمينال", "سطر اوامر", "قالب", "اداة cli", "دوت فايلز",
    ],
    "MLOPS": [
        "model ops", "ai ops", "machine learning ops", "model pipeline",
        "ai deployment", "serving", "inference serving", "production model",
        "model lifecycle", "نشر نماذج", "تشغيل موديل", "خط انتاج موديل",
        "نشر ذكاء", "موديل برودكشن", "دورة حياة موديل", "ام الاوبس",
    ],
    "FINOPS": [
        "cost", "bill", "cloud bill", "savings", "cost reduction",
        "cloud pricing", "usage", "budget control", "cost report",
        "تكلفة", "فاتورة", "مصاريف سحابية", "توفير", "اقتصاد سحابي",
        "خفض تكاليف", "تسعير سحابي", "استهلاك سحابي", "ميزانية", "تقرير تكلفة",
    ],
    "MARKETING": [
        "digital", "media buying", "paid ads", "ppc", "cpc", "product marketing",
        "content marketing", "seo", "marketing plan", "promotion", "marcom",
        "ماركتنق", "ديجيتال ماركتنج", "ديجيتال", "سوشيال ماركتنج", "اعلان",
        "اعلانات مدفوعة", "ميديا باينج", "تسويق منتج", "تسويق محتوى", "سيو",
        "تحسين محركات", "تسويقي", "خطة تسويق", "استراتيجية تسويق", "برومو",
        "بروموشن", "publicité", "marketing digital",
    ],
    "GROWTH": [
        "growth loop", "k factor", "scaling growth", "user acquisition",
        "activation", "aarrr", "pirate metrics", "growth strategy", "viral loop",
        "جروث", "جرووث", "نموذج نمو", "انتشار فيروسي", "توسع",
        "اكتساب مستخدمين", "تنشيط", "استراتيجية نمو", "حلقة نمو", "فيرال",
    ],
    "BRAND": [
        "visual identity", "brand identity", "branding", "brand guidelines",
        "company logo", "brand strategy", "brand name", "slogan", "brand book",
        "هوية بصرية", "لوجو", "لوقو", "علامة تجارية", "برند", "هوية تجارية",
        "براندنج", "شعار الشركة", "هوية رقمية", "استراتيجية براند",
        "اسم تجاري", "سلوجن", "كتاب البراند",
    ],
    "EMAIL": [
        "emails", "newsletters", "email campaign", "smtp", "deliverability",
        "email list", "autoresponder", "email sequence", "mail marketing",
        "ايميل", "ايميلات", "إيميل", "تسويق بالبريد", "نشرة اخبارية",
        "ايميل ماركتنج", "كامبين ايميل", "تسليم بريد", "قائمة ايميلات",
        "رد تلقائي", "سلسلة ايميلات",
    ],
    "SOCIAL": [
        "social media manager", "account", "snapchat", "linkedin", "tweet",
        "followers", "engagement", "hashtag", "trending", "tik tok", "insta",
        "سوشيال", "سوشيال ميديا", "ميديا", "منشورات", "ادارة سوشيال",
        "حسابات", "انستجرام", "فيس بوك", "تيكتوك", "سناب شات", "لينكد إن",
        "تويت", "فولورز", "متابعين", "تفاعل", "ريل", "هاشتاج", "تريند",
    ],
    "CRO": [
        "conversion rate", "split test", "funnel optimization", "bounce rate",
        "conversion optimization", "page optimization", "conversion funnel",
        "سي ار او", "سيرو", "تحسين تحويل", "تجربة مقارنة", "نسبة تحويل",
        "تحويلات", "تحسين الصفحة", "معدل ارتداد", "قمع تحويل", "اب تيست",
    ],
    "SALES": [
        "crm", "pipeline sales", "cold call", "deal", "customer", "negotiation",
        "commission", "sales rep", "b2b sales", "sales funnel", "مندوب مبيعات",
        "سيلز", "بروسبكت", "عملاء", "عميل", "صفقة", "بيع", "تسويق مبيعات",
        "سي ار ام", "خط مبيعات", "مكالمة باردة", "اكتساب", "اقناع", "تفاوض",
        "عمولة",
    ],
}

PERSONA_BLOCK = re.compile(r"^  ([A-Z]+):\n", re.MULTILINE)
KEYWORDS_LINE = re.compile(r"^    keywords:\n", re.MULTILINE)
KEYWORD_ITEM = re.compile(r"^    -[^\S\n]+(.*?)[^\S\n]*$", re.MULTILINE)


def _insert_keywords(text: str, code: str, new_keywords: list[str]) -> str:
    """Append ``- kw`` lines inside ``  CODE:``'s ``keywords:`` block."""
    block = PERSONA_BLOCK.search(text)
    while block and block.group(1) != code:
        block = PERSONA_BLOCK.search(text, block.end())
    if not block:
        raise KeyError(f"persona block not found: {code}")
    start = block.end()
    next_block = PERSONA_BLOCK.search(text, start)
    end = next_block.start() if next_block else len(text)
    segment = text[start:end]

    kw_match = KEYWORDS_LINE.search(segment)
    if not kw_match:
        raise KeyError(f"keywords list not found in persona: {code}")
    kw_start = kw_match.end()
    # Collect only items contiguous with the keywords list — a later list at
    # the same indent (e.g. a trailing `skills:` block) must not be treated
    # as keyword entries or receive insertions.
    items: list[re.Match[str]] = []
    cursor = kw_start
    while True:
        line_end = segment.find("\n", cursor)
        if line_end == -1:
            line_end = len(segment)
        m = KEYWORD_ITEM.match(segment, cursor)
        if m and m.end() <= line_end:
            items.append(m)
            cursor = line_end + 1
        else:
            break
    existing = {_normalize_arabic(m.group(1)).lower() for m in items}
    # insert_at is segment-absolute: past the last item's newline, or right
    # after the `keywords:` line when the list is empty.
    if items:
        tail = items[-1].end()
        insert_at = tail + 1 if segment[tail:tail + 1] == "\n" else tail
    else:
        insert_at = kw_start

    additions = [
        kw for kw in new_keywords
        if _normalize_arabic(kw).lower() not in existing
    ]
    if not additions:
        return text
    lines = "".join(f"    - {kw}\n" for kw in additions)
    return text[: start + insert_at] + lines + text[start + insert_at:]


def main() -> int:
    text = YAML.read_text(encoding="utf-8")
    total = 0
    for code, kws in EXPANSION.items():
        before = text
        text = _insert_keywords(text, code, kws)
        added = (text.count("\n") - before.count("\n"))
        total += added
        print(f"{code}: +{added} keywords")
    YAML.write_text(text, encoding="utf-8", newline="\n")
    print(f"total: +{total} keywords")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

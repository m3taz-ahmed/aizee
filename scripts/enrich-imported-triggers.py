"""Enrich imported agent-skills with Arabic + domain-phrase triggers.

Imported skills (frontmatter contains ``metadata:`` — the agent-skills
standard marker absent from native aiZee skills) got heuristic EN-only
triggers. This pass adds Arabic glossary hits found in each skill's
description plus high-signal domain phrases, deduped against existing
triggers. Idempotent: re-running adds nothing new.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
DESC_RE = re.compile(r'^description:\s*"?(.*?)"?\s*$', re.MULTILINE)

# English term -> Arabic trigger(s). Covers the imported corpus domains:
# marketing/growth, dev, data, media, docs.
AR_GLOSSARY: dict[str, str] = {
    "seo": "تحسين محركات البحث",
    "conversion rate": "معدل التحويل",
    "cro": "تحسين معدل التحويل",
    "email marketing": "التسويق بالبريد",
    "cold email": "البريد البارد",
    "cold outreach": "التواصل البارد",
    "marketing": "تسويق",
    "growth": "نمو",
    "sales": "مبيعات",
    "pricing": "تسعير",
    "launch": "إطلاق",
    "onboarding": "تأهيل المستخدم",
    "signup": "تسجيل",
    "paywall": "جدار الدفع",
    "churn": "مغادرة العملاء",
    "referral": "إحالة",
    "brand": "هوية تجارية",
    "copywriting": "كتابة إعلانية",
    "landing page": "صفحة هبوط",
    "lead": "عميل محتمل",
    "analytics": "تحليلات",
    "attribution": "إسناد",
    "tracking": "تتبع",
    "backlink": "روابط خلفية",
    "keyword": "كلمة مفتاحية",
    "architecture": "معمارية",
    "code review": "مراجعة كود",
    "deploy": "نشر",
    "security": "أمان",
    "performance": "أداء",
    "database": "قاعدة بيانات",
    "debug": "تصحيح أخطاء",
    "documentation": "توثيق",
    "video": "فيديو",
    "design": "تصميم",
    "ux": "تجربة مستخدم",
    "dashboard": "لوحة تحكم",
    "auth": "مصادقة",
    "payment": "مدفوعات",
    "subscription": "اشتراك",
    "prospecting": "استكشاف العملاء",
    "community": "مجتمع",
    "influencer": "تسويق المؤثرين",
    "webinar": "ويبينار",
    "retrospective": "استرجاع",
    "brainstorm": "عصف ذهني",
    "reverse engineer": "هندسة عكسية",
    "prompt": "برومبت",
    "agent": "وكيل ذكاء اصطناعي",
    "spec": "مواصفات",
    "ticket": "تذكرة",
    "epic": "ملحمة",
    "story": "قصة مستخدم",
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "when", "user", "users", "use", "using", "want", "wants", "ask", "asks",
    "see", "this", "that", "from", "into", "your", "their", "its", "our",
    "can", "could", "should", "would", "will", "not", "no", "any", "all",
    "is", "are", "be", "been", "has", "have", "had", "do", "does", "did",
    "about", "over", "under", "than", "then", "them", "they", "you",
    "what", "which", "who", "how", "why", "if", "as", "at", "by", "it",
    "we", "he", "she", "i", "me", "my", "his", "her",
}

MAX_NEW_TRIGGERS = 12


def is_imported(fm: str) -> bool:
    return "metadata:" in fm


def parse_triggers(fm: str) -> tuple[list[str], int, int]:
    """Return (existing triggers, block start offset, block end offset)."""
    m = re.search(r"^triggers:\n((?:  - .*\n)+)", fm, re.MULTILINE)
    if not m:
        return [], -1, -1
    items = [line.strip()[2:].strip().strip('"').strip("'") for line in m.group(1).splitlines()]
    return items, m.start(1), m.end(1)


def candidate_triggers(description: str) -> list[str]:
    desc = description.lower()
    found: list[str] = []
    for en, ar in AR_GLOSSARY.items():
        if re.search(r"\b" + re.escape(en) + r"\b", desc):
            found.append(ar)
    # EN domain phrases: 2-3 word sequences with a domain-ish head word
    words = re.findall(r"[a-z][a-z0-9-]{2,}", desc)
    phrases: list[str] = []
    for i in range(len(words) - 1):
        pair = f"{words[i]} {words[i + 1]}"
        if all(w not in STOPWORDS for w in pair.split()) and not any(
            c.isdigit() for c in pair
        ):
            phrases.append(pair)
    seen: set[str] = set()
    out: list[str] = []
    for t in found + phrases:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            out.append(t)
    return out[:MAX_NEW_TRIGGERS]


def enrich(path: Path) -> str:
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    m = FM_RE.match(text)
    if not m or not is_imported(m.group(1)):
        return "skip"
    fm = m.group(1)
    existing, bstart, bend = parse_triggers(fm)
    dm = DESC_RE.search(fm)
    description = dm.group(1) if dm else path.parent.name.replace("-", " ")
    have = {t.lower() for t in existing}
    new = [t for t in candidate_triggers(description) if t.lower() not in have]
    if not new:
        return "skip"
    if bstart >= 0:
        extra = "".join(f"  - {t}\n" for t in new)
        new_fm = fm[:bend] + extra + fm[bend:]
    else:
        # no triggers block: append one at end of frontmatter
        block_lines = "triggers:\n" + "".join(f"  - {t}\n" for t in new)
        new_fm = fm.rstrip("\n") + "\n" + block_lines
    new_text = text[: m.start(1)] + new_fm + text[m.end(1) :]
    path.write_bytes(new_text.replace("\n", eol).encode("utf-8"))
    return f"+{len(new)}"


def main() -> None:
    changed = skipped = 0
    for skill_md in sorted(SKILLS.rglob("SKILL.md")):
        result = enrich(skill_md)
        if result == "skip":
            skipped += 1
        else:
            changed += 1
            print(f"{result:>5}  {skill_md.parent.name}")
    print(f"enriched={changed} skipped={skipped}")


if __name__ == "__main__":
    main()

"""Add Arabic triggers to vendored BMAD skills (bmad-*/bmod-*).

BMAD skills carry EN-only triggers from upstream. This pass appends
curated Arabic triggers per skill so Arabic requests route correctly.
Idempotent: existing triggers are preserved and deduped.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILLS = Path(__file__).resolve().parent.parent / "skills"
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)

# skill dir name -> Arabic triggers to add
AR: dict[str, list[str]] = {
    "bmad": ["بي ماد", "bmad help", "إعداد bmad"],
    "bmad-agent-analyst": ["ماري", "محلل أعمال", "أبحاث سوق", "تحليل منافسين", "موجز"],
    "bmad-agent-architect": ["وينستون", "مهندس معماري", "معمارية تقنية", "قرار معماري"],
    "bmad-agent-dev": ["أميليا", "مطورة", "تنفيذ قصة", "اكتب كود"],
    "bmad-agent-pm": ["جون", "مدير منتج", "خطة منتج", "وثيقة متطلبات"],
    "bmad-agent-po": ["صوفيا", "مالك منتج", "قصص مستخدم", "ملحمات", "Epic", "Story"],
    "bmad-agent-ux-designer": ["سالي", "مصممة تجربة", "تصميم UX", "تجربة مستخدم"],
    "bmad-architecture": ["وثيقة معمارية", "معمارية الحل", "قرار معماري ADR"],
    "bmad-brainstorming": ["عصف ذهني", "توليد أفكار", "أفكار"],
    "bmad-build": ["نفذ القصة", "ابني الميزة", "تنفيذ متكامل", "story implementation"],
    "bmad-build-auto": ["تنفيذ تلقائي", "بناء بدون إشراف"],
    "bmad-code-review": ["مراجعة كود", "مراجعة PR", "مراجعة متعددة"],
    "bmad-customize": ["تخصيص bmad", "تعديل سلوك الوكيل", "customize.toml"],
    "bmad-deep-recon": ["بحث معمق", "استطلاع تقني", "دراسة أدبيات", "بحث دومين"],
    "bmad-eval": ["تقييم مهارة", "معيار مهارة", "دقة التفعيل"],
    "bmad-facilitate": ["تسهيل", "إنشاء وثيقة", "التحقق من وثيقة"],
    "bmad-forge-idea": ["تشكيل فكرة", "اختبار فكرة", "تقوية فكرة"],
    "bmad-ingest": ["تفريغ اجتماع", "ملاحظات اجتماع", "تفريغ صوتي"],
    "bmad-party-mode": ["نقاش جماعي", "حلقة نقاش", "تركيز جماعي", "مجلس"],
    "bmad-project-context": ["سياق المشروع", "تعليمات الوكلاء", "AGENTS.md"],
    "bmad-qa-generate-e2e-tests": ["اختبارات نهاية إلى نهاية", "اختبارات API", "تغطية آلية"],
    "bmad-retrospective": ["استرجاع", "دروس مستفادة", "مراجعة ملحمة"],
    "bmad-review": ["مراجعة diff", "مراجعة معمارية", "مراجعة عدائية"],
    "bmad-shard-pro": ["تقسيم وثيقة", "فهرس", "وثيقة طويلة"],
    "bmad-toolsmith": ["صناعة مهارة", "بناء وكيل", "scaffold skill"],
    "bmad-ux": ["رؤية UX", "وثائق تجربة المستخدم", "design.md"],
    "bmad-walkthrough": ["مراجعة إرشادية", "دليل مراجعة", "مراجعة commit"],
}

GENERIC = ["bmad", "بي ماد"]


def enrich(path: Path, extra: list[str]) -> str:
    raw = path.read_bytes().decode("utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    m = FM_RE.match(text)
    if not m:
        return "skip"
    fm = m.group(1)
    tm = re.search(r"^triggers:\n((?:  - .*\n)+)", fm, re.MULTILINE)
    if tm:
        existing = {line.strip()[2:].strip().lower() for line in tm.group(1).splitlines()}
        new = [t for t in extra if t.lower() not in existing]
        if not new:
            return "skip"
        block = tm.group(1) + "".join(f"  - {t}\n" for t in new)
        new_fm = fm[: tm.start(1)] + block + fm[tm.end(1) :]
    else:
        new_fm = fm.rstrip("\n") + "\ntriggers:\n" + "".join(f"  - {t}\n" for t in extra)
    new_text = text[: m.start(1)] + new_fm + text[m.end(1) :]
    path.write_bytes(new_text.replace("\n", eol).encode("utf-8"))
    return f"+{len(extra if tm is None else new)}"


def main() -> None:
    changed = skipped = 0
    for skill_md in sorted(SKILLS.glob("bmad*/SKILL.md")) + sorted(
        SKILLS.glob("bmod*/SKILL.md")
    ):
        name = skill_md.parent.name
        extra = list(AR.get(name, []))
        if name not in AR:
            extra = GENERIC
        result = enrich(skill_md, extra)
        if result == "skip":
            skipped += 1
        else:
            changed += 1
            print(f"{result:>5}  {name}")
    print(f"enriched={changed} skipped={skipped}")


if __name__ == "__main__":
    main()

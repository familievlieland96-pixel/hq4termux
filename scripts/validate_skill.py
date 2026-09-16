#!/usr/bin/env python3
"""validate_skill.py - Gate validator for generated/drafted skills.

Rejects hollow draft skills that contain placeholder / edit-me / todo lines.
Exit 0 = clean (pipeline continues). Exit 1 = hollow (pipeline fails loudly).

Usage: python3 validate_skill.py <skill-file.md>
"""
import argparse
import re
import sys
from pathlib import Path

HOLLOW_PATTERNS = [
    r"\[edit\s+me\]",
    r"\[fill\s+from\s+transcript\]",
    r"\[fill\s+this\s+in\]",
    r"\[todo\]",
    r"\[tbd\]",
    r"\[replace\s+with",
    r"\[insert\s+(real|actual|specific|correct)",
    r"skill\s+to\s+be\s+implemented",
    r"work\s+in\s+progress",
    r"draft\s*-\s*human\s+review\s+required",
    r"not\s+yet\s+implemented",
]


def validate(skill_path: Path) -> tuple[bool, list[str]]:
    if not skill_path.exists():
        return False, [f"File not found: {skill_path.name}"]
    try:
        content = skill_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, [f"Cannot read file: {e}"]
    errors = []
    for pattern in HOLLOW_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            errors.append(f"Hollow placeholder found ('{pattern}'): {matches[0]}")
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if len(lines) < 10:
        errors.append(f"Skill too short: {len(lines)} lines (need at least 10)")
    if not content.strip().startswith("---"):
        errors.append("Missing YAML frontmatter (---)")
    if not re.search(r"^name:\s*\S", content, re.MULTILINE):
        errors.append("Missing 'name:' field in frontmatter")
    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Gate validator for hq4termux skills")
    parser.add_argument("skill_file", help="Path to skill .md file to validate")
    args = parser.parse_args()
    clean, errors = validate(Path(args.skill_file))
    if clean:
        print(f"PASS: {args.skill_file} - skill looks valid")
        sys.exit(0)
    print(f"FAIL: {args.skill_file} - {len(errors)} issue(s):")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)


if __name__ == "__main__":
    main()

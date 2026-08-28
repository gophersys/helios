"""Every repo-relative path cited in the .claude skills must resolve.

The skills were re-anchored from ~/.claude copies by an automated
substitution that mangled 11 reference lines into non-paths
(`framework/ (this repo) — DENSE-UI.md`). An agent following a skill with a
dangling reference silently loses the document the step depends on. This
walks every backticked `framework/...` or `demos/...` token in the skills
and asserts it exists — the same sweep that caught the mangle.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[3]
SKILLS = sorted((REPO / ".claude" / "skills").rglob("SKILL.md"))


def test_skills_exist():
    assert len(SKILLS) == 3, f"expected 3 skills, found {[str(s) for s in SKILLS]}"


def test_cited_repo_paths_resolve():
    dangling = []
    for skill in SKILLS:
        for token in re.findall(r"`([^`\n]+)`", skill.read_text()):
            cited = token.startswith(("framework/", "demos/", "docs/", "tools/"))
            if cited and not (REPO / token.rstrip("/")).exists():
                dangling.append(f"{skill.parent.name}: {token}")
    assert not dangling, f"dangling repo paths in skills: {dangling}"

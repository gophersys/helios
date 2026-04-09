#!/usr/bin/env python3
"""Generate role-manifest.json from docs page frontmatter.

Standalone script (not an mkdocs hook) that scans docs/ for min_role
frontmatter and writes the manifest to the site output directory.
Run after zensical build or mkdocs build.

Usage:
    python3 hooks/generate_role_manifest.py
"""

import json
import os
import re
import sys

ROLE_HIERARCHY = {"OPERATOR": 1, "DEVELOPER": 2, "MAINTAINER": 3, "ADMIN": 4}


def generate(docs_dir: str, site_dir: str) -> int:
    manifest: dict[str, dict] = {}
    exclude = {"_internal", "_archive"}

    for root, dirs, files in os.walk(docs_dir):
        dirs[:] = [d for d in dirs if d not in exclude]
        for f in files:
            if not f.endswith(".md"):
                continue
            path = os.path.join(root, f)
            with open(path) as fh:
                content = fh.read(500)

            m = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if not m:
                continue
            for line in m.group(1).split("\n"):
                if line.strip().startswith("min_role:"):
                    role = line.split(":", 1)[1].strip()
                    if role in ROLE_HIERARCHY:
                        rel = os.path.relpath(path, docs_dir)
                        url = "/" + rel.replace("\\", "/").replace(".md", "/")
                        url = url.replace("/index/", "/")
                        manifest[url] = {
                            "min_role": role,
                            "min_level": ROLE_HIERARCHY[role],
                        }
                    break

    output = {"pages": manifest, "role_hierarchy": ROLE_HIERARCHY}
    os.makedirs(site_dir, exist_ok=True)
    manifest_path = os.path.join(site_dir, "role-manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(output, fh, indent=2)

    print(f"role-manifest.json: {len(manifest)} pages")
    return len(manifest)


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs_dir = os.path.join(repo_root, "docs")
    site_dir = os.path.join(repo_root, "apps", "frontend", "docs", "site")
    generate(docs_dir, site_dir)

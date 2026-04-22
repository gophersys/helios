"""MkDocs hook that generates role-manifest.json from page frontmatter.

Each page can specify `min_role` in its YAML frontmatter (OPERATOR,
DEVELOPER, MAINTAINER, ADMIN). This hook collects every tagged page
and writes a JSON manifest into the site output at build time.
Client-side JavaScript uses the manifest to filter navigation.

Usage in mkdocs.yml:
    hooks:
      - hooks/role_filter.py
"""

import json
import os

ROLE_HIERARCHY = {
    "OPERATOR": 1,
    "DEVELOPER": 2,
    "MAINTAINER": 3,
    "ADMIN": 4,
}

_manifest: dict[str, dict] = {}


def on_page_markdown(markdown, page, config, files):
    """Collect min_role from each page's frontmatter."""
    meta = page.meta or {}
    min_role = meta.get("min_role")
    if min_role and min_role in ROLE_HIERARCHY:
        url = page.url
        if not url.startswith("/"):
            url = f"/{url}"
        _manifest[url] = {
            "min_role": min_role,
            "min_level": ROLE_HIERARCHY[min_role],
        }
    return markdown


def on_post_build(config):
    """Write the collected manifest to role-manifest.json in the site output."""
    site_dir = config["site_dir"]
    manifest_path = os.path.join(site_dir, "role-manifest.json")
    output = {
        "pages": _manifest,
        "role_hierarchy": ROLE_HIERARCHY,
    }
    with open(manifest_path, "w") as f:
        json.dump(output, f, indent=2)

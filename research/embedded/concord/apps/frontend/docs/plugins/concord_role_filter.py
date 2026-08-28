"""MkDocs plugin that generates role-manifest.json from page frontmatter.

Each page can specify a `min_role` in its YAML frontmatter (OPERATOR,
DEVELOPER, MAINTAINER, ADMIN).  At build time this plugin collects every
tagged page and writes a JSON manifest into the site output.  Client-side
JavaScript then uses the manifest to filter navigation by the logged-in
user's role.
"""

import json
import os

from mkdocs.plugins import BasePlugin

ROLE_HIERARCHY = {
    "OPERATOR": 1,
    "DEVELOPER": 2,
    "MAINTAINER": 3,
    "ADMIN": 4,
}


class ConcordRoleFilter(BasePlugin):
    """Collect min_role metadata and emit role-manifest.json."""

    def __init__(self):
        super().__init__()
        self.manifest: dict[str, dict] = {}

    def on_page_markdown(self, markdown, page, config, files):
        meta = page.meta or {}
        min_role = meta.get("min_role")
        if min_role and min_role in ROLE_HIERARCHY:
            url = page.url
            if not url.startswith("/"):
                url = f"/{url}"
            self.manifest[url] = {
                "min_role": min_role,
                "min_level": ROLE_HIERARCHY[min_role],
            }
        return markdown

    def on_post_build(self, config):
        site_dir = config["site_dir"]
        manifest_path = os.path.join(site_dir, "role-manifest.json")
        output = {
            "pages": self.manifest,
            "role_hierarchy": ROLE_HIERARCHY,
        }
        with open(manifest_path, "w") as f:
            json.dump(output, f, indent=2)

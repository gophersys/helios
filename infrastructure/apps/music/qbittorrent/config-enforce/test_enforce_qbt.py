"""TDD spec for enforce_qbt.enforce_config.

Run: python3 -m pytest -q   (or: python3 test_enforce_qbt.py)

The function idempotently ensures a set of (section, key) = value entries in a
qBittorrent.conf, surgically — every unrelated line is preserved byte-for-byte,
and running it twice is a no-op.
"""
import unittest

from enforce_qbt import enforce_config, REQUIRED


def kv(text, section, key):
    """Pull a key's value from within a section (test helper, not prod code)."""
    cur, out = None, {}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1]
        elif "=" in line and cur == section:
            k, v = line.split("=", 1)
            if k.strip() == key:
                out = v.strip()
    return out


class EnforceConfig(unittest.TestCase):
    def test_empty_input_creates_all_required(self):
        out = enforce_config("")
        for section, kvs in REQUIRED.items():
            for key, val in kvs.items():
                self.assertEqual(kv(out, section, key), val,
                                 f"{section}/{key} missing from empty input")

    def test_wrong_value_is_corrected(self):
        src = "[BitTorrent]\nSession\\Interface=eth0\n"
        out = enforce_config(src)
        self.assertEqual(kv(out, "BitTorrent", "Session\\Interface"), "tun0")

    def test_missing_key_inserted_into_existing_section(self):
        src = "[Preferences]\nWebUI\\Port=8080\n"
        out = enforce_config(src)
        self.assertEqual(kv(out, "Preferences", "WebUI\\LocalHostAuth"), "false")
        # unrelated key preserved
        self.assertEqual(kv(out, "Preferences", "WebUI\\Port"), "8080")

    def test_missing_section_is_created(self):
        out = enforce_config("[Meta]\nMigrationVersion=6\n")
        self.assertEqual(kv(out, "BitTorrent", "Session\\Interface"), "tun0")
        # unrelated section untouched
        self.assertEqual(kv(out, "Meta", "MigrationVersion"), "6")

    def test_idempotent(self):
        once = enforce_config("")
        twice = enforce_config(once)
        self.assertEqual(once, twice, "second pass must be a no-op")

    def test_unrelated_lines_preserved_verbatim(self):
        src = ("[LegalNotice]\nAccepted=true\n\n"
               "[BitTorrent]\nSession\\Port=6881\n"
               "Session\\Interface=eth0\n")
        out = enforce_config(src)
        self.assertIn("[LegalNotice]", out)
        self.assertIn("Accepted=true", out)
        self.assertIn("Session\\Port=6881", out)   # sibling key untouched
        self.assertEqual(kv(out, "BitTorrent", "Session\\Interface"), "tun0")

    def test_no_duplicate_keys_after_run(self):
        out = enforce_config(enforce_config("[Preferences]\n"))
        count = sum(
            1 for ln in out.splitlines()
            if ln.split("=", 1)[0].strip() == "WebUI\\LocalHostAuth"
        )
        self.assertEqual(count, 1, "key must appear exactly once")

    def test_committed_configmap_matches_generated(self):
        # drift guard: the deployed ConfigMap must equal the renderer's output,
        # so the .py stays the single source of truth.
        import os
        import gen_configmap
        if not os.path.exists(gen_configmap.CONFIGMAP_PATH):
            self.skipTest("configmap not generated yet")
        with open(gen_configmap.CONFIGMAP_PATH, encoding="utf-8") as f:
            committed = f.read()
        self.assertEqual(committed, gen_configmap.render(),
                         "ConfigMap drifted from enforce_qbt.py — run "
                         "`python3 gen_configmap.py > ../15-config-enforce.configmap.yaml`")

    def test_required_set_matches_intent(self):
        # guardrail: the exact settings we reconcile (see debt-register D1)
        self.assertEqual(REQUIRED["BitTorrent"]["Session\\Interface"], "tun0")
        self.assertEqual(REQUIRED["BitTorrent"]["Session\\InterfaceName"], "tun0")
        self.assertEqual(
            REQUIRED["Preferences"]["WebUI\\AuthSubnetWhitelist"], "10.42.0.0/16")
        self.assertEqual(
            REQUIRED["Preferences"]["WebUI\\AuthSubnetWhitelistEnabled"], "true")
        self.assertEqual(REQUIRED["Preferences"]["WebUI\\LocalHostAuth"], "false")


if __name__ == "__main__":
    unittest.main(verbosity=2)

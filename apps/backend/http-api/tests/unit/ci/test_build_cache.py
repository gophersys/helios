"""Tests for build cache / fingerprinting."""
import pytest
from api.v2.ci.build_cache import compute_build_fingerprint


class TestBuildFingerprint:
    def test_deterministic(self):
        fp1 = compute_build_fingerprint("repo", "abc123", "alpha_b0", "debug")
        fp2 = compute_build_fingerprint("repo", "abc123", "alpha_b0", "debug")
        assert fp1 == fp2

    def test_different_commit_different_fingerprint(self):
        fp1 = compute_build_fingerprint("repo", "abc123", "alpha_b0", "debug")
        fp2 = compute_build_fingerprint("repo", "def456", "alpha_b0", "debug")
        assert fp1 != fp2

    def test_different_variant_different_fingerprint(self):
        fp1 = compute_build_fingerprint("repo", "abc123", "alpha_b0", "debug")
        fp2 = compute_build_fingerprint("repo", "abc123", "alpha_b0", "release")
        assert fp1 != fp2

    def test_config_flags_affect_fingerprint(self):
        fp1 = compute_build_fingerprint("repo", "abc", "b0", "debug", {"harness": True})
        fp2 = compute_build_fingerprint("repo", "abc", "b0", "debug", {"harness": False})
        assert fp1 != fp2

    def test_config_flags_order_independent(self):
        fp1 = compute_build_fingerprint("repo", "abc", "b0", "debug", {"a": 1, "b": 2})
        fp2 = compute_build_fingerprint("repo", "abc", "b0", "debug", {"b": 2, "a": 1})
        assert fp1 == fp2

    def test_none_flags_same_as_empty(self):
        fp1 = compute_build_fingerprint("repo", "abc", "b0", "debug", None)
        fp2 = compute_build_fingerprint("repo", "abc", "b0", "debug", {})
        assert fp1 == fp2

    def test_returns_hex_string(self):
        fp = compute_build_fingerprint("repo", "abc", "b0", "debug")
        assert len(fp) == 64  # SHA-256 hex
        assert all(c in "0123456789abcdef" for c in fp)

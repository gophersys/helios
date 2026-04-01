"""Request dataclasses for CI/Build endpoints following the from_json() pattern."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BitbucketWebhookPayload:
    """Parsed Bitbucket Server webhook payload."""
    event_key: str
    repo_slug: str
    project_key: str
    branch: str
    commit_sha: str
    pr_id: Optional[int] = None
    pr_title: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BitbucketWebhookPayload"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        event_key = data.get("eventKey", "")
        if not event_key:
            return None, "eventKey is required"

        # Extract repository info
        repository = data.get("repository", {})
        repo_slug = repository.get("slug", "")
        project = repository.get("project", {})
        project_key = project.get("key", "")

        if not repo_slug:
            return None, "repository.slug is required"

        # Extract branch and commit based on event type
        branch = ""
        commit_sha = ""
        pr_id = None
        pr_title = None

        if event_key.startswith("pr:"):
            # Pull request events
            pr = data.get("pullRequest", {})
            pr_id = pr.get("id")
            pr_title = pr.get("title")

            from_ref = pr.get("fromRef", {})
            branch = from_ref.get("displayId", "")
            commit_sha = from_ref.get("latestCommit", "")

        elif event_key == "repo:refs_changed":
            # Push events
            changes = data.get("changes", [])
            if changes:
                change = changes[0]
                ref_id = change.get("ref", {}).get("id", "")
                # Extract branch name from refs/heads/xxx
                if ref_id.startswith("refs/heads/"):
                    branch = ref_id[len("refs/heads/"):]
                else:
                    branch = change.get("ref", {}).get("displayId", ref_id)
                commit_sha = change.get("toHash", "")

        if not branch:
            return None, "Could not extract branch from webhook payload"

        return cls(
            event_key=event_key,
            repo_slug=repo_slug,
            project_key=project_key,
            branch=branch,
            commit_sha=commit_sha,
            pr_id=pr_id,
            pr_title=pr_title,
            raw=data,
        ), None


@dataclass
class CiTriggerRequest:
    """Manual CI trigger request — same pipeline flow, no HMAC check."""
    product_id: str
    repo_slug: str
    branch: str
    variant: str = "debug"
    mtib_rev: str = "1.2"
    commit_sha: Optional[str] = None
    firmware_version: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["CiTriggerRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        product_id = (data.get("productId") or "").strip()
        if not product_id:
            return None, "productId is required"

        repo_slug = (data.get("repoSlug") or "").strip()
        if not repo_slug:
            return None, "repoSlug is required"

        branch = (data.get("branch") or "").strip()
        if not branch:
            return None, "branch is required"

        variant = (data.get("variant") or "debug").strip()
        # Both debug and release variants are valid
        # release maps to "no_debug" folder in artifacts
        if variant not in ("debug", "release"):
            return None, "variant must be 'debug' or 'release'"

        mtib_rev = (data.get("mtibRev") or "1.2").strip()

        commit_sha = data.get("commitSha")
        if commit_sha:
            commit_sha = commit_sha.strip()

        firmware_version = data.get("firmwareVersion")
        if firmware_version:
            firmware_version = firmware_version.strip()

        return cls(
            product_id=product_id,
            repo_slug=repo_slug,
            branch=branch,
            variant=variant,
            mtib_rev=mtib_rev,
            commit_sha=commit_sha,
            firmware_version=firmware_version,
        ), None


@dataclass
class BuildCreateRequest:
    """Trigger a manual firmware build."""

    product: str
    board: str
    target: str
    variant: str
    branch: str
    mtib_rev: str = "1.2"
    commit_sha: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    version_override: Optional[str] = None
    trigger_type: str = "worker"
    notes: Optional[str] = None
    product_id: Optional[str] = None
    initial_status: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BuildCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        trigger_type = (data.get("triggerTypes") or "worker").strip()
        if trigger_type not in ("worker", "manual", "webhook"):
            return None, "triggerTypes must be one of: worker, manual, webhook"

        product_id = (data.get("productId") or "").strip() or None

        product = (data.get("product") or "").strip()
        if not product and not product_id:
            return None, "product or productId is required"

        if trigger_type == "manual" and not product and not product_id:
            return None, "manual builds require product or productId"

        board = (data.get("board") or "").strip()
        if not board:
            return None, "board is required"

        target = (data.get("target") or "").strip()
        if not target:
            return None, "target is required"

        variant = (data.get("variant") or "release").strip()
        if variant not in ("release", "debug"):
            return None, "variant must be 'release' or 'debug'"

        branch = (data.get("branch") or "").strip()
        if not branch:
            return None, "branch is required"

        mtib_rev = (data.get("mtibRev") or "1.2").strip()

        commit_sha = data.get("commitSha")
        if commit_sha is not None:
            commit_sha = commit_sha.strip() or None

        config = data.get("config")
        if config is not None and not isinstance(config, dict):
            return None, "config must be an object"

        version_override = data.get("versionOverride") or data.get("firmwareVersion")
        if version_override:
            version_override = str(version_override).strip()

        notes = data.get("notes")
        if notes is not None:
            notes = str(notes).strip() or None

        initial_status = (data.get("initialStatus") or "").strip() or None
        if initial_status is not None and initial_status != "SUCCESS":
            return None, "initialStatus must be 'SUCCESS' or omitted"

        return cls(
            product=product,
            board=board,
            target=target,
            variant=variant,
            branch=branch,
            mtib_rev=mtib_rev,
            commit_sha=commit_sha,
            config=config,
            version_override=version_override,
            trigger_type=trigger_type,
            notes=notes,
            product_id=product_id,
            initial_status=initial_status,
        ), None


@dataclass
class PipelineCreateRequest:
    """Create a CI pipeline (build -> validate chain).

    Can be triggered manually (product name) or by git poller (productId).
    Git poller also provides repoSlug and commitSha for traceability.
    """

    product: str  # Product name or repo slug
    board: str
    branch: str
    product_id: Optional[str] = None  # DB product ID (from git poller)
    repo_slug: Optional[str] = None   # Git repo slug (from git poller)
    commit_sha: Optional[str] = None  # Commit SHA (from git poller)
    trigger_type: str = "manual"      # manual, poller, webhook
    mfg_repo_slug: Optional[str] = None  # Manufacturing firmware repo
    mfg_ssh_url: Optional[str] = None    # Manufacturing firmware SSH URL
    name: Optional[str] = None
    build_variant: str = "debug"
    validation_config: Optional[Dict[str, Any]] = None
    # Build matrix options: smoke(1), silicon(1), integration(1), nightly(2), fuota(8)
    matrix_mode: str = "fuota"
    main_commit: Optional[str] = None  # Main branch commit for comparison
    pr_branch: Optional[str] = None    # PR branch name
    auto_validate: bool = False        # Auto-trigger validation on all builds passing

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["PipelineCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        # Product can be specified by ID (git poller) or name (manual)
        product_id = (data.get("productId") or "").strip() or None
        repo_slug = (data.get("repoSlug") or "").strip() or None
        product = (data.get("product") or repo_slug or "").strip()
        if not product and not product_id:
            return None, "product or productId is required"

        board = (data.get("board") or "").strip()
        if not board:
            return None, "board is required"

        branch = (data.get("branch") or "").strip()
        if not branch:
            return None, "branch is required"

        commit_sha = (data.get("commitSha") or "").strip() or None
        trigger_type = (data.get("triggerTypes") or "manual").strip()
        mfg_repo_slug = (data.get("mfgRepoSlug") or "").strip() or None
        mfg_ssh_url = (data.get("mfgSshUrl") or "").strip() or None

        name = (data.get("name") or "").strip() or None
        build_variant = (data.get("buildVariant") or "debug").strip()

        validation_config = data.get("validationConfig")
        if validation_config is not None and not isinstance(validation_config, dict):
            return None, "validationConfig must be an object"

        # Build matrix mode — must match ValidationStage enum names (lowercase)
        matrix_mode = (data.get("matrixMode") or "fuota").strip()
        valid_modes = ("smoke", "silicon", "integration", "nightly", "fuota")
        if matrix_mode not in valid_modes:
            return None, f"matrixMode must be one of: {', '.join(valid_modes)}"

        main_commit = (data.get("mainCommit") or "").strip() or None
        pr_branch = (data.get("prBranch") or "").strip() or None

        auto_validate = data.get("autoValidate", False)
        if not isinstance(auto_validate, bool):
            return None, "autoValidate must be a boolean"

        return cls(
            product=product,
            board=board,
            branch=branch,
            product_id=product_id,
            repo_slug=repo_slug,
            commit_sha=commit_sha,
            trigger_type=trigger_type,
            mfg_repo_slug=mfg_repo_slug,
            mfg_ssh_url=mfg_ssh_url,
            name=name,
            build_variant=build_variant,
            validation_config=validation_config,
            matrix_mode=matrix_mode,
            main_commit=main_commit,
            pr_branch=pr_branch,
            auto_validate=auto_validate,
        ), None



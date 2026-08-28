"""Resolve test packages and gate run scheduling.

Manufacturing and validation share this module so the picking rules
and the runnability gates stay consistent across both paths.

Two responsibilities:

* :func:`resolve_test_package` — pick the right TestPackage row given
  some combination of explicit id/version, package type, and a status
  preference. Used by mfg session creation, the mfg runner deployment,
  and the validation scheduler.

* :func:`assert_validation_stage_runnable` — gate validation queue
  scheduling on the stage having a blessed released package
  (``ProductStageConfig.releasedTestPackageId``). Returns a 409 error
  tuple when the gate fails, ``None`` when it passes.

* :func:`assert_purpose_match` — enforce dev/release isolation between
  a package's status and a fixture's purpose. The actual call sites
  land in a later commit; the helper lives here so all gating code is
  in one place.
"""

from typing import Literal, Optional, Tuple

from src.lib.errors import bad_request, conflict, not_found

ResolveMode = Literal["RELEASED", "DEV", "ANY"]
PackageType = Literal["VALIDATION", "MANUFACTURING"]


def resolve_test_package(
    db,
    product_id: str,
    package_type: PackageType,
    *,
    explicit_id: Optional[str] = None,
    explicit_version: Optional[str] = None,
    mode: ResolveMode = "RELEASED",
):
    """Pick the test package for a run or session.

    Resolution order:

    1. ``explicit_id`` — exact id lookup. 404 if missing, 400 if it
       belongs to a different product or has the wrong type.
    2. ``explicit_version`` — find by ``(productId, type, version)``.
       404 if missing.
    3. ``mode``-driven fallback:
         * ``"RELEASED"`` — latest RELEASED package, or ``None`` if none exist
         * ``"DEV"`` — latest DEVELOPMENT package, or ``None`` if none exist
         * ``"ANY"`` — latest of any status, or ``None`` if none exist

    Returns a tuple ``(test_package, error_response)`` where exactly
    one is ever non-``None`` for the explicit cases. For the
    mode-driven path both can be ``None`` (no candidate exists, but
    that's not necessarily an error — the caller decides).
    """
    if explicit_id:
        tp = db.testpackage.find_unique(where={"id": explicit_id})
        if not tp:
            return None, not_found(f"Test package {explicit_id} not found")
        if tp.productId != product_id:
            return None, bad_request(
                "Test package does not belong to this product"
            )
        if tp.type != package_type:
            return None, bad_request(
                f"Test package type {tp.type} does not match expected {package_type}"
            )
        return tp, None

    if explicit_version:
        tp = db.testpackage.find_first(
            where={
                "productId": product_id,
                "type": package_type,
                "version": explicit_version,
            },
        )
        if not tp:
            return None, not_found(
                f"{package_type.lower()} test package version "
                f"'{explicit_version}' not found"
            )
        return tp, None

    where: dict = {"productId": product_id, "type": package_type}
    if mode == "RELEASED":
        where["status"] = "RELEASED"
    elif mode == "DEV":
        where["status"] = "DEVELOPMENT"
    # mode == "ANY" — no status filter

    tp = db.testpackage.find_first(where=where, order={"createdAt": "desc"})
    return tp, None


def assert_validation_stage_runnable(stage_config) -> Optional[tuple]:
    """Gate validation auto-scheduling on a blessed released package.

    Validation runs are auto-triggered by build completion; without an
    explicit package binding the system would silently auto-pick the
    latest released candidate, which masks "I forgot to release a new
    package" mistakes. Fail loudly instead.

    Returns a Flask error tuple when the stage has no released
    package bound (or no stage config at all), ``None`` when runnable.
    """
    if stage_config is None:
        return conflict(
            "Validation queue entry has no stage config — bind one before "
            "scheduling runs."
        )
    released_id = getattr(stage_config, "releasedTestPackageId", None)
    if not released_id:
        return conflict(
            "Validation stage has no released test package — bind a released "
            "package to this stage before scheduling runs."
        )
    return None


def assert_purpose_match(test_package, fixture) -> Optional[tuple]:
    """Gate run creation on the package status / fixture purpose pairing.

    The check is intentionally asymmetric:

    * RELEASE fixtures are the production floor — they ONLY accept
      RELEASED packages. A DEVELOPMENT package on a RELEASE fixture is
      a 409: that's the protection that stops dev code from touching
      customer hardware.
    * DEV fixtures are sandboxes — they accept BOTH dev and released
      packages. The common workflow ("iterate on a dev rig, release,
      verify the released package on the same rig before shipping")
      works with no operator-side fiddling.

    To make a fixture strict-only-released, it's already
    ``purpose=RELEASE``. To run a released package on a dev rig, no
    flip needed — the dev rig accepts it.

    Returns a Flask error tuple on mismatch, ``None`` on match.
    """
    pkg_status = getattr(test_package, "status", None)
    fixture_purpose = getattr(fixture, "purpose", None)

    if pkg_status == "DEVELOPMENT" and fixture_purpose == "RELEASE":
        return conflict(
            "Development packages cannot run on release fixtures. "
            "Pick a dev fixture, or release the package first."
        )
    return None

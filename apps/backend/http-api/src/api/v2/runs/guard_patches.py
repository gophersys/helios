"""Guard check patches — documents exact changes needed in files that use
the old db.session / db.test Prisma accessors. These models were replaced
by TestRun (db.testrun) and TestExecution (db.testexecution) in the unified
run data model.

Apply each patch below by replacing the OLD code with the NEW code in the
specified file and function.

Note: db.manufacturingsession references are CORRECT and should NOT be
changed — ManufacturingSession remains its own model.
"""

# ═══════════════════════════════════════════════════════════════════════
# 1. fixtures/fixtures.py — dashboard_overview()
#    File: apps/backend/http-api/src/api/v2/fixtures/fixtures.py
#    Lines: 80-93
#
#    db.session.count → db.testrun.count
#    The validation stats section uses db.session which no longer exists.
#    Replace with db.testrun and filter by type="VALIDATION".
#    Also update status filter: old model used "PASSED", new model uses
#    "COMPLETED" (runs that complete with 0 failures are COMPLETED).
#
# OLD CODE (lines 80-93):
#
#     if "validation:view" in perms:
#         sess_where: dict = {"type": "VALIDATION"}
#         if product_where:
#             sess_where["productId"] = product_where.get("id", {})
#         total_runs = db.session.count(where=sess_where)
#         active_runs = db.session.count(where={**sess_where, "status": "ACTIVE"})
#         passed_runs = db.session.count(where={**sess_where, "status": "PASSED"})
#         queue_depth = db.validationqueueentry.count(where={"status": {"in": ["QUEUED", "ASSIGNED"]}})
#         stats["validation"] = {
#             "total": total_runs,
#             "active": active_runs,
#             "passed": passed_runs,
#             "passRate": round(passed_runs / total_runs * 100) if total_runs > 0 else None,
#             "queueDepth": queue_depth,
#         }
#
# NEW CODE:
#
#     if "validation:view" in perms:
#         run_where: dict = {"type": "VALIDATION"}
#         if product_where:
#             run_where["productId"] = product_where.get("id", {})
#         total_runs = db.testrun.count(where=run_where)
#         active_runs = db.testrun.count(where={**run_where, "status": "ACTIVE"})
#         passed_runs = db.testrun.count(where={**run_where, "status": "COMPLETED"})
#         queue_depth = db.validationqueueentry.count(where={"status": {"in": ["QUEUED", "ASSIGNED"]}})
#         stats["validation"] = {
#             "total": total_runs,
#             "active": active_runs,
#             "passed": passed_runs,
#             "passRate": round(passed_runs / total_runs * 100) if total_runs > 0 else None,
#             "queueDepth": queue_depth,
#         }
#
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 2. products/products.py — delete_product()
#    File: apps/backend/http-api/src/api/v2/products/products.py
#    Lines: 402-410
#
#    db.session.find_first → db.testrun.find_first
#    db.test.find_first    → db.testexecution.find_first
#
#    The guard checks prevent deleting a product that has runs or
#    executions referencing it. The old model used "Session" and "Test".
#    TestExecution doesn't have a direct productId — it belongs to a
#    RunTarget which belongs to a TestRun. So the test guard should
#    check for TestRun instead (which already covers executions).
#
# OLD CODE (lines 402-410):
#
#     # Check if product has sessions
#     session_ref = db.session.find_first(where={"productId": product_id})
#     if session_ref:
#         return conflict("Cannot delete product: it has associated sessions")
#
#     # Check if product has tests
#     test_ref = db.test.find_first(where={"productId": product_id})
#     if test_ref:
#         return conflict("Cannot delete product: it has associated tests")
#
# NEW CODE:
#
#     # Check if product has test runs
#     run_ref = db.testrun.find_first(where={"productId": product_id})
#     if run_ref:
#         return conflict("Cannot delete product: it has associated test runs")
#
#     # Check if product has manufacturing sessions
#     mfg_ref = db.manufacturingsession.find_first(where={"productId": product_id})
#     if mfg_ref:
#         return conflict("Cannot delete product: it has associated manufacturing sessions")
#
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 3. assets/asset_sets.py — delete_asset_set()
#    File: apps/backend/http-api/src/api/v2/assets/asset_sets.py
#    Lines: 313-316
#
#    db.session.count → db.testrun.count
#    The guard prevents deleting an asset set that has test runs
#    referencing it.
#
# OLD CODE (lines 313-316):
#
#     # Check if any sessions reference this asset set
#     linked_sessions = db.session.count(where={"assetSetId": asset_set_id})
#     if linked_sessions > 0:
#         return bad_request(f"Cannot delete — {linked_sessions} session(s) reference this asset set")
#
# NEW CODE:
#
#     # Check if any test runs reference this asset set
#     linked_runs = db.testrun.count(where={"assetSetId": asset_set_id})
#     if linked_runs > 0:
#         return bad_request(f"Cannot delete — {linked_runs} run(s) reference this asset set")
#
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 4. builds/build_runs.py — list_build_run_sessions()
#    File: apps/backend/http-api/src/api/v2/builds/build_runs.py
#    Lines: 328-336
#
#    db.session.count     → db.testrun.count
#    db.session.find_many → db.testrun.find_many
#
#    Also update the serializer block (lines 341-358) since TestRun
#    uses different field names:
#      - s.finishedAt → s.completedAt
#      - targetCount, completedCount, passedCount, failedCount remain the same
#
# OLD CODE (lines 328-358):
#
#         where = {"buildRunId": run_id}
#         total = db.session.count(where=where)
#         sessions = db.session.find_many(
#             where=where,
#             skip=skip,
#             take=limit,
#             order={"createdAt": "desc"},
#             include={"product": True},
#         )
#
#         pages = (total + limit - 1) // limit if limit > 0 else 0
#
#         data = []
#         for s in sessions:
#             entry = {
#                 "id": s.id,
#                 "name": s.name,
#                 "type": s.type if hasattr(s, "type") else "VALIDATION",
#                 "productId": s.productId,
#                 "status": s.status,
#                 "targetCount": s.targetCount,
#                 "completedCount": s.completedCount,
#                 "passedCount": s.passedCount,
#                 "failedCount": s.failedCount,
#                 "startedAt": s.startedAt.isoformat() if s.startedAt else None,
#                 "finishedAt": s.finishedAt.isoformat() if s.finishedAt else None,
#                 "createdAt": s.createdAt.isoformat(),
#             }
#             if hasattr(s, "product") and s.product is not None:
#                 entry["product"] = {"id": s.product.id, "name": s.product.name}
#             data.append(entry)
#
# NEW CODE:
#
#         where = {"buildRunId": run_id}
#         total = db.testrun.count(where=where)
#         runs = db.testrun.find_many(
#             where=where,
#             skip=skip,
#             take=limit,
#             order={"createdAt": "desc"},
#             include={"product": True},
#         )
#
#         pages = (total + limit - 1) // limit if limit > 0 else 0
#
#         data = []
#         for r in runs:
#             entry = {
#                 "id": r.id,
#                 "name": r.name,
#                 "type": r.type if hasattr(r, "type") else "VALIDATION",
#                 "productId": r.productId,
#                 "status": r.status,
#                 "targetCount": r.targetCount,
#                 "completedCount": r.completedCount,
#                 "passedCount": r.passedCount,
#                 "failedCount": r.failedCount,
#                 "startedAt": r.startedAt.isoformat() if r.startedAt else None,
#                 "completedAt": r.completedAt.isoformat() if r.completedAt else None,
#                 "createdAt": r.createdAt.isoformat(),
#             }
#             if hasattr(r, "product") and r.product is not None:
#                 entry["product"] = {"id": r.product.id, "name": r.product.name}
#             data.append(entry)
#
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 4b. builds/build_runs.py — validate_build_run()
#     File: apps/backend/http-api/src/api/v2/builds/build_runs.py
#     Line: 397
#
#     db.session.find_unique → db.testrun.find_unique
#
#     The guard checks whether a prior validation run is still active
#     before creating a new one. Same model rename.
#
# OLD CODE (line 397):
#
#             prior_run = db.session.find_unique(where={"id": build_run.validationRunId})
#
# NEW CODE:
#
#             prior_run = db.testrun.find_unique(where={"id": build_run.validationRunId})
#
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════
# 5. services/retention.py — cleanup_old_validation_runs()
#    File: apps/backend/http-api/src/services/retention.py
#    Lines: 46-53, 82
#
#    db.session.find_many → db.testrun.find_many
#    db.session.delete    → db.testrun.delete
#
#    Also update the include block: the old model had testExecutions.results,
#    the new model has targets.executions.steps. And finishedAt → completedAt.
#
# OLD CODE (lines 46-53):
#
#     old_runs = db.session.find_many(
#         where={
#             "finishedAt": {"lt": cutoff},
#         },
#         include={
#             "testExecutions": {"include": {"results": True}},
#         },
#     )
#
# NEW CODE:
#
#     old_runs = db.testrun.find_many(
#         where={
#             "completedAt": {"lt": cutoff},
#         },
#         include={
#             "targets": {"include": {"executions": {"include": {"steps": True}}}},
#         },
#     )
#
# OLD CODE (line 82):
#
#             db.session.delete(where={"id": run_id})
#
# NEW CODE:
#
#             db.testrun.delete(where={"id": run_id})
#
# Also update the docstring (line 29):
#   "Database records (Session, TestExecution, TestResult cascade)"
#   →
#   "Database records (TestRun, RunTarget, TestExecution, TestStep cascade)"
#
# ═══════════════════════════════════════════════════════════════════════

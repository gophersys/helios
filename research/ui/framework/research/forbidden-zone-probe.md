# Forbidden-zone probe — method and result (2026-08-14)

**Question.** G-1 declares gap-pair ratios in (1.03, 1.45) "sloppy". Are the
thresholds load-bearing in a fragile way on real layouts, and do our own
solved panels respect the law they are audited by?

**Method.** A blind system cannot run human subjects, so it probes its rule's
operational robustness instead: extract every same-kind adjacent knob-row gap
the solver emits across all three demo panels, under every locally available
font (2 on the probing machine: Ableton Sans Small, Arial; DejaVu joins on
the fleet), form all pair ratios, then (1) check the deep forbidden core
(1.06..1.40) for occupants, (2) sweep the upper threshold 1.20..1.60 in 0.05
steps counting classification flips. The probe is a permanent test
(`test_forbidden_zone_probe.py`) — it re-runs on every gate, so this record
cannot silently go stale.

**Result.** 8 gap pairs; ratios ∈ {{1.000 ×6, 1.015 ×2}}; max 1.015.
- Deep core occupancy: **zero**. Every real layout is EQUAL-rhythm (within
  1.5%) — rhythm-by-construction and the nudge corrections keep panels far
  from the zone rather than skirting it.
- Threshold sweep: **perfect plateau** — every threshold in 1.20..1.60
  classifies the corpus identically. On real solved layouts the exact 1.45
  is not load-bearing at all; it only matters for HAND-made layouts, which
  is precisely the audit's job.

**Reading.** The law's teeth show only when geometry is hand-placed (the
operator's pre-solver rounds, where 1.07 and 1.33 ratios really occurred and
really read as sloppy). Solver-emitted geometry structurally avoids the zone.
The thresholds stay as adopted (detection JND ~3%; grouping ≥1.45 from the
Gori & Spillmann ratio composition) — unchallenged by this probe, and the
probe's regression guard now prevents any future layout from entering the
core unnoticed.

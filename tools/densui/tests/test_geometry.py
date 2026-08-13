from densui import breathing, contains, gap_law_violations, hgap, inter


def test_inter_detects_and_names_overlap():
    assert inter((0, 0, 10, 10), (5, 5, 20, 20)) == (5, 5, 10, 10)


def test_inter_ignores_touching():
    assert inter((0, 0, 10, 10), (10, 0, 20, 10)) is None


def test_hgap_neighbours_and_non_neighbours():
    assert hgap((0, 0, 10, 10), (14, 2, 20, 8)) == 4
    assert hgap((0, 0, 10, 10), (14, 20, 20, 30)) is None


def test_containment_can_fail():
    assert contains((0, 0, 10, 10), (0, 0, 100, 100)) is None
    assert contains((0, 0, 110, 10), (0, 0, 100, 100)) == 10


def test_breathing_can_fail():
    assert breathing((0, 0, 10, 90), (0, 0, 100, 100)) is None
    assert breathing((0, 0, 10, 99.5), (0, 0, 100, 100)) == 0.5


def test_gap_law_forbidden_zone():
    # 50 vs 60 = ratio 1.2: inside the forbidden zone
    assert gap_law_violations([50, 60]) == [(50, 60)]
    # equal within tolerance, and clearly hierarchical, both legal
    assert gap_law_violations([50, 51]) == []
    assert gap_law_violations([50, 80]) == []

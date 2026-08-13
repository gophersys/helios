"""Gate-3 drills, RUN not asserted — the bench demo's contract stage.

Each drill is the framework's own requirement executed: echo suppression by
token, device coercion adopted without loops, undo keyed to source, streams
that refuse set() and go stale rather than zero, disconnect honesty.
"""

import pytest

from densui.fakes import FakeSerial
from densui.tree import Desc, Tree, TreeError

DESCS = [
    Desc("power.rail.3v3.setpoint", "float", 2.8, 3.6, 3.30),
    Desc("power.ilimit", "float", 0.05, 2.0, 0.50),
    Desc("tele.rail.3v3.v", "stream", staleness_s=0.5),
]


def make():
    tree = Tree(DESCS, now=Clock())
    dev = FakeSerial(tree.device_report, quantize={"power.rail.3v3.setpoint": 0.05})
    tree._adapter = dev
    return tree, dev


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_echo_by_token_confirms_silently_and_coercion_is_adopted():
    tree, _dev = make()
    seen = []
    tree.subscribe("power.rail.3v3.setpoint", lambda v, a: seen.append(v))
    tree.set("power.rail.3v3.setpoint", 3.333, source="user")
    # device quantized to 3.35; the echo carried our token -> confirmed
    # updates silently, local stays the optimistic value, NO notify loop
    assert seen == [3.333]
    assert tree.confirmed("power.rail.3v3.setpoint") == 3.35
    assert not tree.pending("power.rail.3v3.setpoint")


def test_unsolicited_disagreement_is_adopted_and_repainted():
    tree, dev = make()
    seen = []
    tree.subscribe("power.rail.3v3.setpoint", lambda v, a: seen.append(v))
    dev.push_unsolicited("power.rail.3v3.setpoint", 3.05)
    assert tree.get("power.rail.3v3.setpoint") == 3.05
    assert seen == [3.05]  # hiding a disagreement hides a bug


def test_undo_records_only_user_sources():
    tree, dev = make()
    tree.set("power.ilimit", 1.0, source="user")
    tree.set("power.ilimit", 1.5, source="automation")
    dev.push_unsolicited("power.ilimit", 0.8)
    assert [a for a, _ in tree.undo_stack()] == ["power.ilimit"]
    assert len(tree.undo_stack()) == 1  # neither automation nor device


def test_streams_refuse_set_and_go_stale_not_zero():
    tree, _dev = make()
    with pytest.raises(TreeError, match="stream"):
        tree.set("tele.rail.3v3.v", 3.3, source="user")
    assert tree.stale("tele.rail.3v3.v")  # never seen = unknown, not 0
    tree.stream_report("tele.rail.3v3.v", 3.297)
    assert not tree.stale("tele.rail.3v3.v")
    tree._now.t = 0.6  # deadline passes
    assert tree.stale("tele.rail.3v3.v")


def test_disconnect_leaves_pending_and_reconnect_report_resolves():
    tree, dev = make()
    dev.connected = False
    tree.set("power.rail.3v3.setpoint", 3.5, source="user")
    assert tree.pending("power.rail.3v3.setpoint")  # honest: unacked
    dev.connected = True
    dev.push_unsolicited("power.rail.3v3.setpoint", 3.5)
    assert not tree.pending("power.rail.3v3.setpoint")


def test_unknown_address_throws_everywhere():
    tree, _ = make()
    for fn in (
        lambda: tree.get("nope"),
        lambda: tree.set("nope", 1, source="user"),
        lambda: tree.subscribe("nope", print),
    ):
        with pytest.raises(TreeError, match="unknown parameter"):
            fn()


def test_seam_coalesces_last_write_wins_and_bounds_the_queue():
    from densui.seam import Seam

    tree, dev = make()
    seam = Seam(dev)
    tree._adapter = seam
    for i in range(120):  # a 120-event drag burst
        tree.set("power.ilimit", 0.05 + i * 0.01, source="user")
    assert seam.depth() == 1  # bounded: one slot per address
    assert seam.flush() == 1  # one wire write, the last value
    assert dev.applied[-1][1] == pytest.approx(1.24)


def test_device_never_moves_a_value_under_the_cursor():
    tree, dev = make()
    tree.engage("power.rail.3v3.setpoint")
    dev.push_unsolicited("power.rail.3v3.setpoint", 2.9)
    assert tree.get("power.rail.3v3.setpoint") == 3.30  # queued, not applied
    tree.release("power.rail.3v3.setpoint")
    assert tree.get("power.rail.3v3.setpoint") == 2.9  # applied on release


def test_readall_resync_clears_pendings_with_device_truth():
    tree, dev = make()
    tree.set("power.rail.3v3.setpoint", 3.5, source="user")  # acked (3.5)
    dev.connected = False
    tree.set("power.ilimit", 1.5, source="user")  # unacked
    assert tree.pending("power.ilimit")
    dev.connected = True
    tree.resync()
    assert not tree.pending("power.ilimit")
    assert tree.get("power.ilimit") == 0.50  # the lost write REVERTS — the
    # panel must not show a setpoint the hardware does not hold
    assert tree.confirmed("power.rail.3v3.setpoint") == 3.5

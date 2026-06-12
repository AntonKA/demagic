from pathlib import Path

from demagic.ledger.ledger import ArtifactStatus, Ledger


def test_register_and_reconcile(tmp_path: Path):
    led = Ledger(workdir=tmp_path / ".demagic")
    led.register("prg:1", kind="program")
    led.register("prg:1/expr:0", kind="expression")
    assert led.pending_count() == 2

    led.set_status("prg:1", ArtifactStatus.CONVERTED)
    led.set_status("prg:1/expr:0", ArtifactStatus.FLAGGED, reason="unmapped function XYZ()")
    gaps = led.reconcile()
    assert gaps == []


def test_reconcile_reports_pending(tmp_path: Path):
    led = Ledger(workdir=tmp_path / ".demagic")
    led.register("prg:2", kind="program")
    assert led.reconcile() == ["prg:2"]


def test_persistence_roundtrip(tmp_path: Path):
    workdir = tmp_path / ".demagic"
    led = Ledger(workdir=workdir)
    led.register("ds:1", kind="data_object")
    led.set_status("ds:1", ArtifactStatus.UNPARSED, reason="unknown element <Foo>")
    led.save()

    led2 = Ledger.load(workdir)
    assert led2.get("ds:1").status == ArtifactStatus.UNPARSED
    assert "Foo" in (led2.get("ds:1").reason or "")


def test_register_is_idempotent(tmp_path: Path):
    led = Ledger(workdir=tmp_path / ".demagic")
    led.register("prg:1", kind="program")
    led.set_status("prg:1", ArtifactStatus.CONVERTED)
    led.register("prg:1", kind="program")  # re-scan must not reset status
    assert led.get("prg:1").status == ArtifactStatus.CONVERTED

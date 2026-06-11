"""Tests del util de fecha en horario Argentina (UTC-3)."""

from datetime import datetime, timezone

from app.core.fecha import fmt_fecha_ar


def test_fmt_naive_utc_se_convierte_a_argentina():
    # Naive = se asume UTC. 03:00 UTC → 00:00 Argentina.
    assert fmt_fecha_ar(datetime(2026, 6, 3, 3, 0, 0)) == "03/06/2026 00:00"


def test_fmt_aware_utc_se_convierte():
    dt = datetime(2026, 6, 3, 3, 0, 0, tzinfo=timezone.utc)
    assert fmt_fecha_ar(dt) == "03/06/2026 00:00"


def test_fmt_none_devuelve_guion():
    assert fmt_fecha_ar(None) == "—"


def test_fmt_cruza_medianoche_hacia_atras():
    # 02:00 UTC del día 3 → 23:00 Argentina del día 2.
    assert fmt_fecha_ar(datetime(2026, 6, 3, 2, 0, 0)) == "02/06/2026 23:00"

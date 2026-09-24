import itertools

import numpy as np
import pandas as pd
import pytest

from potencia.calculo import (Estudio, Tarifa, calcular_inversion, cargar_precios,
                              opciones_inversion_defecto, validar_potencias)
from potencia.calendario import asignar_periodos, festivos
from tests import generador as g


@pytest.fixture(scope="module")
def estudio():
    esp = g.esperado(g.curva_fisica())
    curva = pd.DataFrame({"inicio": esp.index, "kw": esp.to_numpy()})
    return Estudio(curva, "Península", Tarifa.desde_precios(cargar_precios(), "6.1TD"))


def test_periodos_peninsula():
    ts = pd.to_datetime(["2026-01-13 09:00", "2026-01-13 08:45", "2026-01-13 07:45",
                         "2026-03-10 10:00", "2026-06-10 22:15", "2026-04-14 19:00",
                         "2026-01-17 12:00", "2026-01-06 12:00", "2026-01-01 12:00", "2026-05-01 12:00"])
    assert list(asignar_periodos(ts, "Península")) == [1, 2, 6, 2, 4, 4, 6, 6, 6, 6]


def test_periodos_canarias_y_ceuta():
    # Canarias: julio (alta) -> P1 punta, P3 llano; Ceuta: enero (alta) -> P1 punta, P4 llano
    ts = pd.to_datetime(["2026-07-14 11:00", "2026-07-14 09:00"])
    assert list(asignar_periodos(ts, "Canarias")) == [1, 3]
    ts = pd.to_datetime(["2026-01-13 20:00", "2026-01-13 16:00", "2026-04-14 11:00"])
    assert list(asignar_periodos(ts, "Ceuta")) == [1, 4, 3]


def test_festivos_fijos():
    f = festivos([2026])
    assert pd.Timestamp("2026-10-12").date() in f
    assert pd.Timestamp("2026-04-03").date() not in f   # Viernes Santo: sin fecha fija


def test_coste_formula_manual(estudio):
    pc = np.array([200, 210, 220, 230, 240, 250.0])
    c = estudio.coste(pc)
    t = estudio.tarifa
    fijo = (pc * t.tp).sum() * estudio.dias_totales / t.dias_anio
    assert c.total_fijo == pytest.approx(fijo)
    exc = 0.0
    for i in range(len(estudio.meses)):
        for p in range(6):
            v = estudio.kw[(estudio.idx_mes == i) & (estudio.periodo == p + 1)]
            d = np.clip(v - pc[p], 0, None)
            exc += t.tep[p] * np.sqrt((d ** 2).sum())
    assert c.total_exceso == pytest.approx(exc)


def test_optimo_es_minimo_con_orden(estudio):
    o = estudio.optimo()
    assert all(o[i] <= o[i + 1] for i in range(5))
    base = estudio.coste(o).total
    # ningún vecino entero (que respete el orden) mejora el óptimo
    for delta in itertools.product((-1, 0, 1), repeat=6):
        pc = o + np.array(delta)
        if validar_potencias(pc) is None:
            assert estudio.coste(pc).total >= base - 1e-6


def test_inversion():
    derechos = {"acceso": 16.992541, "extension": 15.718632, "enganche": 79.49197}
    actual = [250, 265, 265, 265, 265, 265]
    op = opciones_inversion_defecto([340] * 6, actual)
    inv = calcular_inversion([340] * 6, actual, op, derechos)
    assert inv["total"] == pytest.approx(75 * (16.992541 + 15.718632) + 79.49197)
    op = opciones_inversion_defecto([265] * 6, actual)
    assert calcular_inversion([265] * 6, actual, op, derechos)["total"] == pytest.approx(79.49197)


def test_validar_potencias():
    assert validar_potencias([1, 2, 3, 4, 5, 6]) is None
    assert "crecientes" in validar_potencias([10, 5, 5, 5, 5, 5])

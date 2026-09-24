import numpy as np
import pandas as pd
import pytest

from potencia.calculo import Estudio, ResumenMultipunto, Tarifa, cargar_precios, evaluar, opciones_inversion_defecto
from potencia.lector_curva import LectorCurva
from tests import generador as g

CUPS_A = "ES0000000000000001AA0F"
CUPS_B = "ES0000000000000002BB0F"


@pytest.fixture(scope="module")
def curvas():
    return {CUPS_A: g.curva_fisica(semilla=1), CUPS_B: g.curva_fisica(semilla=2)}


def test_lector_varios_cups(tmp_path, curvas):
    ruta = tmp_path / "multi.txt"
    g.escribir_p5d_multipunto(curvas, ruta)
    lector = LectorCurva(ruta)
    lector.procesar()
    assert sorted(lector.cups_disponibles) == sorted(curvas)
    for cups, fis in curvas.items():
        c = lector.procesar(cups=cups)
        assert c.cups == cups
        esperado = g.esperado(fis)
        assert np.abs(c.datos["kw"].to_numpy() - esperado.to_numpy()).max() < 0.01


def test_resumen_suma_actual_y_optima(curvas):
    pr = cargar_precios()
    lista = []
    for k, (cups, fis) in enumerate(curvas.items()):
        esp = g.esperado(fis)
        tarifa = Tarifa.desde_precios(pr, "6.1TD" if k == 0 else "3.0TD")
        est = Estudio(pd.DataFrame({"inicio": esp.index, "kw": esp.to_numpy()}), "Península", tarifa)
        actual = [150] * 5 + [200]
        opt = est.optimo()
        escs = evaluar(est, [("Propuesta 1", opt, opciones_inversion_defecto(opt, actual))], actual)
        lista.append((est, escs))
    r = ResumenMultipunto(lista)
    act, optima = r.escenarios
    assert act.coste.total == pytest.approx(sum(escs[0].coste.total for _, escs in lista))
    assert optima.coste.total == pytest.approx(sum(escs[1].coste.total for _, escs in lista))
    assert optima.inversion["total"] == pytest.approx(sum(escs[1].inversion["total"] for _, escs in lista))
    assert optima.ahorro == pytest.approx(act.coste.total - optima.coste.total)
    assert len(r.etiquetas_meses) == 12 and not r.periodos_distintos
    assert r.energia_kwh().sum() == pytest.approx(sum(est.energia_kwh().sum() for est, _ in lista))

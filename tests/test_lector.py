import numpy as np
import pandas as pd
import pytest

from potencia.lector_curva import LectorCurva
from tests import generador as g


@pytest.fixture(scope="module")
def fisica():
    return g.curva_fisica()


@pytest.fixture(scope="module")
def esperado_qh(fisica):
    return g.esperado(fisica)


@pytest.fixture(scope="module")
def esperado_h(fisica):
    return g.esperado(fisica, horaria=True)


def _comparar(curva, esperado, tol):
    s = curva.datos.set_index("inicio")["kw"]
    assert len(s) == len(esperado), (len(s), len(esperado))
    assert (s.index == esperado.index).all()
    assert np.abs(s.to_numpy() - esperado.to_numpy()).max() < tol


@pytest.mark.parametrize("escritor, nombre, unidad, conv", [
    (g.escribir_p5d, "p5d.txt", "kWh", "Fin de periodo"),
    (g.escribir_datadis_cuartos, "datadis.csv", "kWh", "Fin de periodo"),
    (g.escribir_iso_offset, "iso.csv", "kW", "Fin de periodo"),
])
def test_cuartohorarias(tmp_path, fisica, esperado_qh, escritor, nombre, unidad, conv):
    ruta = tmp_path / nombre
    escritor(fisica, ruta)
    c = LectorCurva(ruta).procesar()
    assert c.resolucion_min == 15
    assert c.unidad == unidad
    assert c.convenio.startswith(conv)
    assert c.huecos_rellenados == 0
    assert len(c.dias_cambio_hora) == 2
    _comparar(c, esperado_qh, tol=0.01)


def test_excel_geype(tmp_path, esperado_qh):
    ruta = tmp_path / "geype.xlsx"
    g.escribir_excel_geype(esperado_qh, ruta)
    lector = LectorCurva(ruta)
    assert lector.hoja_defecto == "Curva_potencia"
    c = lector.procesar()
    assert c.unidad == "kW"
    _comparar(c, esperado_qh, tol=1e-6)


def test_horaria_ordinal_wh(tmp_path, fisica, esperado_h):
    ruta = tmp_path / "horaria.csv"
    g.escribir_distribuidora_horaria(fisica, ruta)
    c = LectorCurva(ruta).procesar()
    assert c.resolucion_min == 60
    assert c.unidad == "Wh"
    assert c.es_horaria
    _comparar(c, esperado_h, tol=0.002)


def test_ancho_horario(tmp_path, fisica, esperado_h):
    ruta = tmp_path / "ancho.xlsx"
    g.escribir_ancho_horario(fisica, ruta)
    c = LectorCurva(ruta).procesar()
    assert c.resolucion_min == 60
    _comparar(c, esperado_h, tol=1e-6)


def test_huecos_y_recorte(tmp_path):
    fis = g.curva_fisica("2025-03-01", "2026-06-15")
    fis = fis.drop(fis.index[1000:1008])               # dos horas sin dato
    ruta = tmp_path / "p5d.txt"
    g.escribir_p5d(fis, ruta)
    c = LectorCurva(ruta).procesar()
    assert c.huecos_rellenados == 8
    assert c.fecha_inicio == pd.Timestamp("2025-06-01")
    assert c.fecha_fin == pd.Timestamp("2026-06-01")
    assert any("12 últimos meses" in a for a in c.avisos)


def test_forzar_unidad(tmp_path, fisica, esperado_qh):
    ruta = tmp_path / "p5d.txt"
    g.escribir_p5d(fisica, ruta)
    c = LectorCurva(ruta).procesar(unidad="kW")
    s = c.datos["kw"].to_numpy()
    assert np.allclose(s * 4, esperado_qh.to_numpy(), atol=0.01)

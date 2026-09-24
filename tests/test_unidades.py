"""Detección de la unidad a partir del título de las columnas y del resto del fichero."""
import numpy as np
import pytest

from potencia.lector_curva import LectorCurva
from tests import generador as g


@pytest.fixture(scope="module")
def fisica():
    return g.curva_fisica()


@pytest.fixture(scope="module")
def esperado(fisica):
    return g.esperado(fisica)


def _escribir(fis, ruta, cabecera, factor, antes=(), columna_unidad=None):
    """CSV con etiqueta de fin de periodo; `factor` convierte kW al valor escrito."""
    loc = g._etiquetas_fin(fis)
    filas = list(antes) + cabecera
    for l, k in zip(loc, fis["kw"]):
        fila = f"{l:%d/%m/%Y};{l:%H:%M};{str(round(k * factor, 6)).replace('.', ',')}"
        filas.append(fila + (f";{columna_unidad}" if columna_unidad else ""))
    ruta.write_text("\n".join(filas), encoding="utf-8")


@pytest.mark.parametrize("caso, cabecera, factor, antes, col_unidad, unidad, origen", [
    ("titulo_kw", ["Fecha;Hora;Potencia media (kW)"], 1, (), None, "kW", "título"),
    ("titulo_guion", ["Fecha;Hora;AE_kW"], 1, (), None, "kW", "título"),
    ("fila_unidades", ["Fecha;Hora;Valor", ";;kW"], 1, (), None, "kW", "título"),
    ("fila_formatos", ["Fecha;Hora;Valor", "dd/mm/aaaa;hh:mm;kWh"], 0.25, (), None, "kWh", "«valor kwh»"),
    ("columna_unidad", ["Fecha;Hora;Medida;Unidad"], 1, (), "kW", "kW", "columna de unidades"),
    ("nota_encima", ["Fecha;Hora;Medida"], 1, ("Curva de carga del suministro", "Unidades: kW"), None, "kW",
     "encima de la tabla"),
    ("mwh", ["Fecha;Hora;Consumo (MWh)"], 0.25 / 1000, (), None, "MWh", "título"),
    ("simbolo_manda", ["Fecha;Hora;Potencia (kWh)"], 0.25, (), None, "kWh", "título"),
    ("palabra", ["Fecha;Hora;Potencia"], 1, (), None, "kW", "palabra"),
])
def test_unidad_detectada(tmp_path, fisica, esperado, caso, cabecera, factor, antes, col_unidad, unidad, origen):
    ruta = tmp_path / f"{caso}.csv"
    _escribir(fisica, ruta, cabecera, factor, antes, col_unidad)
    c = LectorCurva(ruta).procesar()
    assert c.unidad == unidad
    assert origen in c.origen_unidad
    assert not any("No se ha podido identificar la unidad" in a for a in c.avisos)
    assert np.abs(c.datos["kw"].to_numpy() - esperado.to_numpy()).max() < 0.01


def test_sin_unidad_avisa(tmp_path, fisica):
    ruta = tmp_path / "sin_unidad.csv"
    _escribir(fisica, ruta, ["Fecha;Hora;Medida"], 0.25)
    c = LectorCurva(ruta).procesar()
    assert c.unidad == "kWh"
    assert any("No se ha podido identificar la unidad" in a for a in c.avisos)

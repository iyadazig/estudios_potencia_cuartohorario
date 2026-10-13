"""Varios ficheros de curva a la vez: uno por mes y por CUPS, con formatos distintos."""
import numpy as np
import pandas as pd
import pytest

from potencia.lector_curva import LectorCurva, LectorCurvas, abrir_curvas
from tests import generador as g

CUPS_A = "ES0000000000000001AA0F"
CUPS_B = "ES0000000000000002BB0F"


def _por_meses(fis):
    """Trozos de la curva física por mes de la hora local de inicio de cada cuarto."""
    mes = fis["utc"].dt.tz_convert(g.TZ).dt.strftime("%Y-%m")
    return [(m, fis[mes == m].reset_index(drop=True)) for m in sorted(mes.unique())]


def _p5d(fis, ruta, cups):
    g.escribir_p5d_multipunto({cups: fis}, ruta)


def _excel_kw(fis, ruta, cups):
    """Excel con fecha-hora de fin del cuarto y potencia en kW, sin columna de CUPS (va en el nombre)."""
    fin = g._etiquetas_fin(fis).dt.tz_localize(None)
    pd.DataFrame({"Fecha y hora": fin.dt.strftime("%d/%m/%Y %H:%M"), "Potencia (kW)": fis["kw"]}).to_excel(
        ruta, index=False)


def _comparar(curva, esperado, tol=0.01):
    s = curva.datos.set_index("inicio")["kw"]
    esperado = esperado.reindex(s.index)
    assert len(s) and np.abs(s.to_numpy() - esperado.to_numpy()).max() < tol


def test_un_fichero_por_mes_formatos_mezclados(tmp_path):
    fis = g.curva_fisica()
    rutas = []
    for k, (mes, trozo) in enumerate(_por_meses(fis)):
        if k % 3 == 0:
            ruta = tmp_path / f"curva_{mes}.txt"
            _p5d(trozo, ruta, CUPS_A)                         # kWh, hora de fin, con CUPS
        elif k % 3 == 1:
            ruta = tmp_path / f"{CUPS_A}_{mes}.xlsx"
            _excel_kw(trozo, ruta, CUPS_A)                    # kW, CUPS solo en el nombre
        else:
            ruta = tmp_path / f"datadis_{mes}.csv"
            g.escribir_datadis_cuartos(trozo, ruta)           # kWh, hora 24:00
            ruta.write_text(ruta.read_text(encoding="cp1252").replace(g.CUPS, CUPS_A), encoding="cp1252")
        rutas.append(ruta)
    lector = abrir_curvas(rutas)
    assert isinstance(lector, LectorCurvas)
    c = lector.procesar()
    assert c.cups == CUPS_A and lector.cups_disponibles == [CUPS_A]
    assert c.fecha_inicio == pd.Timestamp("2025-06-01") and c.fecha_fin == pd.Timestamp("2026-06-01")
    assert len(c.ficheros) == 12 and not c.sin_datos and c.huecos_rellenados == 0
    assert "varias" in c.unidad                                # kWh y kW según el fichero
    _comparar(c, g.esperado(fis))


def test_varios_cups_en_ficheros_mensuales(tmp_path):
    fisicas = {CUPS_A: g.curva_fisica(semilla=1), CUPS_B: g.curva_fisica(semilla=2)}
    rutas = []
    for cups, fis in fisicas.items():
        for mes, trozo in _por_meses(fis):
            ruta = tmp_path / f"{cups}_{mes}.xlsx"
            _excel_kw(trozo, ruta, cups)
            rutas.append(ruta)
    lector = LectorCurvas(sorted(rutas))                      # mezclados por orden alfabético
    assert sorted(lector.cups_disponibles) == sorted(fisicas)
    for cups, fis in fisicas.items():
        c = lector.procesar(cups=cups)
        assert c.cups == cups and len(c.datos) == len(g.esperado(fis))
        _comparar(c, g.esperado(fis))


def test_falta_un_mes_no_se_inventa(tmp_path):
    fis = g.curva_fisica()
    rutas = []
    for mes, trozo in _por_meses(fis):
        if mes == "2025-11":
            continue                                          # falta el fichero de noviembre
        ruta = tmp_path / f"curva_{mes}.txt"
        _p5d(trozo, ruta, CUPS_A)
        rutas.append(ruta)
    c = LectorCurvas(rutas).procesar()
    assert len(c.sin_datos) == 1
    a, b = c.sin_datos[0]
    assert a == pd.Timestamp("2025-11-01") and b == pd.Timestamp("2025-12-01")
    assert not (c.datos["inicio"].dt.strftime("%Y-%m") == "2025-11").any()
    assert any("No hay datos del 01/11/2025" in x for x in c.avisos)
    _comparar(c, g.esperado(fis))


def test_ficheros_solapados(tmp_path):
    fis = g.curva_fisica()
    meses = _por_meses(fis)
    rutas = []
    for k, (mes, trozo) in enumerate(meses):
        if k + 1 < len(meses):                                 # cada fichero lleva también el día 1 del mes siguiente
            trozo = pd.concat([trozo, meses[k + 1][1].head(96)], ignore_index=True)
        ruta = tmp_path / f"curva_{mes}.txt"
        _p5d(trozo, ruta, CUPS_A)
        rutas.append(ruta)
    c = LectorCurvas(rutas).procesar()
    assert any("más de un fichero" in x for x in c.avisos)
    assert not any("duplicados" in x for x in c.avisos)
    _comparar(c, g.esperado(fis))


def test_un_fichero_con_hueco_largo(tmp_path):
    fis = g.curva_fisica()
    loc = fis["utc"].dt.tz_convert(g.TZ)
    fis = fis[~((loc >= "2025-09-10") & (loc < "2025-09-15"))]             # 5 días sin datos
    ruta = tmp_path / "curva.txt"
    _p5d(fis, ruta, CUPS_A)
    c = LectorCurva(ruta).procesar()
    assert c.sin_datos == [(pd.Timestamp("2025-09-10"), pd.Timestamp("2025-09-15"))]
    assert c.huecos_rellenados == 0 and len(c.datos) == len(g.esperado(g.curva_fisica())) - 5 * 96

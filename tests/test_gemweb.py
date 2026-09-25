"""Conexión con Gemweb, con la API simulada (no se conecta a internet)."""
import sys
import xml.etree.ElementTree as ET
from datetime import date

import numpy as np
import pandas as pd
import pytest

from potencia import gemweb
from potencia.lector_curva import LectorCurva
from tests import generador as g

CUPS = "ES0000000000000001AA0F"


class ApiFalsa(gemweb.ClienteGemweb):
    """Responde como Gemweb: inventario y telelecturas con hora de fin y 96 cuartos por día."""

    def __init__(self, fis, inventario):
        super().__init__("usuario", "clave")
        self.fis = fis
        self.inventario = inventario
        self.peticiones = []

    def _post(self, peticion, timeout=None, **p):
        self.peticiones.append((peticion, p))
        if peticion == "get_inventory":
            filas = [f for f in self.inventario if f["cups"] == p["search_values"]]
            if not filas:
                raise gemweb.GemwebError("No se han encontrado resultados")
            xml = "<root>" + "".join("<subministrament>" + "".join(f"<{k}>{v}</{k}>" for k, v in f.items() if v)
                                     + "</subministrament>" for f in filas) + "</root>"
            return ET.fromstring(xml)
        # get_metering: [date_from 00:15, date_to 23:45] en hora local normalizada a 96 cuartos/día
        esp = g.esperado(self.fis)
        fin = esp.index + pd.Timedelta(minutes=15)
        sel = (fin > pd.Timestamp(p["date_from"])) & (fin < pd.Timestamp(p["date_to"]) + pd.Timedelta(days=1))
        valores = "".join(f'<value date="{f:%Y-%m-%d}  {f:%H:%M}">{k / 4:.4f}</value>'
                          for f, k in zip(fin[sel], esp[sel]))
        return ET.fromstring(f"<root><subministrament><id>{p['id']}</id><units>kWh</units>"
                             f"<values>{valores}</values></subministrament></root>")


@pytest.fixture(scope="module")
def fisica():
    return g.curva_fisica()


def test_descarga_en_tramos_y_lectura(tmp_path, fisica):
    api = ApiFalsa(fisica, [{"id": "7", "cups": CUPS, "tarifa_acces": "6.1TD"}])
    s = api.buscar_suministro(CUPS.lower())
    assert s["id"] == "7" and s["tarifa_acces"] == "6.1TD"
    df, fallidos = api.descargar_curva(s["id"], date(2025, 5, 31), date(2026, 6, 1))
    assert not fallidos
    assert df["fecha"].is_unique                           # los tramos se solapan un día
    assert sum(1 for pet, _ in api.peticiones if pet == "get_metering") == 12   # 366 días en tramos de 31
    ruta = tmp_path / "gemweb.csv"
    gemweb.escribir_csv({CUPS: df}, ruta)
    c = LectorCurva(ruta).procesar(convenio="Fin de periodo")
    assert c.cups == CUPS and c.unidad == "kWh"
    esperado = g.esperado(fisica)
    assert c.fecha_inicio == pd.Timestamp("2025-06-01") and c.fecha_fin == pd.Timestamp("2026-06-01")
    assert np.abs(c.datos["kw"].to_numpy() - esperado.to_numpy()).max() < 0.01


def test_buscar_suministro_activo_y_cups_20(fisica):
    inventario = [{"id": "1", "cups": CUPS[:20], "data_baixa": "2024-01-01"},
                  {"id": "2", "cups": CUPS[:20]}]
    api = ApiFalsa(fisica, inventario)
    assert api.buscar_suministro(CUPS)["id"] == "2"         # CUPS de 22 → se prueba con 20; el de alta
    assert api.buscar_suministro("ES0000000000000009ZZ0F") is None


def test_utilidades():
    assert gemweb.zona_por_codigo_postal("07001") == "Illes Balears"
    assert gemweb.zona_por_codigo_postal("7001") == "Illes Balears"
    assert gemweb.zona_por_codigo_postal("38001") == "Canarias"
    assert gemweb.zona_por_codigo_postal("41012") == "Península"
    assert gemweb.zona_por_codigo_postal(None) is None
    assert gemweb.periodo_defecto(date(2026, 9, 25)) == (date(2025, 9, 1), date(2026, 8, 31))
    assert gemweb.lista_cups(f"{CUPS.lower()};\n {CUPS}, ES0000000000000002BB0F") == [CUPS, "ES0000000000000002BB0F"]


@pytest.mark.skipif(sys.platform != "win32", reason="cifrado DPAPI de Windows")
def test_credenciales_cifradas(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("GEMWEB_CLIENT_ID", raising=False)
    monkeypatch.delenv("GEMWEB_CLIENT_SECRET", raising=False)
    assert gemweb.cargar_credenciales() is None
    gemweb.guardar_credenciales("usuarioAPI", "secreto-123")
    guardado = (tmp_path / "EstudioPotencia" / "gemweb.json").read_text(encoding="utf-8")
    assert "secreto-123" not in guardado
    assert gemweb.cargar_credenciales() == ("usuarioAPI", "secreto-123")

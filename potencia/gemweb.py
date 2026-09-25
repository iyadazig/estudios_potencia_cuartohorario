"""
Descarga de curvas cuartohorarias desde la API de Gemweb.

Adaptado del cliente del proyecto «API_Gemweb» (GemwebClient): gestión del token
(válido 1 h), reintentos y descarga de telelecturas en tramos. Aquí solo se usan
dos operaciones:
  - get_inventory (subministraments): CUPS -> id interno, tarifa, potencias, datos.
  - get_metering  (quart-horari, consum): energía de cada cuarto de hora en kWh.

Formato observado en la API: fechas «AAAA-MM-DD  HH:MM» con la hora de FIN del
cuarto (la primera del día es 00:15) y 96 cuartos por día también en los días de
cambio de hora.

Las credenciales se guardan en %APPDATA%\\EstudioPotencia\\gemweb.json, con el
secreto cifrado para el usuario de Windows (DPAPI).
"""

import base64
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

URL = "https://api.gemweb.es"
TIMEOUT = 60
TIMEOUT_METERING = 180
REINTENTOS = 3
ESPERAS_REINTENTO = [5, 15]
DIAS_TRAMO = 31          # tramos de un mes para no saturar el servidor


class GemwebError(Exception):
    """Error devuelto por la API o de conexión."""


# --------------------------------------------------------------------------
# credenciales
# --------------------------------------------------------------------------

def _ruta_credenciales():
    base = Path(os.environ.get("APPDATA") or Path.home())
    return base / "EstudioPotencia" / "gemweb.json"


def _dpapi(datos: bytes, cifrar: bool) -> bytes:
    """Cifra / descifra con la protección de datos de Windows (solo el mismo usuario puede leerlo)."""
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    entrada = BLOB(len(datos), ctypes.create_string_buffer(datos, len(datos)))
    salida = BLOB()
    fn = ctypes.windll.crypt32.CryptProtectData if cifrar else ctypes.windll.crypt32.CryptUnprotectData
    if not fn(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(salida)):
        raise GemwebError("No se ha podido cifrar/descifrar la clave de Gemweb.")
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(salida.pbData)


def guardar_credenciales(client_id, client_secret):
    ruta = _ruta_credenciales()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    try:
        secreto = {"dpapi": base64.b64encode(_dpapi(client_secret.encode("utf-8"), True)).decode("ascii")}
    except Exception:
        secreto = {"texto": client_secret}      # fuera de Windows
    ruta.write_text(json.dumps({"client_id": client_id, "client_secret": secreto}), encoding="utf-8")


def credenciales_propias():
    """Credenciales del propio usuario (variables de entorno o guardadas en su perfil) o None."""
    if os.environ.get("GEMWEB_CLIENT_ID") and os.environ.get("GEMWEB_CLIENT_SECRET"):
        return os.environ["GEMWEB_CLIENT_ID"], os.environ["GEMWEB_CLIENT_SECRET"]
    ruta = _ruta_credenciales()
    if not ruta.exists():
        return None
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
        s = d["client_secret"]
        secreto = _dpapi(base64.b64decode(s["dpapi"]), False).decode("utf-8") if "dpapi" in s else s["texto"]
        return d["client_id"], secreto
    except Exception:
        return None


def credenciales_incluidas():
    """
    Credenciales de GE&PE incluidas en el ejecutable al compilarlo con construir_exe.py
    (módulo generado _credenciales_incluidas.py, excluido de git). None si no las hay.
    """
    try:
        from ._credenciales_incluidas import obtener
        return obtener()
    except Exception:
        return None


def cargar_credenciales():
    """(client_id, client_secret): las propias del usuario o, si no tiene, las incluidas en el ejecutable."""
    return credenciales_propias() or credenciales_incluidas()


def usa_credenciales_incluidas():
    return credenciales_propias() is None and credenciales_incluidas() is not None


def ofuscar(client_id, client_secret):
    """Código fuente del módulo _credenciales_incluidas.py (datos ofuscados, no en texto plano)."""
    clave = os.urandom(32)
    datos = json.dumps([client_id, client_secret]).encode("utf-8")
    mezcla = bytes(b ^ clave[i % len(clave)] for i, b in enumerate(datos))
    return ('"""Generado por construir_exe.py al compilar el ejecutable. NO SUBIR A GIT (está en .gitignore)."""\n\n'
            f'_K = "{base64.b64encode(clave).decode()}"\n'
            f'_D = "{base64.b64encode(mezcla).decode()}"\n\n\n'
            'def obtener():\n'
            '    import base64\n'
            '    import json\n'
            '    k, d = base64.b64decode(_K), base64.b64decode(_D)\n'
            '    return tuple(json.loads(bytes(b ^ k[i % len(k)] for i, b in enumerate(d)).decode("utf-8")))\n')


def leer_secrets_toml(ruta):
    """Credenciales de un .streamlit/secrets.toml del proyecto API_Gemweb."""
    import tomllib
    with open(ruta, "rb") as f:
        s = tomllib.load(f)
    return s["GEMWEB_CLIENT_ID"], s["GEMWEB_CLIENT_SECRET"]


# --------------------------------------------------------------------------
# cliente
# --------------------------------------------------------------------------

class ClienteGemweb:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._caduca = None

    def _token_valido(self):
        return bool(self._token) and datetime.now() < self._caduca - timedelta(minutes=5)

    def _renovar_token(self):
        import requests
        try:
            r = requests.post(URL, data={"request": "get_token", "client_id": self.client_id,
                                         "client_secret": self.client_secret,
                                         "grant_type": "client_credentials"}, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException as e:
            raise GemwebError(f"No se ha podido conectar con Gemweb: {e}") from e
        raiz = ET.fromstring(r.text)
        if raiz.find("error") is not None:
            raise GemwebError(f"Credenciales de Gemweb no válidas: {raiz.findtext('error')}")
        token = raiz.findtext("access_token")
        if not token:
            raise GemwebError("Gemweb no ha devuelto el token de acceso.")
        self._token = token
        self._caduca = datetime.now() + timedelta(seconds=int(raiz.findtext("expires_in", default="3600")))

    def _post(self, peticion, timeout=TIMEOUT, **parametros):
        import requests
        for intento in range(1, REINTENTOS + 1):
            if not self._token_valido():
                self._renovar_token()
            datos = {"request": peticion, "access_token": self._token}
            datos.update({k: v for k, v in parametros.items() if v not in (None, "")})
            try:
                r = requests.post(URL, data=datos, timeout=timeout)
                r.raise_for_status()
                break
            except (requests.Timeout, requests.ConnectionError) as e:
                if intento == REINTENTOS:
                    raise GemwebError(f"Gemweb no responde ({peticion}) tras {REINTENTOS} intentos.") from e
                time.sleep(ESPERAS_REINTENTO[intento - 1])
            except requests.RequestException as e:
                raise GemwebError(f"Error de Gemweb ({peticion}): {e}") from e
        try:
            raiz = ET.fromstring(r.text)
        except ET.ParseError as e:
            raise GemwebError(f"Gemweb ha devuelto una respuesta no válida ({peticion}).") from e
        if raiz.find("error") is not None:
            raise GemwebError(raiz.findtext("error") or f"Error de Gemweb ({peticion})")
        return raiz

    def comprobar(self):
        """Pide un token para validar las credenciales."""
        self._renovar_token()

    # ------------------------------------------------------------------
    def buscar_suministro(self, cups):
        """Datos del suministro en el inventario de Gemweb (dict) o None si no existe."""
        cups = cups.strip().upper()
        candidatos = [cups] + ([cups[:20]] if len(cups) > 20 else [])
        for c in candidatos:
            try:
                raiz = self._post("get_inventory", category="subministraments",
                                  search_by="subministraments.cups", search_values=c, limit=5)
            except GemwebError as e:
                if "no se han encontrado" in str(e).lower():
                    continue
                raise
            filas = [{h.tag: h.text for h in nodo} for nodo in raiz]
            filas = [f for f in filas if f.get("id")]
            if filas:
                # si hay varios (altas y bajas), el que sigue de alta
                activos = [f for f in filas if not f.get("data_baixa")]
                return (activos or filas)[0]
        return None

    def descargar_curva(self, id_suministro, desde, hasta, al_avanzar=None):
        """
        Energía cuartohoraria (kWh) entre dos fechas (date), en tramos de un mes.
        Devuelve (DataFrame[fecha, kwh], tramos_fallidos).
        """
        tramos, ini = [], desde
        while True:
            fin = min(ini + timedelta(days=DIAS_TRAMO), hasta)
            tramos.append((ini, fin))
            if fin >= hasta:
                break
            ini = fin          # los tramos se solapan un día: no se pierde ningún cuarto
        partes, fallidos = [], []
        for n, (a, b) in enumerate(tramos, 1):
            if al_avanzar:
                al_avanzar(n, len(tramos), a, b)
            try:
                raiz = self._post("get_metering", timeout=TIMEOUT_METERING, id=int(id_suministro),
                                  date_from=a.isoformat(), date_to=b.isoformat(), data_source="comptador",
                                  period="quart-horari", field="consum", language="es")
            except GemwebError as e:
                fallidos.append(f"{a:%d/%m/%Y} – {b:%d/%m/%Y}: {e}")
                continue
            for sub in raiz.findall(".//subministrament"):
                unidades = (sub.findtext("units") or "kWh").strip()
                for v in sub.findall(".//value"):
                    partes.append((v.get("date"), float(v.text or 0), unidades))
        if not partes:
            return pd.DataFrame(columns=["fecha", "kwh"]), fallidos
        df = pd.DataFrame(partes, columns=["fecha", "valor", "unidades"])
        factor = {"kwh": 1.0, "wh": 0.001, "mwh": 1000.0}.get(df["unidades"].iloc[0].lower(), 1.0)
        df["kwh"] = df["valor"] * factor
        df["fecha"] = df["fecha"].str.replace(r"\s+", " ", regex=True).str.strip()
        df = df.drop_duplicates("fecha").sort_values("fecha", key=lambda s: pd.to_datetime(s, errors="coerce"))
        return df[["fecha", "kwh"]].reset_index(drop=True), fallidos


# --------------------------------------------------------------------------
# utilidades
# --------------------------------------------------------------------------

def periodo_defecto(hoy=None):
    """Últimos 12 meses completos: (primer día, último día)."""
    hoy = hoy or date.today()
    fin = hoy.replace(day=1) - timedelta(days=1)
    ini = (fin.replace(day=1) - timedelta(days=1)).replace(day=1)
    for _ in range(10):
        ini = (ini - timedelta(days=1)).replace(day=1)
    return ini, fin


def zona_por_codigo_postal(cp):
    """Sistema eléctrico a partir del código postal (None si no se puede deducir)."""
    cp = re.sub(r"\D", "", str(cp or ""))
    if not 4 <= len(cp) <= 5:
        return None
    return {"07": "Illes Balears", "35": "Canarias", "38": "Canarias", "51": "Ceuta",
            "52": "Melilla"}.get(cp.zfill(5)[:2], "Península")


def numero(texto):
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def lista_cups(texto):
    """CUPS únicos de un texto (separados por saltos de línea, espacios, comas o punto y coma)."""
    return list(dict.fromkeys(c.strip().upper() for c in re.split(r"[\s,;]+", texto or "") if c.strip()))


def escribir_csv(curvas, ruta):
    """
    Guarda las curvas descargadas en un CSV que el lector del programa interpreta
    directamente: CUPS; fecha-hora de fin del cuarto; energía en kWh.
    curvas: {cups: DataFrame[fecha, kwh]}
    """
    partes = [pd.DataFrame({"CUPS": cups, "Fecha hora (fin del cuarto)": df["fecha"],
                            "Consumo (kWh)": df["kwh"]}) for cups, df in curvas.items() if len(df)]
    pd.concat(partes, ignore_index=True).to_csv(ruta, sep=";", index=False, decimal=",", encoding="utf-8-sig")

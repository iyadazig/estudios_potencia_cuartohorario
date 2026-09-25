"""Ventanas de conexión con Gemweb: credenciales y descarga de curvas por CUPS."""

import queue
import tempfile
import threading
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import gemweb
from .gui import FUENTE, FUENTE_B, TARIFAS, boton


class _Cancelado(Exception):
    pass


def _centrar(ventana, padre):
    ventana.update_idletasks()
    x = padre.winfo_rootx() + (padre.winfo_width() - ventana.winfo_reqwidth()) // 2
    y = padre.winfo_rooty() + max(0, (padre.winfo_height() - ventana.winfo_reqheight()) // 3)
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")


class DialogoCredenciales(tk.Toplevel):
    """Usuario y clave de la API de Gemweb; se validan pidiendo un token y se guardan cifrados."""

    def __init__(self, padre):
        super().__init__(padre)
        self.title("Conexión con Gemweb")
        self.resizable(False, False)
        self.ok = False
        marco = ttk.Frame(self, padding=16)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text="Credenciales de la API de Gemweb", font=("Arial", 10, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        actuales = gemweb.cargar_credenciales()
        self.v_id = tk.StringVar(value=actuales[0] if actuales else "")
        self.v_secreto = tk.StringVar(value=actuales[1] if actuales else "")
        ttk.Label(marco, text="Client ID:").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(marco, textvariable=self.v_id, width=40).grid(row=1, column=1, columnspan=2, sticky="we", pady=3)
        ttk.Label(marco, text="Client secret:").grid(row=2, column=0, sticky="w", pady=3)
        ttk.Entry(marco, textvariable=self.v_secreto, width=40, show="•").grid(row=2, column=1, columnspan=2,
                                                                              sticky="we", pady=3)
        ttk.Button(marco, text="Importar de secrets.toml (proyecto API_Gemweb)…",
                   command=self._importar).grid(row=3, column=1, columnspan=2, sticky="w", pady=(4, 8))
        ttk.Label(marco, foreground="#666666", font=("Arial", 8), justify="left",
                  text="Se guardan en tu perfil de Windows (%APPDATA%\\EstudioPotencia) con la clave cifrada:\n"
                       "solo tu usuario puede leerla.").grid(row=4, column=0, columnspan=3, sticky="w")
        pie = ttk.Frame(marco)
        pie.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(pie, text="Cancelar", command=self.destroy).pack(side="right", padx=(6, 0))
        boton(pie, "Probar y guardar", self._guardar, ancho=16, alto=1, fuente=10).pack(side="right")
        self.transient(padre)
        _centrar(self, padre)
        self.grab_set()

    def _importar(self):
        ruta = filedialog.askopenfilename(parent=self, title="secrets.toml del proyecto API_Gemweb",
                                          filetypes=[("secrets.toml", "*.toml"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            cid, sec = gemweb.leer_secrets_toml(ruta)
        except Exception as e:
            messagebox.showerror("No se ha podido leer", f"El fichero no tiene GEMWEB_CLIENT_ID y "
                                 f"GEMWEB_CLIENT_SECRET.\n\n{e}", parent=self)
            return
        self.v_id.set(cid)
        self.v_secreto.set(sec)

    def _guardar(self):
        cid, sec = self.v_id.get().strip(), self.v_secreto.get().strip()
        if not cid or not sec:
            messagebox.showwarning("Faltan datos", "Indica el Client ID y el Client secret.", parent=self)
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            gemweb.ClienteGemweb(cid, sec).comprobar()
        except Exception as e:
            messagebox.showerror("Conexión fallida", str(e), parent=self)
            return
        finally:
            self.config(cursor="")
        gemweb.guardar_credenciales(cid, sec)
        self.ok = True
        self.destroy()


class DialogoGemweb(tk.Toplevel):
    """
    Descarga la curva cuartohoraria (energía en kWh) de los CUPS indicados.
    Resultado (self.resultado): (ruta_csv, {cups: datos del inventario}, avisos, rellenar_datos)
    """

    def __init__(self, padre, credenciales, multipunto=False, cups_inicial=""):
        super().__init__(padre)
        self.title("Descargar curva de Gemweb")
        self.geometry("760x620")
        self.minsize(640, 520)
        self.credenciales = credenciales
        self.multipunto = multipunto
        self.resultado = None
        self._cola = queue.Queue()
        self._cancelar = threading.Event()
        self._hilo = None

        marco = ttk.Frame(self, padding=14)
        marco.pack(fill="both", expand=True)
        cab = ttk.Frame(marco)
        cab.pack(fill="x")
        ttk.Label(cab, text=f"Conectado como: {credenciales[0]}", font=FUENTE_B).pack(side="left")
        ttk.Button(cab, text="Cambiar credenciales…", command=self._cambiar_credenciales).pack(side="right")

        caja = ttk.LabelFrame(marco, text="CUPS a descargar" + (" (uno por línea, o separados por ; o ,)"
                                                              if multipunto else ""), padding=8)
        caja.pack(fill="x", pady=(10, 6))
        if multipunto:
            self.txt_cups = tk.Text(caja, height=6, font=("Consolas", 10), relief="solid", bd=1)
            self.txt_cups.pack(fill="x")
            self.txt_cups.insert("1.0", cups_inicial)
        else:
            self.v_cups = tk.StringVar(value=cups_inicial)
            ttk.Entry(caja, textvariable=self.v_cups, width=34, font=("Consolas", 10)).pack(anchor="w")

        per = ttk.LabelFrame(marco, text="Periodo", padding=8)
        per.pack(fill="x", pady=6)
        ini, fin = gemweb.periodo_defecto()
        self.v_desde = tk.StringVar(value=ini.strftime("%d/%m/%Y"))
        self.v_hasta = tk.StringVar(value=fin.strftime("%d/%m/%Y"))
        ttk.Label(per, text="Desde:").pack(side="left")
        ttk.Entry(per, textvariable=self.v_desde, width=12).pack(side="left", padx=(4, 14))
        ttk.Label(per, text="Hasta:").pack(side="left")
        ttk.Entry(per, textvariable=self.v_hasta, width=12).pack(side="left", padx=4)
        ttk.Label(per, text="(por defecto, los 12 últimos meses completos)", foreground="#666666").pack(
            side="left", padx=10)

        opc = ttk.Frame(marco)
        opc.pack(fill="x", pady=(4, 6))
        self.v_rellenar = tk.BooleanVar(value=True)
        ttk.Checkbutton(opc, variable=self.v_rellenar,
                        text="Rellenar la tarifa, las potencias contratadas y los datos del suministro con los de "
                             "Gemweb").pack(anchor="w")
        self.v_guardar = tk.BooleanVar(value=False)
        ttk.Checkbutton(opc, variable=self.v_guardar,
                        text="Guardar también la curva descargada en un fichero Excel").pack(anchor="w")

        self.progreso = ttk.Progressbar(marco, mode="determinate", maximum=1.0)
        self.progreso.pack(fill="x", pady=(6, 4))
        self.txt_log = tk.Text(marco, height=10, wrap="word", font=FUENTE, relief="flat", bg="#F4F6F8",
                               state="disabled")
        self.txt_log.pack(fill="both", expand=True)

        pie = ttk.Frame(marco)
        pie.pack(fill="x", pady=(10, 0))
        self.btn_cerrar = ttk.Button(pie, text="Cancelar", command=self._cerrar)
        self.btn_cerrar.pack(side="right", padx=(6, 0))
        self.btn_descargar = boton(pie, "🌐  Descargar", self._descargar, ancho=16, alto=1, fuente=10)
        self.btn_descargar.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.transient(padre)
        _centrar(self, padre)
        self.grab_set()

    # ------------------------------------------------------------------
    def _log(self, texto):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", texto + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _cambiar_credenciales(self):
        dlg = DialogoCredenciales(self)
        self.wait_window(dlg)
        if dlg.ok:
            self.credenciales = gemweb.cargar_credenciales()
            self.destroy()
            messagebox.showinfo("Gemweb", "Credenciales guardadas. Vuelve a pulsar «Descargar de Gemweb».")

    def _cerrar(self):
        if self._hilo and self._hilo.is_alive():
            if not messagebox.askyesno("Cancelar", "¿Cancelar la descarga en curso?", parent=self):
                return
            self._cancelar.set()
            self._log("Cancelando…")
            return
        self.destroy()

    def _leer_fecha(self, texto):
        return datetime.strptime(texto.strip(), "%d/%m/%Y").date()

    def _descargar(self):
        cups = gemweb.lista_cups(self.txt_cups.get("1.0", "end") if self.multipunto else self.v_cups.get())
        if not cups:
            messagebox.showwarning("Faltan CUPS", "Indica al menos un CUPS.", parent=self)
            return
        if not self.multipunto and len(cups) > 1:
            messagebox.showwarning("Varios CUPS", "En un estudio individual indica un solo CUPS "
                                   "(para varios, abre un estudio multipunto).", parent=self)
            return
        try:
            desde, hasta = self._leer_fecha(self.v_desde.get()), self._leer_fecha(self.v_hasta.get())
        except ValueError:
            messagebox.showwarning("Fecha no válida", "Escribe las fechas como dd/mm/aaaa.", parent=self)
            return
        if hasta <= desde:
            messagebox.showwarning("Periodo no válido", "La fecha final debe ser posterior a la inicial.", parent=self)
            return
        self.btn_descargar.configure(state="disabled")
        self.btn_cerrar.configure(text="Cancelar descarga")
        self._cancelar.clear()
        self._hilo = threading.Thread(target=self._trabajo, args=(cups, desde, hasta), daemon=True)
        self._hilo.start()
        self.after(200, self._atender_cola)

    # ------------------------------------------------------------------ hilo de descarga
    def _trabajo(self, lista, desde, hasta):
        enviar = self._cola.put
        cliente = gemweb.ClienteGemweb(*self.credenciales)
        curvas, info, avisos = {}, {}, []
        total = len(lista)
        try:
            for i, cups in enumerate(lista):
                if self._cancelar.is_set():
                    raise _Cancelado()
                enviar(("log", f"[{i + 1}/{total}] {cups}: buscando en el inventario de Gemweb…"))
                s = cliente.buscar_suministro(cups)
                if s is None:
                    avisos.append(f"{cups}: no está en el inventario de Gemweb.")
                    enviar(("log", "   ✖ no encontrado"))
                    continue
                tarifa = (s.get("tarifa_acces") or "").strip()
                if tarifa not in TARIFAS:
                    avisos.append(f"{cups}: tarifa {tarifa or 'desconocida'} (el estudio es para 6.1TD y 3.0TD); "
                                  "se descarga igualmente.")
                enviar(("log", f"   id {s['id']} · {tarifa} · {s.get('nom') or ''} · lectura "
                               f"{'cuartohoraria' if s.get('tipus_lectura') == 'quart_hora' else 'HORARIA'}"))

                def avance(n, n_tramos, a, b, i=i):
                    if self._cancelar.is_set():
                        raise _Cancelado()
                    enviar(("progreso", (i + (n - 1) / n_tramos) / total))
                    enviar(("estado", f"{cups}: tramo {n}/{n_tramos} ({a:%d/%m/%Y} – {b:%d/%m/%Y})"))

                # un día de margen a cada lado: el programa se queda luego con los meses completos
                df, fallidos = cliente.descargar_curva(s["id"], desde - timedelta(days=1), hasta + timedelta(days=1),
                                                       avance)
                if df.empty:
                    avisos.append(f"{cups}: Gemweb no tiene telelecturas cuartohorarias en el periodo."
                                  + (f" ({fallidos[0]})" if fallidos else ""))
                    enviar(("log", "   ✖ sin datos"))
                    continue
                for f in fallidos:
                    avisos.append(f"{cups}: tramo sin descargar {f}")
                ini_d, fin_d = df["fecha"].iloc[0], df["fecha"].iloc[-1]
                enviar(("log", f"   ✔ {len(df):,} cuartos de hora ({ini_d[:10]} – {fin_d[:10]})".replace(",", ".")))
                ultimo = datetime.strptime(fin_d[:16], "%Y-%m-%d %H:%M") - timedelta(minutes=15)
                if ultimo.date() < hasta:
                    avisos.append(f"{cups}: Gemweb solo tiene datos hasta el {ultimo:%d/%m/%Y %H:%M}.")
                s["_lectura_horaria"] = s.get("tipus_lectura") != "quart_hora"
                curvas[cups], info[cups] = df, s
            enviar(("fin", (curvas, info, avisos)))
        except _Cancelado:
            enviar(("cancelado", None))
        except Exception as e:
            enviar(("error", str(e)))

    def _atender_cola(self):
        try:
            while True:
                tipo, dato = self._cola.get_nowait()
                if tipo == "log":
                    self._log(dato)
                elif tipo == "estado":
                    self.title(f"Descargar curva de Gemweb – {dato}")
                elif tipo == "progreso":
                    self.progreso["value"] = dato
                elif tipo == "error":
                    self._restaurar()
                    messagebox.showerror("Error de Gemweb", dato, parent=self)
                    return
                elif tipo == "cancelado":
                    self._restaurar()
                    self._log("Descarga cancelada.")
                    return
                elif tipo == "fin":
                    self._terminar(*dato)
                    return
        except queue.Empty:
            pass
        self.after(200, self._atender_cola)

    def _restaurar(self):
        self.title("Descargar curva de Gemweb")
        self.btn_descargar.configure(state="normal")
        self.btn_cerrar.configure(text="Cancelar")

    def _terminar(self, curvas, info, avisos):
        self.progreso["value"] = 1.0
        self._restaurar()
        for a in avisos:
            self._log(f"⚠ {a}")
        if not curvas:
            messagebox.showwarning("Sin datos", "No se ha descargado la curva de ningún CUPS.\n\n" +
                                   "\n".join(avisos[:10]), parent=self)
            return
        carpeta = Path(tempfile.gettempdir()) / "EstudioPotencia"
        carpeta.mkdir(exist_ok=True)
        ruta = carpeta / f"gemweb_{datetime.now():%Y%m%d_%H%M%S}.csv"
        gemweb.escribir_csv(curvas, ruta)
        if self.v_guardar.get():
            destino = filedialog.asksaveasfilename(parent=self, title="Guardar la curva descargada",
                                                   defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                                   initialfile=f"Curva Gemweb {datetime.now():%Y-%m-%d}.xlsx")
            if destino:
                import pandas as pd
                try:
                    pd.read_csv(ruta, sep=";", decimal=",", encoding="utf-8-sig").to_excel(destino, index=False)
                except PermissionError:
                    messagebox.showerror("Error", "No se puede guardar el Excel. ¿Está abierto?", parent=self)
        self.resultado = (ruta, info, avisos, self.v_rellenar.get())
        self.destroy()

"""Interfaz gráfica (tkinter) del estudio de optimización de potencia."""

import os
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .calculo import (N_P, Estudio, Tarifa, cargar_precios, evaluar, fmt, fmt_pot,
                      opciones_inversion_defecto, ruta_recurso, texto_conceptos, validar_potencias)
from .calendario import ZONAS
from .graficos import (AZUL_BOTON, AZUL_OSCURO, COLORES_SUAVES, ROJO_GEYPE, color, dibujar_costes,
                       dibujar_curva_paneles, dibujar_curva_selector, dibujar_maximos)
from .lector_curva import CONVENIOS, UNIDADES, LectorCurva

TARIFAS = ["6.1TD", "3.0TD"]
MAX_PROPUESTAS = 6
FUENTE = ("Arial", 9)
FUENTE_B = ("Arial", 9, "bold")


def _num(texto):
    try:
        return float(str(texto).strip().replace(".", "").replace(",", ".")) if "," in str(texto) \
            else float(str(texto).strip())
    except ValueError:
        return None


def boton(padre, texto, comando, bg=AZUL_BOTON, activo="#125AA0", ancho=26, alto=2, fuente=11):
    return tk.Button(padre, text=texto, command=comando, width=ancho, height=alto, bg=bg, fg="white",
                     font=("Arial", fuente, "bold"), activebackground=activo, activeforeground="white",
                     relief="raised", bd=3, cursor="hand2")


class MarcoDesplazable(ttk.Frame):
    """Frame con barra de desplazamiento vertical."""

    def __init__(self, padre):
        super().__init__(padre)
        self.lienzo = tk.Canvas(self, highlightthickness=0, bg="white")
        barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.interior = tk.Frame(self.lienzo, bg="white")
        self.interior.bind("<Configure>", lambda e: self.lienzo.configure(scrollregion=self.lienzo.bbox("all")))
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")
        self.lienzo.bind("<Configure>", lambda e: self.lienzo.itemconfigure(self._ventana, width=e.width))
        self.lienzo.configure(yscrollcommand=barra.set)
        self.lienzo.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.interior.bind("<Enter>", lambda e: self.lienzo.bind_all("<MouseWheel>", self._rueda))
        self.interior.bind("<Leave>", lambda e: self.lienzo.unbind_all("<MouseWheel>"))

    def _rueda(self, evento):
        self.lienzo.yview_scroll(int(-evento.delta / 120), "units")


# --------------------------------------------------------------------------
# diálogos
# --------------------------------------------------------------------------

class SelectorZona(tk.Toplevel):
    def __init__(self, padre, zona_actual=None):
        super().__init__(padre)
        self.title("Zona del suministro")
        self.resizable(False, False)
        self.zona = None
        self.configure(padx=25, pady=20)
        ttk.Label(self, text="Selecciona la zona del suministro:", font=FUENTE_B).pack(pady=(0, 8))
        self.var = tk.StringVar(value=zona_actual or ZONAS[0])
        ttk.Combobox(self, textvariable=self.var, values=ZONAS, state="readonly", width=28).pack()
        ttk.Label(self, text="Determina las temporadas y horarios de los 6 periodos\n"
                             "(art. 7 de la Circular 3/2020 de la CNMC).",
                  foreground="#555555", justify="center").pack(pady=10)
        boton(self, "Continuar", self._aceptar, ancho=18, alto=1).pack(pady=(5, 0))
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        # si la ventana principal aún está oculta, un diálogo "transient" tampoco se mostraría
        if padre.winfo_viewable():
            self.transient(padre)
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_reqwidth()) // 2
        y = (self.winfo_screenheight() - self.winfo_reqheight()) // 3
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))
        self.focus_force()
        self.grab_set()
        self.bind("<Return>", lambda e: self._aceptar())

    def _aceptar(self):
        self.zona = self.var.get()
        self.destroy()


class DialogoCarga(tk.Toplevel):
    """Muestra cómo se ha interpretado la curva y permite corregir los ajustes."""

    def __init__(self, padre, lector, zona, ajustes=None):
        super().__init__(padre)
        self.title("Interpretación de la curva de carga")
        self.geometry("880x720")
        self.minsize(700, 520)
        self.lector = lector
        self.zona = zona
        self.resultado = None
        ajustes = ajustes or {}

        marco = ttk.Frame(self, padding=12)
        marco.pack(fill="both", expand=True)
        ttk.Label(marco, text=Path(lector.ruta).name, font=("Arial", 10, "bold")).pack(anchor="w")

        opciones = ttk.LabelFrame(marco, text="Ajustes de lectura (se detectan automáticamente)", padding=8)
        opciones.pack(fill="x", pady=8)
        self.v_hoja = tk.StringVar(value=ajustes.get("hoja") or lector.hoja_defecto or "")
        self.v_unidad = tk.StringVar(value=ajustes.get("unidad", UNIDADES[0]))
        self.v_conv = tk.StringVar(value=ajustes.get("convenio", CONVENIOS[0]))
        self.v_cups = tk.StringVar(value=ajustes.get("cups") or "")
        fila = 0
        if len(lector.hojas) > 1:
            ttk.Label(opciones, text="Hoja:").grid(row=fila, column=0, sticky="w")
            ttk.Combobox(opciones, textvariable=self.v_hoja, values=[str(h) for h in lector.hojas],
                         state="readonly", width=30).grid(row=fila, column=1, sticky="w", padx=5, pady=2)
            fila += 1
        ttk.Label(opciones, text="Unidad de los valores:").grid(row=fila, column=0, sticky="w")
        ttk.Combobox(opciones, textvariable=self.v_unidad, values=UNIDADES, state="readonly",
                     width=30).grid(row=fila, column=1, sticky="w", padx=5, pady=2)
        fila += 1
        ttk.Label(opciones, text="La hora de cada registro marca:").grid(row=fila, column=0, sticky="w")
        ttk.Combobox(opciones, textvariable=self.v_conv, values=CONVENIOS, state="readonly",
                     width=30).grid(row=fila, column=1, sticky="w", padx=5, pady=2)
        fila += 1
        self.fila_cups = fila
        self.combo_cups = ttk.Combobox(opciones, textvariable=self.v_cups, state="readonly", width=30)
        ttk.Button(opciones, text="Volver a interpretar", command=self._procesar).grid(
            row=0, column=2, rowspan=2, padx=15)
        self.opciones = opciones

        marco_txt = ttk.Frame(marco)
        marco_txt.pack(fill="x")
        self.resumen = tk.Text(marco_txt, height=12, wrap="word", font=FUENTE, relief="flat", bg="#F4F6F8")
        barra = ttk.Scrollbar(marco_txt, command=self.resumen.yview)
        self.resumen.configure(yscrollcommand=barra.set)
        self.resumen.pack(side="left", fill="x", expand=True)
        barra.pack(side="right", fill="y")

        ttk.Label(marco, text="Primeros registros interpretados:", font=FUENTE_B).pack(anchor="w", pady=(8, 2))
        cols = ("inicio", "fin", "kw", "estimado")
        self.tabla = ttk.Treeview(marco, columns=cols, show="headings", height=8)
        for c, t, w in zip(cols, ("Inicio del cuarto", "Fin del cuarto", "Potencia (kW)", "Estimado"),
                           (180, 180, 120, 90)):
            self.tabla.heading(c, text=t)
            self.tabla.column(c, width=w, anchor="center")
        self.tabla.pack(fill="both", expand=True)

        pie = ttk.Frame(marco)
        pie.pack(fill="x", pady=(10, 0))
        ttk.Button(pie, text="Cancelar", command=self.destroy).pack(side="right", padx=5)
        boton(pie, "✔  Aceptar curva", self._aceptar, ancho=18, alto=1, fuente=10).pack(side="right")

        self.transient(padre)
        self.grab_set()
        self._procesar()

    def _procesar(self):
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            hoja = self.v_hoja.get() if len(self.lector.hojas) > 1 else self.lector.hoja_defecto
            hoja = next((h for h in self.lector.hojas if str(h) == str(hoja)), self.lector.hoja_defecto)
            self.curva = self.lector.procesar(self.zona, self.v_unidad.get(), self.v_conv.get(), hoja,
                                              self.v_cups.get() or None)
        except Exception as e:
            self.curva = None
            self.resumen.delete("1.0", "end")
            self.resumen.insert("end", f"No se ha podido interpretar el fichero:\n{e}")
            return
        finally:
            self.config(cursor="")
        c = self.curva
        if len(self.lector.cups_disponibles) > 1:
            ttk.Label(self.opciones, text="CUPS:").grid(row=self.fila_cups, column=0, sticky="w")
            self.combo_cups.configure(values=self.lector.cups_disponibles)
            self.combo_cups.grid(row=self.fila_cups, column=1, sticky="w", padx=5, pady=2)
            if not self.v_cups.get():
                self.v_cups.set(c.cups or "")
        d = c.datos
        energia = d["kw"].sum() * 0.25
        lineas = [
            f"Columnas usadas: " + ", ".join(f"{k.replace('nombre_', '')} = «{v}»"
                                             for k, v in c.columnas.items() if k.startswith("nombre_")),
            f"Resolución original: {'CUARTOHORARIA (15 min)' if c.resolucion_min == 15 else f'HORARIA ({c.resolucion_min} min)'}"
            f"   ·   Unidad: {c.unidad}   ·   Hora del registro: {c.convenio}",
            f"Periodo: {c.fecha_inicio:%d/%m/%Y %H:%M} – {c.fecha_fin:%d/%m/%Y %H:%M}   ·   "
            f"{len(d):,} cuartos de hora ({c.n_registros:,} registros leídos)".replace(",", "."),
            f"Potencia máxima: {fmt(d['kw'].max(), 1)} kW   ·   Energía total: {fmt(energia)} kWh",
            f"CUPS: {c.cups or 'no incluido en el fichero'}",
        ]
        if c.dias_cambio_hora:
            lineas.append("Cambios de hora: " + "; ".join(c.dias_cambio_hora))
        if c.avisos:
            lineas.append("")
            lineas += [f"⚠ {a}" for a in c.avisos]
        self.resumen.delete("1.0", "end")
        self.resumen.insert("end", "\n".join(lineas))

        self.tabla.delete(*self.tabla.get_children())
        for _, r in d.head(12).iterrows():
            fin = r["inicio"] + np.timedelta64(15, "m")
            self.tabla.insert("", "end", values=(f"{r['inicio']:%d/%m/%Y %H:%M}", f"{fin:%d/%m/%Y %H:%M}",
                                                 fmt(r["kw"], 2), "Sí" if r["estimado"] else ""))

    def _aceptar(self):
        if self.curva is None:
            messagebox.showerror("Curva no válida", "Corrige los ajustes de lectura antes de aceptar.", parent=self)
            return
        self.resultado = self.curva
        self.ajustes = {"hoja": self.curva.hoja, "unidad": self.v_unidad.get(), "convenio": self.v_conv.get(),
                        "cups": self.v_cups.get() or None}
        self.destroy()


# --------------------------------------------------------------------------
# fila de propuesta
# --------------------------------------------------------------------------

class FilaPropuesta:
    ETIQ_INV = [("acometida", "¿Modifica acometida?"), ("acceso", "Derechos de acceso"),
                ("extension", "Derechos de extensión"), ("enganche", "Derechos de enganche")]

    def __init__(self, app, indice, editable):
        self.app = app
        self.indice = indice          # 1 = Propuesta 1 (óptima), 2.. = manuales
        self.editable = editable
        self.vars = [tk.StringVar() for _ in range(N_P)]
        self.inv = {k: tk.BooleanVar(value=(k == "enganche")) for k, _ in self.ETIQ_INV}
        self.inv_manual = False
        self.widgets = []
        self.resultados = {}

    @property
    def nombre(self):
        return f"Propuesta {self.indice}"

    def construir(self, padre, fila):
        c = color(self.indice)
        nombre = self.nombre + (" (óptima)" if self.indice == 1 else "")
        lb = tk.Label(padre, text=nombre, bg=c, fg="white", font=FUENTE_B, padx=6, pady=3, width=16)
        lb.grid(row=fila, column=0, sticky="nsew", padx=1, pady=(4, 0))
        self.widgets.append(lb)
        for p in range(N_P):
            e = tk.Entry(padre, textvariable=self.vars[p], width=7, justify="center", font=FUENTE,
                         relief="solid", bd=1)
            if not self.editable:
                e.configure(state="readonly", readonlybackground="#FDF0E6")
            e.grid(row=fila, column=1 + p, padx=1, pady=(4, 0), sticky="nsew")
            e.bind("<Return>", lambda ev: self.app.calcular())
            self.widgets.append(e)
        for j, clave in enumerate(("fijo", "exceso", "total", "ahorro", "pct", "inversion", "prs")):
            lb = tk.Label(padre, text="", font=FUENTE_B if clave in ("total", "ahorro") else FUENTE,
                          bg=COLORES_SUAVES[self.indice % len(COLORES_SUAVES)], width=9, anchor="e", padx=4)
            lb.grid(row=fila, column=7 + j, sticky="nsew", padx=1, pady=(4, 0))
            self.resultados[clave] = lb
            self.widgets.append(lb)
        inv = tk.Frame(padre, bg="white")
        inv.grid(row=fila + 1, column=1, columnspan=13, sticky="w", pady=(0, 2))
        tk.Label(inv, text="Inversión:", bg="white", fg="#555555", font=("Arial", 8)).pack(side="left")
        for clave, texto in self.ETIQ_INV:
            cb = tk.Checkbutton(inv, text=texto, variable=self.inv[clave], bg="white", font=("Arial", 8),
                                command=self._marcar_manual, activebackground="white")
            cb.pack(side="left", padx=4)
        self.widgets.append(inv)

    def _marcar_manual(self):
        self.inv_manual = True

    def destruir(self):
        for w in self.widgets:
            w.destroy()
        self.widgets = []

    def potencias(self):
        return [_num(v.get()) for v in self.vars]

    def fijar(self, pc):
        for v, p in zip(self.vars, pc):
            v.set(fmt_pot(p).replace(".", ""))

    def vacia(self):
        return all(not v.get().strip() for v in self.vars)

    def opciones(self):
        return {k: v.get() for k, v in self.inv.items()}

    def fijar_opciones(self, op):
        for k, v in op.items():
            self.inv[k].set(v)

    def mostrar(self, esc):
        r = self.resultados
        r["fijo"].config(text=fmt(esc.coste.total_fijo))
        r["exceso"].config(text=fmt(esc.coste.total_exceso))
        r["total"].config(text=fmt(esc.coste.total))
        r["ahorro"].config(text=fmt(esc.ahorro), fg="#C00000" if esc.ahorro < 0 else "black")
        r["pct"].config(text=f"{fmt(100 * esc.ahorro_pct, 1)} %")
        r["inversion"].config(text=fmt(esc.inversion["total"], 2) if esc.inversion.get("total") else "-")
        r["prs"].config(text=fmt(esc.prs, 2) if esc.prs is not None else "-")

    def limpiar_resultados(self):
        for lb in self.resultados.values():
            lb.config(text="")


# --------------------------------------------------------------------------
# aplicación
# --------------------------------------------------------------------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("Optimización de la potencia contratada – GE&PE")
        self.precios = cargar_precios()
        self.zona = None
        self.lector = None
        self.ajustes_carga = None
        self.curva = None
        self.estudio = None
        self._clave_estudio = None
        self._optimo = None
        self.escenarios = None
        self.propuestas = []

        self.iniciada = False
        sel = SelectorZona(self)
        self.wait_window(sel)
        if not sel.zona:
            self.destroy()
            return
        self.iniciada = True
        self.zona = sel.zona

        ancho = min(1500, self.winfo_screenwidth() - 40)
        alto = min(930, self.winfo_screenheight() - 80)
        self.geometry(f"{ancho}x{alto}+10+10")
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self.minsize(1150, 700)
        self.configure(bg="white")
        estilo = ttk.Style(self)
        estilo.configure("Treeview.Heading", font=FUENTE_B)
        estilo.configure("Treeview", font=FUENTE, rowheight=int(22 * self._escala()))
        estilo.configure("TNotebook.Tab", font=FUENTE_B, padding=(10, 4))

        self._construir_cabecera()
        cuerpo = ttk.Frame(self)
        cuerpo.pack(fill="both", expand=True)
        self._construir_panel_izquierdo(cuerpo)
        self._construir_pestanas(cuerpo)
        self.protocol("WM_DELETE_WINDOW", self._salir)
        self.deiconify()

    def _salir(self):
        self.quit()
        self.destroy()

    # ------------------------------------------------------------------ cabecera
    def _construir_cabecera(self):
        cab = tk.Frame(self, bg="white")
        cab.pack(fill="x")
        try:
            from PIL import Image, ImageTk
            im = Image.open(ruta_recurso("assets/logo_geype.png"))
            im.thumbnail((200, 52))
            fondo = Image.new("RGBA", im.size, "white")
            fondo.alpha_composite(im.convert("RGBA"))
            self._logo = ImageTk.PhotoImage(fondo)
            tk.Label(cab, image=self._logo, bg="white").pack(side="left", padx=12, pady=6)
        except Exception:
            pass
        tk.Label(cab, text="Optimización de la potencia contratada", bg="white", fg=ROJO_GEYPE,
                 font=("Arial", 16, "bold")).pack(side="left", padx=10)
        der = tk.Frame(cab, bg="white")
        der.pack(side="right", padx=12)
        self.lb_zona = tk.Label(der, text=f"Zona: {self.zona}", bg="white", font=("Arial", 10, "bold"))
        self.lb_zona.pack(side="left")
        ttk.Button(der, text="Cambiar zona", command=self._cambiar_zona).pack(side="left", padx=8)
        tk.Frame(self, bg=ROJO_GEYPE, height=3).pack(fill="x")

    def _cambiar_zona(self):
        sel = SelectorZona(self, self.zona)
        self.wait_window(sel)
        if sel.zona and sel.zona != self.zona:
            self.zona = sel.zona
            self.lb_zona.config(text=f"Zona: {self.zona}")
            if self.lector is not None:        # los cambios de hora dependen de la zona (Canarias)
                a = self.ajustes_carga or {}
                self.curva = self.lector.procesar(self.zona, a.get("unidad", UNIDADES[0]),
                                                  a.get("convenio", CONVENIOS[0]), a.get("hoja"), a.get("cups"))
            self._invalidar()

    # ------------------------------------------------------------------ panel izquierdo
    def _construir_panel_izquierdo(self, padre):
        izq = ttk.Frame(padre, padding=(10, 8))
        izq.pack(side="left", fill="y")

        datos = ttk.LabelFrame(izq, text="Datos del suministro", padding=8)
        datos.pack(fill="x")
        self.v_datos = {}
        campos = [("titular", "Titular"), ("cups", "CUPS"), ("instalacion", "Instalación"),
                  ("direccion", "Dirección"), ("fecha", "Fecha del estudio")]
        for i, (clave, texto) in enumerate(campos):
            ttk.Label(datos, text=texto + ":").grid(row=i, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=date.today().strftime("%d/%m/%Y") if clave == "fecha" else "")
            ttk.Entry(datos, textvariable=v, width=30).grid(row=i, column=1, sticky="we", pady=2, padx=(5, 0))
            self.v_datos[clave] = v
        ttk.Label(datos, text="Tarifa:").grid(row=len(campos), column=0, sticky="w", pady=2)
        self.v_tarifa = tk.StringVar(value=TARIFAS[0])
        cb = ttk.Combobox(datos, textvariable=self.v_tarifa, values=TARIFAS, state="readonly", width=12)
        cb.grid(row=len(campos), column=1, sticky="w", pady=2, padx=(5, 0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._invalidar())

        curva = ttk.LabelFrame(izq, text="Curva de carga", padding=8)
        curva.pack(fill="x", pady=8)
        ttk.Button(curva, text="📂  Cargar curva de carga…", command=self.cargar_curva).pack(fill="x")
        self.lb_curva = ttk.Label(curva, text="Ninguna curva cargada.\nFormatos: CSV, TXT, XLSX, XLS "
                                              "(cuartohoraria u horaria, kW o kWh).",
                                  wraplength=320, foreground="#555555", justify="left")
        self.lb_curva.pack(fill="x", pady=(6, 0))

        pot = ttk.LabelFrame(izq, text="Potencias contratadas actuales (kW)", padding=8)
        pot.pack(fill="x")
        self.v_actual = [tk.StringVar() for _ in range(N_P)]
        for p in range(N_P):
            ttk.Label(pot, text=f"P{p + 1}", font=FUENTE_B).grid(row=0, column=p, padx=2)
            e = tk.Entry(pot, textvariable=self.v_actual[p], width=7, justify="center", relief="solid", bd=1)
            e.grid(row=1, column=p, padx=2, pady=2)
            e.bind("<Return>", lambda ev: self.calcular())

        ttk.Separator(izq).pack(fill="x", pady=12)
        boton(izq, "🚀  CALCULAR", self.calcular).pack(pady=(0, 10))
        boton(izq, "📄  EXPORTAR PDF", self.exportar_pdf, bg=ROJO_GEYPE, activo="#7A1518").pack()

        info = ttk.Label(izq, wraplength=330, foreground="#666666", justify="left", font=("Arial", 8),
                         text="Propuesta 1 = potencias óptimas calculadas (enteras, con P1 ≤ … ≤ P6).\n"
                              "Propuestas 2 y siguientes = editables; pulsa CALCULAR para recalcular.\n"
                              f"Precios regulados {self.precios.get('vigencia', '')} (config/precios.json).")
        info.pack(side="bottom", fill="x")

    # ------------------------------------------------------------------ pestañas
    def _construir_pestanas(self, padre):
        self.nb = ttk.Notebook(padre)
        self.nb.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.after(80, self._dibujar_pendientes))
        self._pendientes = set()

        # --- Resumen
        desp = MarcoDesplazable(self.nb)
        self.nb.add(desp, text="Resumen")
        res = desp.interior
        arriba = tk.Frame(res, bg="white")
        arriba.pack(fill="x", padx=6, pady=6)
        self.cont_tabla_mes = tk.Frame(arriba, width=600, height=330, bg="white")
        self.cont_tabla_mes.pack_propagate(False)
        self.cont_tabla_mes.pack(side="left", fill="y")
        self.tabla_mes = ttk.Treeview(self.cont_tabla_mes, show="headings", height=14)
        self.tabla_mes.pack(fill="both", expand=True)
        self.tabla_mes.tag_configure("total", font=FUENTE_B, background="#DCE6F1")
        self.tabla_mes.tag_configure("par", background="#F4F7FB")
        self.fig_costes = Figure(figsize=(4.5, 2.6), dpi=100, layout="constrained")
        self.canvas_costes = FigureCanvasTkAgg(self.fig_costes, arriba)
        self.canvas_costes.get_tk_widget().pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(res, text="OPTIMIZACIÓN DE POTENCIA (sin i.e.)", bg=AZUL_OSCURO, fg="white",
                 font=("Arial", 10, "bold"), pady=3).pack(fill="x", padx=6, pady=(8, 0))
        self.rejilla = tk.Frame(res, bg="white")
        self.rejilla.pack(fill="x", padx=6)
        cab = ["Tipo"] + [f"P{i} (kW)" for i in range(1, 7)] + \
            ["T. Fijo (€)", "T. Excesos (€)", "Total (€)", "Ahorro (€) *", "%", "Inversión (€)", "PRS (años)"]
        for j, t in enumerate(cab):
            tk.Label(self.rejilla, text=t, bg=AZUL_OSCURO, fg="white", font=FUENTE_B, padx=4,
                     pady=3).grid(row=0, column=j, sticky="nsew", padx=1, pady=1)
        tk.Label(self.rejilla, text="Actual", bg=color(0), fg="white", font=FUENTE_B, padx=6,
                 pady=3, width=16).grid(row=1, column=0, sticky="nsew", padx=1)
        self.lb_actual = []
        for p in range(N_P):
            lb = tk.Label(self.rejilla, text="", bg="#E2EFDA", font=FUENTE, width=7)
            lb.grid(row=1, column=1 + p, sticky="nsew", padx=1)
            self.lb_actual.append(lb)
        self.res_actual = {}
        for j, clave in enumerate(("fijo", "exceso", "total", "ahorro", "pct", "inversion", "prs")):
            lb = tk.Label(self.rejilla, text="-" if j >= 3 else "", bg="#E2EFDA", font=FUENTE, width=9,
                          anchor="e", padx=4)
            lb.grid(row=1, column=7 + j, sticky="nsew", padx=1)
            self.res_actual[clave] = lb

        barra = tk.Frame(res, bg="white")
        barra.pack(fill="x", padx=6, pady=6)
        mb = tk.Menubutton(barra, text="➕  Propuestas  ▾", bg=AZUL_BOTON, fg="white", font=FUENTE_B,
                           activebackground="#125AA0", activeforeground="white", relief="raised", bd=2,
                           padx=10, pady=4, cursor="hand2")
        menu = tk.Menu(mb, tearoff=False)
        menu.add_command(label="Añadir otra propuesta", command=self.anadir_propuesta)
        menu.add_command(label="Eliminar la última propuesta", command=self.eliminar_propuesta)
        menu.add_separator()
        menu.add_command(label="Copiar la óptima en las propuestas editables", command=self.copiar_optima)
        mb.configure(menu=menu)
        mb.pack(side="left")
        self.lb_notas = tk.Label(res, bg="white", fg="#444444", font=("Arial", 8), justify="left",
                                 anchor="w", wraplength=1000)
        self.lb_notas.pack(fill="x", padx=8, pady=(0, 10))

        self.propuestas = [FilaPropuesta(self, 1, editable=False), FilaPropuesta(self, 2, editable=True)]
        self._redibujar_propuestas()

        # --- Anexos
        self.tabla_energia = self._pestana_tabla("Anexo: Energía (kWh)")
        marco_max = ttk.Frame(self.nb)
        self.nb.add(marco_max, text="Anexo: Potencias máximas (kW)")
        self.tabla_max = self._tabla(marco_max, height=15)
        self.tabla_max.pack(fill="x", padx=6, pady=6)
        self.fig_max = Figure(figsize=(5, 2.2), dpi=100, layout="constrained")
        self.canvas_max = FigureCanvasTkAgg(self.fig_max, marco_max)
        self.canvas_max.get_tk_widget().pack(fill="both", expand=True)

        marco_det = ttk.Frame(self.nb)
        self.nb.add(marco_det, text="Anexo: Detalle de costes")
        sup = ttk.Frame(marco_det)
        sup.pack(fill="x", padx=6, pady=6)
        ttk.Label(sup, text="Escenario:").pack(side="left")
        self.v_det = tk.StringVar()
        self.combo_det = ttk.Combobox(sup, textvariable=self.v_det, state="readonly", width=20)
        self.combo_det.pack(side="left", padx=6)
        self.combo_det.bind("<<ComboboxSelected>>", lambda e: self._mostrar_detalle())
        ttk.Label(sup, text="Importes en € sin impuesto eléctrico. Desglose por periodos a la derecha.",
                  foreground="#666666").pack(side="left", padx=15)
        self.tabla_det = self._tabla(marco_det, height=16)
        barra_h = ttk.Scrollbar(marco_det, orient="horizontal", command=self.tabla_det.xview)
        self.tabla_det.configure(xscrollcommand=barra_h.set)
        self.tabla_det.pack(fill="both", expand=True, padx=6)
        barra_h.pack(fill="x", padx=6, pady=(0, 6))

        marco_pan = ttk.Frame(self.nb)
        self.nb.add(marco_pan, text="Anexo: Curva por periodos")
        self.fig_paneles = Figure(figsize=(5, 3), dpi=100, layout="constrained")
        self.canvas_paneles = FigureCanvasTkAgg(self.fig_paneles, marco_pan)
        self.canvas_paneles.get_tk_widget().pack(fill="both", expand=True)

        marco_sel = ttk.Frame(self.nb)
        self.nb.add(marco_sel, text="Anexo: Curva (selector)")
        filtros = ttk.Frame(marco_sel)
        filtros.pack(fill="x", padx=6, pady=6)
        ttk.Label(filtros, text="Periodo:").pack(side="left")
        self.v_sel_periodo = tk.StringVar(value="Todos")
        cb = ttk.Combobox(filtros, textvariable=self.v_sel_periodo, state="readonly", width=8,
                          values=["Todos"] + [f"P{i}" for i in range(1, 7)])
        cb.pack(side="left", padx=(4, 15))
        cb.bind("<<ComboboxSelected>>", lambda e: self._redibujar_selector())
        ttk.Label(filtros, text="Mes:").pack(side="left")
        self.v_sel_mes = tk.StringVar(value="Año completo")
        self.combo_sel_mes = ttk.Combobox(filtros, textvariable=self.v_sel_mes, state="readonly", width=14)
        self.combo_sel_mes.pack(side="left", padx=4)
        self.combo_sel_mes.bind("<<ComboboxSelected>>", lambda e: self._redibujar_selector())
        ttk.Label(filtros, foreground="#666666",
                  text="Con «Todos», la línea de cada escenario es la potencia contratada del periodo de cada "
                       "cuarto de hora (elige un mes para verlo con claridad).").pack(side="left", padx=15)
        self.fig_curva = Figure(figsize=(5, 3), dpi=100, layout="constrained")
        self.canvas_curva = FigureCanvasTkAgg(self.fig_curva, marco_sel)
        self.canvas_curva.get_tk_widget().pack(fill="both", expand=True)

        marco_log = ttk.Frame(self.nb)
        self.nb.add(marco_log, text="Registro de carga")
        self.txt_log = tk.Text(marco_log, wrap="word", font=FUENTE)
        self.txt_log.pack(fill="both", expand=True, padx=6, pady=6)

    def _dibujar_pendientes(self):
        """Dibuja los gráficos de la pestaña visible (una figura oculta se dimensiona mal)."""
        if not self.escenarios:
            return
        pestana = self.nb.index("current")
        graficos = {0: ("costes", self.fig_costes, self.canvas_costes,
                        lambda: dibujar_costes(self.fig_costes, self.estudio, self.escenarios)),
                    2: ("max", self.fig_max, self.canvas_max,
                        lambda: dibujar_maximos(self.fig_max, self.estudio, self.escenarios[0].pc)),
                    4: ("paneles", self.fig_paneles, self.canvas_paneles,
                        lambda: dibujar_curva_paneles(self.fig_paneles, self.estudio, self.escenarios)),
                    5: ("curva", self.fig_curva, self.canvas_curva, self._dibujar_selector)}
        if pestana not in graficos or graficos[pestana][0] not in self._pendientes:
            return
        clave, fig, canvas, dibujar = graficos[pestana]
        w = canvas.get_tk_widget()
        self.update_idletasks()
        if w.winfo_width() > 10:
            fig.set_size_inches(w.winfo_width() / fig.dpi, w.winfo_height() / fig.dpi, forward=False)
        dibujar()
        canvas.draw()
        self._pendientes.discard(clave)

    def _dibujar_selector(self):
        per = self.v_sel_periodo.get()
        periodo = 0 if per == "Todos" else int(per[1])
        meses = self.estudio.etiquetas_meses
        mes = meses.index(self.v_sel_mes.get()) if self.v_sel_mes.get() in meses else None
        dibujar_curva_selector(self.fig_curva, self.estudio, self.escenarios, periodo, mes)

    def _redibujar_selector(self):
        self._pendientes.add("curva")
        self._dibujar_pendientes()

    def _tabla(self, padre, height=14):
        t = ttk.Treeview(padre, show="headings", height=height)
        t.tag_configure("total", font=FUENTE_B, background="#DCE6F1")
        t.tag_configure("par", background="#F4F7FB")
        return t

    def _pestana_tabla(self, titulo):
        marco = ttk.Frame(self.nb)
        self.nb.add(marco, text=titulo)
        t = self._tabla(marco, height=16)
        t.pack(fill="x", padx=6, pady=6)
        return t

    def _escala(self):
        """Factor de escala de pantalla (DPI) para dimensionar columnas en píxeles."""
        return max(1.0, float(self.tk.call("tk", "scaling")) / 1.333)

    @staticmethod
    def _rellenar(tabla, columnas, filas, anchos=None, totales=0):
        tabla.delete(*tabla.get_children())
        tabla["columns"] = [f"c{i}" for i in range(len(columnas))]
        for i, c in enumerate(columnas):
            tabla.heading(f"c{i}", text=c)
            tabla.column(f"c{i}", width=(anchos[i] if anchos else 90), anchor="center", stretch=False)
        for k, f in enumerate(filas):
            tag = "total" if k >= len(filas) - totales else ("par" if k % 2 else "")
            tabla.insert("", "end", values=f, tags=(tag,))

    # ------------------------------------------------------------------ propuestas
    def _redibujar_propuestas(self):
        for fp in self.propuestas:
            fp.destruir()
        for k, fp in enumerate(self.propuestas):
            fp.construir(self.rejilla, 2 + 2 * k)

    def anadir_propuesta(self):
        if len(self.propuestas) >= MAX_PROPUESTAS:
            messagebox.showinfo("Propuestas", f"Máximo {MAX_PROPUESTAS} propuestas.")
            return
        fp = FilaPropuesta(self, len(self.propuestas) + 1, editable=True)
        self.propuestas.append(fp)
        fp.construir(self.rejilla, 2 + 2 * (len(self.propuestas) - 1))
        if self._optimo is not None:
            fp.fijar(self._optimo)

    def eliminar_propuesta(self):
        if len(self.propuestas) <= 2:
            messagebox.showinfo("Propuestas", "La Propuesta 1 (óptima) y la Propuesta 2 no se pueden eliminar.")
            return
        self.propuestas.pop().destruir()
        if self.escenarios:
            self.calcular()

    def copiar_optima(self):
        if self._optimo is None:
            messagebox.showinfo("Propuestas", "Primero pulsa CALCULAR para obtener la potencia óptima.")
            return
        for fp in self.propuestas[1:]:
            fp.fijar(self._optimo)

    # ------------------------------------------------------------------ carga
    def cargar_curva(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona la curva de carga",
            filetypes=[("Curvas de carga", "*.csv *.txt *.xlsx *.xlsm *.xls *.dat"), ("Todos", "*.*")])
        if not ruta:
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            lector = LectorCurva(ruta)
        except Exception as e:
            messagebox.showerror("Error al leer el fichero", str(e))
            return
        finally:
            self.config(cursor="")
        dlg = DialogoCarga(self, lector, self.zona)
        self.wait_window(dlg)
        if dlg.resultado is None:
            return
        self.lector, self.curva, self.ajustes_carga = lector, dlg.resultado, dlg.ajustes
        c = self.curva
        if c.cups and not self.v_datos["cups"].get().strip():
            self.v_datos["cups"].set(c.cups)
        tipo = "cuartohoraria" if c.resolucion_min == 15 else "HORARIA (cuartos estimados)"
        texto = (f"{Path(ruta).name}\n{c.fecha_inicio:%d/%m/%Y} – {(c.fecha_fin - np.timedelta64(1, 'D')):%d/%m/%Y}"
                 f"  ·  {tipo}  ·  {c.unidad}\nPotencia máxima: {fmt(c.datos['kw'].max(), 1)} kW")
        if c.avisos:
            texto += f"\n⚠ {len(c.avisos)} aviso(s): ver pestaña «Registro de carga»"
        self.lb_curva.config(text=texto, foreground="black")
        self._escribir_log()
        self._invalidar()
        for fp in self.propuestas[1:]:
            fp.inv_manual = False
            for v in fp.vars:
                v.set("")
        self.propuestas[0].inv_manual = False
        if all(_num(v.get()) for v in self.v_actual):
            self.calcular()

    def _escribir_log(self):
        c = self.curva
        self.txt_log.delete("1.0", "end")
        lineas = [f"Fichero: {c.archivo}", f"Hoja: {c.hoja}" if c.hoja else "",
                  f"Resolución original: {c.resolucion_min} min · Unidad: {c.unidad} · Hora del registro: {c.convenio}",
                  f"Registros leídos: {c.n_registros:,}".replace(",", "."),
                  f"Periodo del estudio: {c.fecha_inicio:%d/%m/%Y %H:%M} – {c.fecha_fin:%d/%m/%Y %H:%M}",
                  f"Intervalos rellenados (huecos): {c.huecos_rellenados}",
                  "Cambios de hora: " + ("; ".join(c.dias_cambio_hora) or "ninguno"), "", "Avisos:"]
        lineas += [f"  • {a}" for a in c.avisos] or ["  (ninguno)"]
        self.txt_log.insert("end", "\n".join(l for l in lineas if l is not None))

    # ------------------------------------------------------------------ cálculo
    def _invalidar(self):
        self.estudio = None
        self._clave_estudio = None
        self.escenarios = None

    def _obtener_estudio(self):
        clave = (id(self.curva), self.zona, self.v_tarifa.get())
        if self.estudio is None or self._clave_estudio != clave:
            tarifa = Tarifa.desde_precios(self.precios, self.v_tarifa.get())
            self.estudio = Estudio(self.curva.datos, self.zona, tarifa, self.precios.get("festivos"))
            self._clave_estudio = clave
            self._optimo = self.estudio.optimo()
        return self.estudio

    def calcular(self):
        if self.curva is None:
            messagebox.showwarning("Falta la curva", "Carga primero la curva de carga.")
            return
        actual = [_num(v.get()) for v in self.v_actual]
        if any(p is None or p <= 0 for p in actual):
            messagebox.showwarning("Faltan datos", "Introduce las 6 potencias contratadas actuales.")
            return
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            est = self._obtener_estudio()
            opt = self._optimo
            self.propuestas[0].fijar(opt)
            for fp in self.propuestas[1:]:
                if fp.vacia():
                    fp.fijar(opt)
            propuestas = []
            for fp in self.propuestas:
                pc = fp.potencias()
                err = validar_potencias(pc)
                if err:
                    messagebox.showerror(f"{fp.nombre} no válida", err)
                    return
                if not fp.inv_manual:
                    fp.fijar_opciones(opciones_inversion_defecto(pc, actual))
                propuestas.append((fp.nombre, pc, fp.opciones()))
            self.escenarios = evaluar(est, propuestas, actual)
        finally:
            self.config(cursor="")
        self._mostrar_resultados()
        self._avisos_calculo(actual)

    def _avisos_calculo(self, actual):
        avisos = []
        err = validar_potencias(actual)
        if err:
            avisos.append("Las potencias actuales no cumplen la condición P1 ≤ … ≤ P6.")
        pmax = self.estudio.max_demanda()
        if pmax > 3 * max(actual) or pmax < 0.15 * max(actual):
            avisos.append(f"La potencia máxima de la curva ({fmt(pmax, 1)} kW) es muy distinta de la contratada "
                          f"({fmt(max(actual))} kW). Revisa la unidad de la curva (kW / kWh).")
        if self.v_tarifa.get() == "3.0TD" and max(self._optimo) <= 50:
            avisos.append("La potencia óptima no supera 50 kW: con 3.0TD ≤ 50 kW el punto de medida sería tipo 4 "
                          "y los excesos se facturarían por maxímetro, no por cuartos de hora.")
        if avisos:
            messagebox.showwarning("Revisa", "\n\n".join(avisos))

    def _mostrar_resultados(self):
        est, escs = self.estudio, self.escenarios
        actual = escs[0]
        for p, lb in enumerate(self.lb_actual):
            lb.config(text=fmt_pot(actual.pc[p]))
        self.res_actual["fijo"].config(text=fmt(actual.coste.total_fijo))
        self.res_actual["exceso"].config(text=fmt(actual.coste.total_exceso))
        self.res_actual["total"].config(text=fmt(actual.coste.total), font=FUENTE_B)
        for fp, esc in zip(self.propuestas, escs[1:]):
            fp.mostrar(esc)

        # tabla mensual
        prop = escs[1:]
        cols = ["Mes"] + ["Actual"] + [f"Prop. {e.nombre.split()[-1]}" for e in prop] +             [f"Ahorro P{e.nombre.split()[-1]}" for e in prop]
        filas = []
        for i, m in enumerate(est.etiquetas_meses):
            filas.append([m] + [fmt(e.coste.total_mes[i]) for e in escs] +
                         [fmt(actual.coste.total_mes[i] - e.coste.total_mes[i]) for e in prop])
        filas.append(["Total"] + [fmt(e.coste.total) for e in escs] + [fmt(e.ahorro) for e in prop])
        esc = self._escala()
        anchos = [int(64 * esc)] + [int(78 * esc)] * len(escs) + [int(80 * esc)] * len(prop)
        self._rellenar(self.tabla_mes, cols, filas, anchos, totales=1)
        self.cont_tabla_mes.configure(width=sum(anchos) + 6, height=int(22 * esc) * (len(filas) + 1) + 12)


        inv = [f"{e.nombre}: {texto_conceptos(e.inversion['conceptos'])}" for e in prop if e.inversion.get("total")]
        d = est.tarifa.derechos
        self.lb_notas.config(text=(
            "* Ahorro respecto al coste actual; % sobre el coste de potencia actual. Importes sin impuesto eléctrico.\n"
            f"Inversión ({d.get('nombre', '')}): acceso {fmt(d['acceso'], 6)} €/kW y extensión {fmt(d['extension'], 6)} €/kW "
            f"sobre el aumento de la potencia máxima respecto a la actual; enganche {fmt(d['enganche'], 2)} €. "
            "Si la ampliación es > 250 kW o en suelo no urbanizable, la extensión no se incluye (la ejecuta el titular).\n"
            + ("Conceptos → " + " · ".join(inv) if inv else "")))

        # anexos
        e_kwh = est.energia_kwh()
        maximos = est.maximos()
        cols = ["Mes"] + [f"P{i}" for i in range(1, 7)] + ["Total"]
        filas = [[m] + [fmt(v) for v in e_kwh[i]] + [fmt(e_kwh[i].sum())] for i, m in enumerate(est.etiquetas_meses)]
        tot = e_kwh.sum(0)
        filas.append(["Total"] + [fmt(v) for v in tot] + [fmt(tot.sum())])
        filas.append(["%"] + [f"{fmt(100 * v / tot.sum(), 1)} %" for v in tot] + [""])
        self._rellenar(self.tabla_energia, cols, filas, [int(x * self._escala()) for x in [70] + [100] * 7], totales=2)

        cols = ["Mes"] + [f"P{i}" for i in range(1, 7)] + ["Máximo"]
        filas = [[m] + [fmt(v) for v in maximos[i]] + [fmt(maximos[i].max())] for i, m in enumerate(est.etiquetas_meses)]
        filas.append(["Máximo"] + [fmt(v) for v in maximos.max(0)] + [fmt(maximos.max())])
        self._rellenar(self.tabla_max, cols, filas, [int(x * self._escala()) for x in [70] + [95] * 7], totales=1)

        self.combo_det.configure(values=[e.nombre for e in escs])
        if self.v_det.get() not in [e.nombre for e in escs]:
            self.v_det.set(escs[0].nombre)
        self._mostrar_detalle()

        self.combo_sel_mes.configure(values=["Año completo"] + est.etiquetas_meses)
        if self.v_sel_mes.get() not in ["Año completo"] + est.etiquetas_meses:
            self.v_sel_mes.set("Año completo")
        self._pendientes = {"costes", "max", "paneles", "curva"}
        self._dibujar_pendientes()

    def _mostrar_detalle(self):
        if not self.escenarios:
            return
        esc = next((e for e in self.escenarios if e.nombre == self.v_det.get()), self.escenarios[0])
        est = self.estudio
        c = esc.coste
        cols = ["Mes", "Días", "Total fijo", "Total excesos", "TOTAL"] +             [f"Fijo P{i}" for i in range(1, 7)] + [f"Exceso P{i}" for i in range(1, 7)]
        filas = []
        for i, m in enumerate(est.etiquetas_meses):
            filas.append([m, est.dias_mes[i], fmt(c.fijo[i].sum(), 2), fmt(c.exceso[i].sum(), 2),
                          fmt(c.total_mes[i], 2)] + [fmt(v, 2) for v in c.fijo[i]] + [fmt(v, 2) for v in c.exceso[i]])
        filas.append(["Total", est.dias_totales, fmt(c.total_fijo, 2), fmt(c.total_exceso, 2), fmt(c.total, 2)] +
                     [fmt(v, 2) for v in c.fijo.sum(0)] + [fmt(v, 2) for v in c.exceso.sum(0)])
        anchos = [60, 40, 92, 104, 92] + [66] * 12
        self._rellenar(self.tabla_det, cols, filas, [int(x * self._escala()) for x in anchos], totales=1)

    # ------------------------------------------------------------------ PDF
    def exportar_pdf(self):
        if not self.escenarios:
            messagebox.showwarning("Sin resultados", "Pulsa CALCULAR antes de exportar el informe.")
            return
        from .informe_pdf import generar_pdf
        d = {k: v.get().strip() for k, v in self.v_datos.items()}
        d["tarifa"] = self.v_tarifa.get()
        d["zona"] = self.zona
        nombre = f"Estudio potencia {d.get('titular') or ''} ({d.get('instalacion') or ''})".strip()
        nombre = "".join(ch for ch in nombre if ch not in '\\/:*?"<>|') + ".pdf"
        ruta = filedialog.asksaveasfilename(title="Guardar informe PDF", defaultextension=".pdf",
                                            initialfile=nombre, filetypes=[("PDF", "*.pdf")])
        if not ruta:
            return
        anexos = messagebox.askyesno("Anexos", "¿Incluir los anexos (energía, potencias máximas y curva de carga)?")
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            generar_pdf(ruta, d, self.estudio, self.escenarios, self.curva, self.precios.get("normativa", []),
                        incluir_anexos=anexos)
        except PermissionError:
            messagebox.showerror("Error", "No se puede escribir el PDF. ¿Está abierto en otro programa?")
            return
        except Exception as e:
            messagebox.showerror("Error al generar el PDF", str(e))
            return
        finally:
            self.config(cursor="")
        if messagebox.askyesno("Informe generado", f"PDF guardado en:\n{ruta}\n\n¿Abrirlo ahora?"):
            try:
                os.startfile(ruta)
            except Exception:
                pass


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = App()
    if app.iniciada:
        app.mainloop()

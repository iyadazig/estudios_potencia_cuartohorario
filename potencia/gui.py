"""Interfaz gráfica (tkinter) del estudio de optimización de potencia."""

import os
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .calculo import (N_P, Estudio, ResumenMultipunto, Tarifa, cargar_precios, evaluar, fmt, fmt_pot,
                      opciones_inversion_defecto, ruta_recurso, texto_conceptos, validar_potencias)
from .calendario import ZONAS
from .graficos import (AZUL_BOTON, AZUL_OSCURO, COLORES_SUAVES, ROJO_GEYPE, color, dibujar_costes,
                       dibujar_curva_selector, dibujar_maximos)
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

class TablaColores(tk.Frame):
    """Tabla de etiquetas con color de fondo por columna (el Treeview solo colorea filas)."""

    FONDOS = ("white", "#F4F7FB")
    FONDO_TOTAL = "#DCE6F1"

    def __init__(self, padre):
        super().__init__(padre, bg="white")

    def rellenar(self, columnas, filas, anchos, colores=None, izquierda=()):
        """colores: {índice de columna: (fondo de las filas, fondo de la fila de totales)};
        izquierda: columnas de texto alineadas a la izquierda."""
        colores = colores or {}
        for w in self.winfo_children():
            w.destroy()
        for j, c in enumerate(columnas):
            tk.Label(self, text=c, bg=AZUL_OSCURO, fg="white", font=("Arial", 8, "bold"), width=anchos[j],
                     pady=4).grid(row=0, column=j, sticky="nsew", padx=(0, 1), pady=(0, 1))
        for i, fila in enumerate(filas):
            total = i == len(filas) - 1
            for j, v in enumerate(fila):
                if j in colores:
                    fondo = colores[j][1 if total else 0]
                else:
                    fondo = self.FONDO_TOTAL if total else self.FONDOS[i % 2]
                negrita = total or j in colores or j == 0
                tk.Label(self, text=v, bg=fondo, font=("Arial", 8, "bold") if negrita else ("Arial", 8),
                         width=anchos[j], anchor="w" if j in izquierda else ("center" if j < 2 else "e"),
                         padx=2, pady=3).grid(row=i + 1, column=j,
                                                                                  sticky="nsew", padx=(0, 1))


class SelectorZona(tk.Toplevel):
    """Ventana inicial: tipo de estudio (individual / multipunto) y zona."""

    def __init__(self, padre, zona_actual=None, mostrar_modo=True):
        super().__init__(padre)
        self.title("Nuevo estudio" if mostrar_modo else "Zona del suministro")
        self.resizable(False, False)
        self.zona = None
        self.modo = "individual"
        self.configure(padx=25, pady=20)
        self.v_modo = tk.StringVar(value="individual")
        if mostrar_modo:
            ttk.Label(self, text="Tipo de estudio:", font=FUENTE_B).pack(pady=(0, 4))
            fila = ttk.Frame(self)
            fila.pack(pady=(0, 12))
            ttk.Radiobutton(fila, text="Individual (un CUPS)", variable=self.v_modo,
                            value="individual").pack(side="left", padx=8)
            ttk.Radiobutton(fila, text="Multipunto (varios CUPS en un fichero)", variable=self.v_modo,
                            value="multipunto").pack(side="left", padx=8)
        ttk.Label(self, text="Selecciona la zona del suministro:" if not mostrar_modo else
                  "Zona (en multipunto, zona por defecto de cada CUPS):", font=FUENTE_B).pack(pady=(0, 8))
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
        self.modo = self.v_modo.get()
        self.destroy()


class DialogoCarga(tk.Toplevel):
    """Muestra cómo se ha interpretado la curva y permite corregir los ajustes."""

    def __init__(self, padre, lector, zona, ajustes=None, multipunto=False):
        super().__init__(padre)
        self.multipunto = multipunto
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
        if len(self.lector.cups_disponibles) > 1 and not self.multipunto:
            ttk.Label(self.opciones, text="CUPS:").grid(row=self.fila_cups, column=0, sticky="w")
            self.combo_cups.configure(values=self.lector.cups_disponibles)
            self.combo_cups.grid(row=self.fila_cups, column=1, sticky="w", padx=5, pady=2)
            if not self.v_cups.get():
                self.v_cups.set(c.cups or "")
        d = c.datos
        energia = d["kw"].sum() * 0.25
        lineas = [
            "Columnas usadas: " + ", ".join(f"{k.replace('nombre_', '')} = «{v}»"
                                             for k, v in c.columnas.items() if k.startswith("nombre_")),
            f"Resolución original: {'CUARTOHORARIA (15 min)' if c.resolucion_min == 15 else f'HORARIA ({c.resolucion_min} min)'}"
            f"   ·   Hora del registro: {c.convenio}",
            f"Unidad: {c.descripcion_unidad}",
            f"Periodo: {c.fecha_inicio:%d/%m/%Y %H:%M} – {c.fecha_fin:%d/%m/%Y %H:%M}   ·   "
            f"{len(d):,} cuartos de hora ({c.n_registros:,} registros leídos)".replace(",", "."),
            f"Potencia máxima: {fmt(d['kw'].max(), 1)} kW   ·   Energía total: {fmt(energia)} kWh",
            f"CUPS: {c.cups or 'no incluido en el fichero'}",
        ]
        if self.multipunto:
            n = len(self.lector.cups_disponibles)
            lineas.insert(0, f"ESTUDIO MULTIPUNTO: {n} CUPS detectados" + (
                " (los datos de arriba corresponden al primero)." if n else
                ". ¡El fichero no tiene columna de CUPS: no se puede hacer un estudio multipunto!"))
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
        if self.multipunto and not self.lector.cups_disponibles:
            messagebox.showerror("Sin CUPS", "Para un estudio multipunto el fichero debe incluir una columna con el "
                                 "CUPS de cada registro.", parent=self)
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
# tablas reutilizables
# --------------------------------------------------------------------------

def _corto(nombre):
    """Nombre corto de un escenario para las columnas de la tabla mensual."""
    if nombre in ("Actual", "Óptima"):
        return nombre
    return f"Prop. {nombre.split()[-1]}"


def _escala_de(widget):
    """Factor de escala de pantalla (DPI) para dimensionar columnas en píxeles."""
    return max(1.0, float(widget.tk.call("tk", "scaling")) / 1.333)


class TablaMensual(tk.Frame):
    """Coste de la potencia mes a mes de cada escenario y ahorro respecto al actual."""

    def __init__(self, padre):
        super().__init__(padre, width=600, height=330, bg="white")
        self.pack_propagate(False)
        self.arbol = ttk.Treeview(self, show="headings", height=14)
        self.arbol.pack(fill="both", expand=True)
        self.arbol.tag_configure("total", font=FUENTE_B, background="#DCE6F1")
        self.arbol.tag_configure("par", background="#F4F7FB")

    def rellenar(self, etiquetas, escenarios):
        actual, prop = escenarios[0], escenarios[1:]
        cols = ["Mes"] + [_corto(e.nombre) for e in escenarios] + \
            [("Ahorro" if e.nombre == "Óptima" else f"Ahorro P{e.nombre.split()[-1]}") for e in prop]
        filas = []
        for i, m in enumerate(etiquetas):
            filas.append([m] + [fmt(e.coste.total_mes[i]) for e in escenarios] +
                         [fmt(actual.coste.total_mes[i] - e.coste.total_mes[i]) for e in prop])
        filas.append(["Total"] + [fmt(e.coste.total) for e in escenarios] + [fmt(e.ahorro) for e in prop])
        esc = _escala_de(self)
        anchos = [int(64 * esc)] + [int(78 * esc)] * len(escenarios) + [int(80 * esc)] * len(prop)
        App._rellenar(self.arbol, cols, filas, anchos, totales=1)
        self.configure(width=sum(anchos) + 6, height=int(22 * esc) * (len(filas) + 1) + 12)


class TablaOptimizacion(tk.Frame):
    """Rejilla Actual / Propuesta 1 (óptima) / Propuestas editables, con su menú de propuestas."""

    CLAVES = ("fijo", "exceso", "total", "ahorro", "pct", "inversion", "prs")

    def __init__(self, padre, app):
        super().__init__(padre, bg="white")
        self.app = app
        self.optimo = None
        self.rejilla = tk.Frame(self, bg="white")
        self.rejilla.pack(fill="x")
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
        for j, clave in enumerate(self.CLAVES):
            lb = tk.Label(self.rejilla, text="-" if j >= 3 else "", bg="#E2EFDA", font=FUENTE, width=9,
                          anchor="e", padx=4)
            lb.grid(row=1, column=7 + j, sticky="nsew", padx=1)
            self.res_actual[clave] = lb

        barra = tk.Frame(self, bg="white")
        barra.pack(fill="x", pady=6)
        mb = tk.Menubutton(barra, text="➕  Propuestas  ▾", bg=AZUL_BOTON, fg="white", font=FUENTE_B,
                           activebackground="#125AA0", activeforeground="white", relief="raised", bd=2,
                           padx=10, pady=4, cursor="hand2")
        menu = tk.Menu(mb, tearoff=False)
        menu.add_command(label="Añadir otra propuesta", command=self.anadir)
        menu.add_command(label="Eliminar la última propuesta", command=self.eliminar)
        menu.add_separator()
        menu.add_command(label="Copiar la óptima en las propuestas editables", command=self.copiar_optima)
        mb.configure(menu=menu)
        mb.pack(side="left")

        self.propuestas = [FilaPropuesta(app, 1, editable=False), FilaPropuesta(app, 2, editable=True)]
        for k, fp in enumerate(self.propuestas):
            fp.construir(self.rejilla, 2 + 2 * k)

    def anadir(self):
        if len(self.propuestas) >= MAX_PROPUESTAS:
            messagebox.showinfo("Propuestas", f"Máximo {MAX_PROPUESTAS} propuestas.")
            return
        fp = FilaPropuesta(self.app, len(self.propuestas) + 1, editable=True)
        self.propuestas.append(fp)
        fp.construir(self.rejilla, 2 + 2 * (len(self.propuestas) - 1))
        if self.optimo is not None:
            fp.fijar(self.optimo)

    def eliminar(self):
        if len(self.propuestas) <= 2:
            messagebox.showinfo("Propuestas", "La Propuesta 1 (óptima) y la Propuesta 2 no se pueden eliminar.")
            return
        self.propuestas.pop().destruir()
        if self.app.hay_resultados():
            self.app.calcular()

    def copiar_optima(self):
        if self.optimo is None:
            messagebox.showinfo("Propuestas", "Primero pulsa CALCULAR para obtener la potencia óptima.")
            return
        for fp in self.propuestas[1:]:
            fp.fijar(self.optimo)

    def reiniciar(self):
        """Nueva curva: las propuestas editables se vuelven a precargar con la nueva óptima."""
        for fp in self.propuestas:
            fp.inv_manual = False
            fp.limpiar_resultados()
        for fp in self.propuestas[1:]:
            for v in fp.vars:
                v.set("")

    def recoger(self, optimo, actual):
        """Lista [(nombre, pc, opciones)] de las propuestas, o un mensaje de error."""
        self.optimo = optimo
        self.propuestas[0].fijar(optimo)
        for fp in self.propuestas[1:]:
            if fp.vacia():
                fp.fijar(optimo)
        res = []
        for fp in self.propuestas:
            pc = fp.potencias()
            err = validar_potencias(pc)
            if err:
                return f"{fp.nombre}: {err}"
            if not fp.inv_manual:
                fp.fijar_opciones(opciones_inversion_defecto(pc, actual))
            res.append((fp.nombre, pc, fp.opciones()))
        return res

    def mostrar(self, escenarios):
        actual = escenarios[0]
        for p, lb in enumerate(self.lb_actual):
            lb.config(text=fmt_pot(actual.pc[p]))
        self.res_actual["fijo"].config(text=fmt(actual.coste.total_fijo))
        self.res_actual["exceso"].config(text=fmt(actual.coste.total_exceso))
        self.res_actual["total"].config(text=fmt(actual.coste.total), font=FUENTE_B)
        for fp, esc in zip(self.propuestas, escenarios[1:]):
            fp.mostrar(esc)


def texto_notas(estudio, escenarios):
    inv = [f"{e.nombre}: {texto_conceptos(e.inversion['conceptos'])}" for e in escenarios[1:]
           if e.inversion.get("total")]
    d = estudio.tarifa.derechos
    return ("* Ahorro respecto al coste actual; % sobre el coste de potencia actual. Importes sin impuesto eléctrico.\n"
            f"Inversión ({d.get('nombre', '')}): acceso {fmt(d['acceso'], 6)} €/kW y extensión "
            f"{fmt(d['extension'], 6)} €/kW sobre el aumento de la potencia máxima respecto a la actual; enganche "
            f"{fmt(d['enganche'], 2)} €. Si la ampliación es > 250 kW o en suelo no urbanizable, la extensión no se "
            "incluye (la ejecuta el titular).\n" + ("Conceptos → " + " · ".join(inv) if inv else ""))


# --------------------------------------------------------------------------
# suministro
# --------------------------------------------------------------------------

class Suministro:
    """Un punto de suministro: datos, curva, estudio, propuestas y resultados."""

    def __init__(self, cups=None, zona=None, v_tarifa=None, v_actual=None):
        self.cups = cups
        self.v_denominacion = tk.StringVar()
        self.v_direccion = tk.StringVar()
        self.v_tarifa = v_tarifa or tk.StringVar(value=TARIFAS[0])
        self.v_zona = tk.StringVar(value=zona or ZONAS[0])
        self.v_actual = v_actual or [tk.StringVar() for _ in range(N_P)]
        self.curva = None
        self.zona_curva = None
        self.estudio = None
        self._clave = None
        self.optimo = None
        self.escenarios = None
        self.tabla_mes = None          # TablaMensual
        self.tabla_opt = None          # TablaOptimizacion
        self.lb_notas = None

    @property
    def nombre(self):
        return self.v_denominacion.get().strip() or self.cups or "Suministro"

    def actual(self):
        return [_num(v.get()) for v in self.v_actual]

    def invalidar(self):
        self.estudio = None
        self._clave = None
        self.escenarios = None

    def preparar(self, precios):
        clave = (id(self.curva), self.v_zona.get(), self.v_tarifa.get())
        if self.estudio is None or self._clave != clave:
            tarifa = Tarifa.desde_precios(precios, self.v_tarifa.get())
            self.estudio = Estudio(self.curva.datos, self.v_zona.get(), tarifa, precios.get("festivos"))
            self._clave = clave
            self.optimo = self.estudio.optimo()
        return self.estudio

    def calcular(self, precios):
        """Calcula los escenarios. Devuelve None o un mensaje de error."""
        if self.curva is None:
            return "Falta la curva de carga."
        actual = self.actual()
        if any(p is None or p <= 0 for p in actual):
            return "Faltan las 6 potencias contratadas actuales."
        est = self.preparar(precios)
        propuestas = self.tabla_opt.recoger(self.optimo, actual)
        if isinstance(propuestas, str):
            return propuestas
        self.escenarios = evaluar(est, propuestas, actual)
        return None

    def avisos(self):
        actual = self.actual()
        res = []
        if validar_potencias(actual):
            res.append("Las potencias actuales no cumplen la condición P1 ≤ … ≤ P6.")
        pmax = self.estudio.max_demanda()
        if pmax > 3 * max(actual) or pmax < 0.15 * max(actual):
            res.append(f"La potencia máxima de la curva ({fmt(pmax, 1)} kW) es muy distinta de la contratada "
                       f"({fmt(max(actual))} kW). Revisa la unidad de la curva (kW / kWh).")
        if self.v_tarifa.get() == "3.0TD" and max(self.optimo) <= 50:
            res.append("La potencia óptima no supera 50 kW: con 3.0TD ≤ 50 kW el punto de medida sería tipo 4 "
                       "y los excesos se facturarían por maxímetro, no por cuartos de hora.")
        return res

    def mostrar(self):
        self.tabla_opt.mostrar(self.escenarios)
        self.tabla_mes.rellenar(self.estudio.etiquetas_meses, self.escenarios)
        if self.lb_notas is not None:
            self.lb_notas.config(text=texto_notas(self.estudio, self.escenarios))


# --------------------------------------------------------------------------
# aplicación
# --------------------------------------------------------------------------

TODOS = "Todos (suma)"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("Optimización de la potencia contratada – GE&PE")
        self.precios = cargar_precios()
        self.zona = None
        self.lector = None
        self.ajustes_carga = None
        self.suministros = []
        self.resumen = None             # ResumenMultipunto
        self.anexo = None               # (estudio, escenarios) mostrado en los anexos

        self.iniciada = False
        sel = SelectorZona(self)
        self.wait_window(sel)
        if not sel.zona:
            self.destroy()
            return
        self.iniciada = True
        self.zona = sel.zona
        self.multipunto = getattr(sel, "modo", "individual") == "multipunto"

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
        if not self.multipunto:
            s = Suministro(zona=self.zona, v_tarifa=self.v_tarifa, v_actual=self.v_actual)
            s.tabla_mes, s.tabla_opt, s.lb_notas = self.tabla_mes, self.tabla_opt, self.lb_notas
            self.suministros = [s]
        self.protocol("WM_DELETE_WINDOW", self._salir)
        self.deiconify()

    def _salir(self):
        self.quit()
        self.destroy()

    # compatibilidad con el modo individual (y con las pruebas)
    @property
    def curva(self):
        return self.suministros[0].curva if self.suministros else None

    @curva.setter
    def curva(self, valor):
        s = self.suministros[0]
        s.curva, s.zona_curva = valor, s.v_zona.get()
        s.invalidar()

    @property
    def estudio(self):
        return self.anexo[0] if self.anexo else None

    @property
    def escenarios(self):
        return self.anexo[1] if self.anexo else None

    @property
    def propuestas(self):
        return self.suministros[0].tabla_opt.propuestas

    def anadir_propuesta(self):
        self.suministros[0].tabla_opt.anadir()

    def hay_resultados(self):
        return any(s.escenarios for s in self.suministros)

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
        titulo = "Optimización de la potencia contratada" + (" – Multipunto" if self.multipunto else "")
        tk.Label(cab, text=titulo, bg="white", fg=ROJO_GEYPE, font=("Arial", 16, "bold")).pack(side="left", padx=10)
        der = tk.Frame(cab, bg="white")
        der.pack(side="right", padx=12)
        if self.multipunto:
            tk.Label(der, text="Estudio multipunto: la zona y la tarifa se indican en cada CUPS", bg="white",
                     font=("Arial", 10, "bold")).pack(side="left")
        else:
            self.lb_zona = tk.Label(der, text=f"Zona: {self.zona}", bg="white", font=("Arial", 10, "bold"))
            self.lb_zona.pack(side="left")
            ttk.Button(der, text="Cambiar zona", command=self._cambiar_zona).pack(side="left", padx=8)
        tk.Frame(self, bg=ROJO_GEYPE, height=3).pack(fill="x")

    def _cambiar_zona(self):
        sel = SelectorZona(self, self.zona, mostrar_modo=False)
        self.wait_window(sel)
        if sel.zona and sel.zona != self.zona:
            self.zona = sel.zona
            self.lb_zona.config(text=f"Zona: {self.zona}")
            s = self.suministros[0]
            s.v_zona.set(self.zona)
            if self.lector is not None:        # los cambios de hora dependen de la zona (Canarias)
                self._procesar_curva(s)
            s.invalidar()

    # ------------------------------------------------------------------ panel izquierdo
    def _construir_panel_izquierdo(self, padre):
        izq = ttk.Frame(padre, padding=(10, 8))
        izq.pack(side="left", fill="y")

        datos = ttk.LabelFrame(izq, text="Datos del estudio" if self.multipunto else "Datos del suministro",
                               padding=8)
        datos.pack(fill="x")
        self.v_datos = {}
        campos = [("titular", "Titular"), ("fecha", "Fecha del estudio")] if self.multipunto else \
            [("titular", "Titular"), ("cups", "CUPS"), ("instalacion", "Instalación"),
             ("direccion", "Dirección"), ("fecha", "Fecha del estudio")]
        for i, (clave, texto) in enumerate(campos):
            ttk.Label(datos, text=texto + ":").grid(row=i, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=date.today().strftime("%d/%m/%Y") if clave == "fecha" else "")
            ttk.Entry(datos, textvariable=v, width=30).grid(row=i, column=1, sticky="we", pady=2, padx=(5, 0))
            self.v_datos[clave] = v
        self.v_tarifa = tk.StringVar(value=TARIFAS[0])
        if not self.multipunto:
            ttk.Label(datos, text="Tarifa:").grid(row=len(campos), column=0, sticky="w", pady=2)
            cb = ttk.Combobox(datos, textvariable=self.v_tarifa, values=TARIFAS, state="readonly", width=12)
            cb.grid(row=len(campos), column=1, sticky="w", pady=2, padx=(5, 0))
            cb.bind("<<ComboboxSelected>>", lambda e: self.suministros[0].invalidar())

        curva = ttk.LabelFrame(izq, text="Curva de carga", padding=8)
        curva.pack(fill="x", pady=8)
        ttk.Button(curva, text="📂  Cargar curva de carga…", command=self.cargar_curva).pack(fill="x")
        ttk.Button(curva, text="🌐  Descargar de Gemweb…", command=self.descargar_gemweb).pack(fill="x", pady=(4, 0))
        texto = ("Un único fichero con la curva de todos los CUPS (columna CUPS obligatoria)."
                 if self.multipunto else "Formatos: CSV, TXT, XLSX, XLS (cuartohoraria u horaria, kW o kWh).")
        self.lb_curva = ttk.Label(curva, text="Ninguna curva cargada.\n" + texto,
                                  wraplength=320, foreground="#555555", justify="left")
        self.lb_curva.pack(fill="x", pady=(6, 0))

        self.v_actual = [tk.StringVar() for _ in range(N_P)]
        if not self.multipunto:
            pot = ttk.LabelFrame(izq, text="Potencias contratadas actuales (kW)", padding=8)
            pot.pack(fill="x")
            for p in range(N_P):
                ttk.Label(pot, text=f"P{p + 1}", font=FUENTE_B).grid(row=0, column=p, padx=2)
                e = tk.Entry(pot, textvariable=self.v_actual[p], width=7, justify="center", relief="solid", bd=1)
                e.grid(row=1, column=p, padx=2, pady=2)
                e.bind("<Return>", lambda ev: self.calcular())

        ttk.Separator(izq).pack(fill="x", pady=12)
        boton(izq, "🚀  CALCULAR", self.calcular).pack(pady=(0, 10))
        boton(izq, "📄  EXPORTAR PDF", self.exportar_pdf, bg=ROJO_GEYPE, activo="#7A1518").pack()

        info = ("Propuesta 1 = potencias óptimas calculadas (enteras, con P1 ≤ … ≤ P6).\n"
                "Propuestas 2 y siguientes = editables; pulsa CALCULAR para recalcular.\n")
        if self.multipunto:
            info += ("Rellena en cada CUPS su denominación, tarifa, zona y potencias actuales. El resumen conjunto "
                     "compara la situación actual con la óptima de cada CUPS.\n")
        info += f"Precios regulados {self.precios.get('vigencia', '')} (config/precios.json)."
        ttk.Label(izq, wraplength=330, foreground="#666666", justify="left", font=("Arial", 8),
                  text=info).pack(side="bottom", fill="x")

    # ------------------------------------------------------------------ pestañas
    def _construir_pestanas(self, padre):
        der = ttk.Frame(padre)
        der.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        if self.multipunto:
            barra = ttk.Frame(der)
            barra.pack(fill="x", pady=(0, 4))
            ttk.Label(barra, text="CUPS mostrado en los anexos:", font=FUENTE_B).pack(side="left")
            self.v_cups_anexo = tk.StringVar(value=TODOS)
            self.combo_cups_anexo = ttk.Combobox(barra, textvariable=self.v_cups_anexo, state="readonly",
                                                 width=60, values=[TODOS])
            self.combo_cups_anexo.pack(side="left", padx=6)
            self.combo_cups_anexo.bind("<<ComboboxSelected>>", lambda e: self._mostrar_anexos())
        self.nb = ttk.Notebook(der)
        self.nb.pack(fill="both", expand=True)
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self.after(80, self._dibujar_pendientes))
        self._pendientes = set()

        # --- Resumen
        desp = MarcoDesplazable(self.nb)
        self.nb.add(desp, text="Resumen")
        res = desp.interior
        if self.multipunto:
            tk.Label(res, text="RESUMEN CONJUNTO (actual frente a la óptima de cada CUPS)", bg=ROJO_GEYPE,
                     fg="white", font=("Arial", 10, "bold"), pady=3).pack(fill="x", padx=6, pady=(6, 0))
        arriba = tk.Frame(res, bg="white")
        arriba.pack(fill="x", padx=6, pady=6)
        self.tabla_mes = TablaMensual(arriba)
        self.tabla_mes.pack(side="left", fill="y")
        self.fig_costes = Figure(figsize=(4.5, 2.6), dpi=100, layout="constrained")
        self.canvas_costes = FigureCanvasTkAgg(self.fig_costes, arriba)
        self.canvas_costes.get_tk_widget().pack(side="left", fill="both", expand=True, padx=(8, 0))

        if self.multipunto:
            tk.Label(res, text="RESUMEN POR CUPS (sin i.e.)", bg=AZUL_OSCURO, fg="white",
                     font=("Arial", 10, "bold"), pady=3).pack(fill="x", padx=6, pady=(8, 0))
            self.tabla_cups = TablaColores(res)
            self.tabla_cups.pack(fill="x", padx=6)
            self.lb_notas_multi = tk.Label(res, bg="white", fg="#444444", font=("Arial", 8), justify="left",
                                           anchor="w", wraplength=1000)
            self.lb_notas_multi.pack(fill="x", padx=8, pady=(4, 6))
            self.cont_bloques = tk.Frame(res, bg="white")
            self.cont_bloques.pack(fill="x")
            self.tabla_opt = self.lb_notas = None
        else:
            tk.Label(res, text="OPTIMIZACIÓN DE POTENCIA (sin i.e.)", bg=AZUL_OSCURO, fg="white",
                     font=("Arial", 10, "bold"), pady=3).pack(fill="x", padx=6, pady=(8, 0))
            self.tabla_opt = TablaOptimizacion(res, self)
            self.tabla_opt.pack(fill="x", padx=6)
            self.lb_notas = tk.Label(res, bg="white", fg="#444444", font=("Arial", 8), justify="left",
                                     anchor="w", wraplength=1000)
            self.lb_notas.pack(fill="x", padx=8, pady=(0, 10))

        # --- Anexos
        marco_e = ttk.Frame(self.nb)
        self.nb.add(marco_e, text="Anexo: Energía (kWh)")
        self.tabla_energia = self._tabla(marco_e, height=16)
        self.tabla_energia.pack(fill="x", padx=6, pady=6)

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
        ttk.Label(sup, text="Importes en € sin impuesto eléctrico.",
                  foreground="#666666").pack(side="left", padx=15)
        self.tabla_det = TablaColores(marco_det)
        self.tabla_det.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        marco_sel = ttk.Frame(self.nb)
        self.nb.add(marco_sel, text="Anexo: Curva de carga")
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
                       "cuarto de hora (elige un mes para verlo con claridad). El PDF incluye esta misma "
                       "selección.").pack(side="left", padx=15)
        self.fig_curva = Figure(figsize=(5, 3), dpi=100, layout="constrained")
        self.canvas_curva = FigureCanvasTkAgg(self.fig_curva, marco_sel)
        self.canvas_curva.get_tk_widget().pack(fill="both", expand=True)

        marco_log = ttk.Frame(self.nb)
        self.nb.add(marco_log, text="Registro de carga")
        self.txt_log = tk.Text(marco_log, wrap="word", font=FUENTE)
        self.txt_log.pack(fill="both", expand=True, padx=6, pady=6)

    # ------------------------------------------------------------------ bloques por CUPS (multipunto)
    def _construir_bloques(self):
        for w in self.cont_bloques.winfo_children():
            w.destroy()
        for k, s in enumerate(self.suministros, 1):
            marco = tk.Frame(self.cont_bloques, bg="white", highlightbackground=AZUL_OSCURO, highlightthickness=1)
            marco.pack(fill="x", padx=6, pady=(10, 4))
            tk.Label(marco, text=f"{k}.  CUPS {s.cups}", bg=AZUL_OSCURO, fg="white", font=("Arial", 10, "bold"),
                     anchor="w", padx=8, pady=3).pack(fill="x")
            datos = tk.Frame(marco, bg="white")
            datos.pack(fill="x", padx=6, pady=6)
            tk.Label(datos, text="Denominación:", bg="white", font=FUENTE).grid(row=0, column=0, sticky="w")
            ttk.Entry(datos, textvariable=s.v_denominacion, width=32).grid(row=0, column=1, sticky="w", padx=4)
            tk.Label(datos, text="Dirección:", bg="white", font=FUENTE).grid(row=0, column=2, sticky="w", padx=(10, 0))
            ttk.Entry(datos, textvariable=s.v_direccion, width=48).grid(row=0, column=3, columnspan=5, sticky="w",
                                                                        padx=4)
            tk.Label(datos, text="Tarifa:", bg="white", font=FUENTE).grid(row=1, column=0, sticky="w", pady=(4, 0))
            cb = ttk.Combobox(datos, textvariable=s.v_tarifa, values=TARIFAS, state="readonly", width=10)
            cb.grid(row=1, column=1, sticky="w", padx=4, pady=(4, 0))
            cb.bind("<<ComboboxSelected>>", lambda e, s=s: s.invalidar())
            tk.Label(datos, text="Zona:", bg="white", font=FUENTE).grid(row=1, column=2, sticky="w", padx=(10, 0),
                                                                       pady=(4, 0))
            cb = ttk.Combobox(datos, textvariable=s.v_zona, values=ZONAS, state="readonly", width=14)
            cb.grid(row=1, column=3, sticky="w", padx=4, pady=(4, 0))
            cb.bind("<<ComboboxSelected>>", lambda e, s=s: s.invalidar())
            pot = tk.Frame(datos, bg="white")
            pot.grid(row=1, column=4, columnspan=4, sticky="w", padx=(14, 0), pady=(4, 0))
            tk.Label(pot, text="Potencias actuales (kW):", bg="white", font=FUENTE_B).pack(side="left", padx=(0, 6))
            for p in range(N_P):
                tk.Label(pot, text=f"P{p + 1}", bg="white", font=FUENTE_B).pack(side="left")
                e = tk.Entry(pot, textvariable=s.v_actual[p], width=6, justify="center", relief="solid", bd=1)
                e.pack(side="left", padx=(2, 8))
                e.bind("<Return>", lambda ev: self.calcular())
            c = s.curva
            tk.Label(marco, bg="white", fg="#555555", font=("Arial", 8), anchor="w",
                     text=f"Curva: {c.fecha_inicio:%d/%m/%Y} – {(c.fecha_fin - np.timedelta64(1, 'D')):%d/%m/%Y}"
                          f"  ·  {'cuartohoraria' if c.resolucion_min == 15 else 'HORARIA'}  ·  potencia máxima "
                          f"{fmt(c.datos['kw'].max(), 1)} kW" + (f"  ·  ⚠ {len(c.avisos)} aviso(s)" if c.avisos else "")
                     ).pack(fill="x", padx=8)
            cuerpo = tk.Frame(marco, bg="white")
            cuerpo.pack(fill="x", padx=6, pady=6)
            s.tabla_mes = TablaMensual(cuerpo)
            s.tabla_mes.pack(anchor="w")
            s.tabla_opt = TablaOptimizacion(marco, self)
            s.tabla_opt.pack(fill="x", padx=6)
            s.lb_notas = tk.Label(marco, bg="white", fg="#444444", font=("Arial", 8), justify="left", anchor="w",
                                  wraplength=1000)
            s.lb_notas.pack(fill="x", padx=8, pady=(0, 8))

    # ------------------------------------------------------------------ gráficos
    def _dibujar_pendientes(self):
        """Dibuja los gráficos de la pestaña visible (una figura oculta se dimensiona mal)."""
        pestana = self.nb.index("current")
        graficos = {0: ("costes", self.fig_costes, self.canvas_costes, self._dibujar_costes),
                    2: ("max", self.fig_max, self.canvas_max, self._dibujar_maximos),
                    4: ("curva", self.fig_curva, self.canvas_curva, self._dibujar_selector)}
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

    def _dibujar_costes(self):
        if self.multipunto:
            if self.resumen:
                dibujar_costes(self.fig_costes, self.resumen, self.resumen.escenarios,
                               titulo="Coste de la potencia facturada – conjunto (€)")
        elif self.suministros[0].escenarios:
            s = self.suministros[0]
            dibujar_costes(self.fig_costes, s.estudio, s.escenarios)

    def _aviso_grafico(self, fig, texto):
        fig.clear()
        ax = fig.add_subplot(111)
        ax.axis("off")
        ax.text(0.5, 0.5, texto, ha="center", va="center", fontsize=11, color="#555555")

    def _dibujar_maximos(self):
        if self.anexo is None:
            self._aviso_grafico(self.fig_max, "Selecciona un CUPS concreto para ver su gráfico.")
        else:
            dibujar_maximos(self.fig_max, self.anexo[0], self.anexo[1][0].pc)

    def _seleccion_curva(self, etiqueta=False):
        """(periodo, mes) del selector: periodo 0 = todos; mes None = año completo (índice o etiqueta)."""
        per = self.v_sel_periodo.get()
        periodo = 0 if per == "Todos" else int(per[1])
        mes = self.v_sel_mes.get() if self.v_sel_mes.get() != "Año completo" else None
        if etiqueta or mes is None or self.anexo is None:
            return periodo, mes
        meses = self.anexo[0].etiquetas_meses
        return periodo, (meses.index(mes) if mes in meses else None)

    def _dibujar_selector(self):
        if self.anexo is None:
            self._aviso_grafico(self.fig_curva, "Selecciona un CUPS concreto para ver su curva de carga.")
        else:
            dibujar_curva_selector(self.fig_curva, self.anexo[0], self.anexo[1], *self._seleccion_curva())

    def _redibujar_selector(self):
        self._pendientes.add("curva")
        self._dibujar_pendientes()

    # ------------------------------------------------------------------ tablas
    def _tabla(self, padre, height=14):
        t = ttk.Treeview(padre, show="headings", height=height)
        t.tag_configure("total", font=FUENTE_B, background="#DCE6F1")
        t.tag_configure("par", background="#F4F7FB")
        return t

    def _escala(self):
        return _escala_de(self)

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
        dlg = DialogoCarga(self, lector, self.zona, multipunto=self.multipunto)
        self.wait_window(dlg)
        if dlg.resultado is None:
            return
        self.lector, self.ajustes_carga = lector, dlg.ajustes
        if self.multipunto:
            self._cargar_multipunto(ruta)
        else:
            self._cargar_individual(ruta, dlg.resultado)

    def _procesar_curva(self, s):
        a = self.ajustes_carga or {}
        s.curva = self.lector.procesar(s.v_zona.get(), a.get("unidad", UNIDADES[0]),
                                       a.get("convenio", CONVENIOS[0]), a.get("hoja"),
                                       s.cups if self.multipunto else a.get("cups"))
        s.zona_curva = s.v_zona.get()
        s.invalidar()

    def _cargar_individual(self, ruta, curva, nombre=None):
        s = self.suministros[0]
        s.curva, s.zona_curva = curva, s.v_zona.get()
        s.invalidar()
        if curva.cups and not self.v_datos["cups"].get().strip():
            self.v_datos["cups"].set(curva.cups)
        tipo = "cuartohoraria" if curva.resolucion_min == 15 else "HORARIA (cuartos estimados)"
        if self.AVISO_HORARIA in curva.avisos:
            tipo = "lectura HORARIA en Gemweb (cuartos estimados)"
        texto = (f"{nombre or Path(ruta).name}\n{curva.fecha_inicio:%d/%m/%Y} – "
                 f"{(curva.fecha_fin - np.timedelta64(1, 'D')):%d/%m/%Y}  ·  {tipo}  ·  {curva.unidad}\n"
                 f"Potencia máxima: {fmt(curva.datos['kw'].max(), 1)} kW")
        if curva.avisos:
            texto += f"\n⚠ {len(curva.avisos)} aviso(s): ver pestaña «Registro de carga»"
        self.lb_curva.config(text=texto, foreground="black")
        self._escribir_log()
        s.tabla_opt.reiniciar()
        if all(_num(v.get()) for v in self.v_actual):
            self.calcular()

    def _cargar_multipunto(self, ruta, nombre=None):
        cups = list(self.lector.cups_disponibles)
        self.config(cursor="watch")
        self.update_idletasks()
        errores = []
        nuevos = []
        try:
            for c in cups:
                s = Suministro(cups=c, zona=self.zona)
                try:
                    self._procesar_curva(s)
                    nuevos.append(s)
                except Exception as e:
                    errores.append(f"{c}: {e}")
        finally:
            self.config(cursor="")
        if not nuevos:
            messagebox.showerror("Error", "No se ha podido interpretar la curva de ningún CUPS.\n\n" + "\n".join(errores))
            return
        self.suministros = nuevos
        self.resumen = None
        self.anexo = None
        self._construir_bloques()
        self.combo_cups_anexo.configure(values=[TODOS] + [s.cups for s in nuevos])
        self.v_cups_anexo.set(TODOS)
        self.lb_curva.config(foreground="black", text=f"{nombre or Path(ruta).name}\n{len(nuevos)} CUPS cargados"
                             + (f" ({len(errores)} con error)" if errores else "") +
                             ".\nRellena los datos de cada CUPS y pulsa CALCULAR.")
        self._escribir_log(errores)
        if errores:
            messagebox.showwarning("CUPS con error", "\n".join(errores))

    # ------------------------------------------------------------------ Gemweb
    AVISO_HORARIA = ("En Gemweb este suministro tiene lectura HORARIA: cada cuarto de hora es un reparto de la "
                     "energía de su hora, así que los picos de 15 minutos no son reales y los excesos pueden ser mayores.")

    def descargar_gemweb(self):
        from . import gemweb
        from .gui_gemweb import DialogoCredenciales, DialogoGemweb
        credenciales = gemweb.cargar_credenciales()
        if credenciales is None:
            dlg = DialogoCredenciales(self)
            self.wait_window(dlg)
            if not dlg.ok:
                return
            credenciales = gemweb.cargar_credenciales()
        inicial = "\n".join(s.cups for s in self.suministros if s.cups) if self.multipunto \
            else self.v_datos["cups"].get().strip()
        dlg = DialogoGemweb(self, credenciales, self.multipunto, inicial)
        self.wait_window(dlg)
        if dlg.resultado:
            self.aplicar_descarga_gemweb(dlg.resultado)

    def aplicar_descarga_gemweb(self, resultado):
        """Carga en el estudio la curva descargada de Gemweb (y, si se pidió, los datos del contrato)."""
        from . import gemweb
        ruta, info, avisos, rellenar = resultado
        try:
            self.lector = LectorCurva(ruta)
        except Exception as e:
            messagebox.showerror("Error al leer la curva descargada", str(e))
            return
        self.ajustes_carga = {"unidad": UNIDADES[0], "convenio": "Fin de periodo", "hoja": None, "cups": None}
        nombre = f"Gemweb · descargada el {datetime.now():%d/%m/%Y %H:%M}"

        def avisos_de(cups, curva):
            curva.avisos += [a for a in avisos if a.startswith(cups)]
            if info[cups].get("_lectura_horaria"):
                curva.avisos.append(self.AVISO_HORARIA)

        if not self.multipunto:
            cups, datos = next(iter(info.items()))
            try:
                curva = self.lector.procesar(self.zona, UNIDADES[0], "Fin de periodo", None, cups)
            except Exception as e:
                messagebox.showerror("Error al interpretar la curva", str(e))
                return
            avisos_de(cups, curva)
            self.v_datos["cups"].set(cups)
            if rellenar:
                self._rellenar_desde_gemweb(datos, self.v_tarifa, self.v_actual)
                self.v_datos["instalacion"].set(datos.get("nom") or "")
                self.v_datos["direccion"].set(self._direccion_gemweb(datos))
            self._cargar_individual(ruta, curva, nombre=nombre)
            zona = gemweb.zona_por_codigo_postal(datos.get("codi_postal"))
            if zona and zona != self.zona:
                messagebox.showinfo("Zona", f"Según su código postal, el suministro está en {zona} y el estudio "
                                    f"está en {self.zona}. Si es así, pulsa «Cambiar zona».")
            return

        try:
            self.lector.procesar(self.zona, UNIDADES[0], "Fin de periodo")    # detecta los CUPS del fichero
        except Exception as e:
            messagebox.showerror("Error al interpretar la curva", str(e))
            return
        self._cargar_multipunto(ruta, nombre=nombre)
        for s in self.suministros:
            datos = info.get(s.cups)
            if datos is None:
                continue
            avisos_de(s.cups, s.curva)
            if rellenar:
                self._rellenar_desde_gemweb(datos, s.v_tarifa, s.v_actual)
                s.v_denominacion.set(datos.get("nom") or "")
                s.v_direccion.set(self._direccion_gemweb(datos))
                zona = gemweb.zona_por_codigo_postal(datos.get("codi_postal"))
                if zona:
                    s.v_zona.set(zona)      # al calcular se vuelve a leer la curva con esa zona
        self._escribir_log()
        if rellenar and all(all(_num(v.get()) for v in s.v_actual) for s in self.suministros):
            self.calcular()

    @staticmethod
    def _direccion_gemweb(datos):
        partes = [datos.get("direccio"), " ".join(x for x in (datos.get("codi_postal"), datos.get("poblacio")) if x)]
        return ", ".join(x.strip() for x in partes if x and x.strip())

    @staticmethod
    def _rellenar_desde_gemweb(datos, v_tarifa, v_actual):
        from .gemweb import numero
        tarifa = (datos.get("tarifa_acces") or "").strip()
        if tarifa in TARIFAS:
            v_tarifa.set(tarifa)
        potencias = [numero(datos.get(f"pot_contract_p{k}")) for k in range(1, 7)]
        if all(p and p > 0 for p in potencias):
            for v, pot in zip(v_actual, potencias):
                v.set(f"{pot:g}".replace(".", ","))

    def _escribir_log(self, errores=()):
        self.txt_log.delete("1.0", "end")
        lineas = []
        for s in self.suministros:
            c = s.curva
            if c is None:
                continue
            if self.multipunto:
                lineas.append(f"══ CUPS {s.cups} ══")
            lineas += [f"Fichero: {c.archivo}", f"Hoja: {c.hoja}" if c.hoja else None,
                       f"Resolución original: {c.resolucion_min} min · Hora del registro: {c.convenio}",
                       f"Unidad: {c.descripcion_unidad}",
                       f"Registros leídos: {c.n_registros:,}".replace(",", "."),
                       f"Periodo del estudio: {c.fecha_inicio:%d/%m/%Y %H:%M} – {c.fecha_fin:%d/%m/%Y %H:%M}",
                       f"Intervalos rellenados (huecos): {c.huecos_rellenados}",
                       "Cambios de hora: " + ("; ".join(c.dias_cambio_hora) or "ninguno"), "Avisos:"]
            lineas += [f"  • {a}" for a in c.avisos] or ["  (ninguno)"]
            lineas.append("")
        if errores:
            lineas += ["CUPS no interpretados:"] + [f"  • {e}" for e in errores]
        self.txt_log.insert("end", "\n".join(l for l in lineas if l is not None))

    # ------------------------------------------------------------------ cálculo
    def calcular(self):
        if not self.suministros or all(s.curva is None for s in self.suministros):
            messagebox.showwarning("Falta la curva", "Carga primero la curva de carga.")
            return
        self.config(cursor="watch")
        self.update_idletasks()
        errores = []
        try:
            for s in self.suministros:
                if self.multipunto and s.zona_curva != s.v_zona.get():
                    self._procesar_curva(s)          # los cambios de hora dependen de la zona
                err = s.calcular(self.precios)
                if err:
                    errores.append(f"{s.nombre}: {err}" if self.multipunto else err)
        finally:
            self.config(cursor="")
        if errores:
            titulo = "Faltan datos o hay propuestas no válidas"
            messagebox.showwarning(titulo, "\n\n".join(errores[:12]) + ("\n…" if len(errores) > 12 else ""))
            return
        if self.multipunto:
            self.resumen = ResumenMultipunto([(s.estudio, s.escenarios) for s in self.suministros])
        self._mostrar_resultados()
        avisos = []
        for s in self.suministros:
            avisos += [f"{s.nombre}: {a}" if self.multipunto else a for a in s.avisos()]
        if self.multipunto and self.resumen.periodos_distintos:
            avisos.append("Las curvas de los CUPS no cubren los mismos meses: el resumen mensual suma los meses "
                          "disponibles de cada uno.")
        if avisos:
            messagebox.showwarning("Revisa", "\n\n".join(avisos[:12]) + ("\n…" if len(avisos) > 12 else ""))

    def _filas_cups(self):
        filas = []
        for s in self.suministros:
            act, opt = s.escenarios[0], s.escenarios[1]
            filas.append({"cups": s.cups, "denominacion": s.v_denominacion.get().strip(), "tarifa": s.v_tarifa.get(),
                          "zona": s.v_zona.get(), "actual": act.coste.total, "optima": opt.coste.total,
                          "ahorro": opt.ahorro, "pct": opt.ahorro_pct, "inversion": opt.inversion.get("total", 0),
                          "prs": opt.prs})
        return filas

    def _mostrar_resultados(self):
        for s in self.suministros:
            s.mostrar()
        if self.multipunto:
            r = self.resumen
            self.tabla_mes.rellenar(r.etiquetas_meses, r.escenarios)
            cols = ["Nº", "CUPS", "Denominación", "Tarifa", "Zona", "Coste actual", "Coste óptimo", "Ahorro", "%",
                    "Inversión", "PRS (años)"]
            filas = []
            for k, f in enumerate(self._filas_cups(), 1):
                filas.append([k, f["cups"], f["denominacion"] or "-", f["tarifa"], f["zona"], fmt(f["actual"]),
                              fmt(f["optima"]), fmt(f["ahorro"]), f"{fmt(100 * f['pct'], 1)} %",
                              fmt(f["inversion"], 2) if f["inversion"] else "-",
                              fmt(f["prs"], 2) if f["prs"] is not None else "-"])
            act, opt = r.escenarios[:2]
            filas.append(["", "TOTAL", "", "", "", fmt(act.coste.total), fmt(opt.coste.total), fmt(opt.ahorro),
                          f"{fmt(100 * opt.ahorro_pct, 1)} %",
                          fmt(opt.inversion["total"], 2) if opt.inversion["total"] else "-",
                          fmt(opt.prs, 2) if opt.prs is not None else "-"])
            colores = {5: ("#E2EFDA", "#C6E0B4"), 6: ("#FCE4D6", "#F8CBAD"), 7: ("#E3EEF9", "#BFD7EE")}
            self.tabla_cups.rellenar(cols, filas, [4, 24, 28, 7, 12, 12, 12, 11, 8, 11, 10], colores, izquierda={2})
            self.lb_notas_multi.config(text="Coste de la potencia sin impuesto eléctrico. Ahorro y % respecto al coste "
                                            "actual; inversión y PRS de la propuesta óptima (Propuesta 1) de cada CUPS.")
            self.combo_cups_anexo.configure(values=[TODOS] + [s.cups for s in self.suministros])
            if self.v_cups_anexo.get() not in [TODOS] + [s.cups for s in self.suministros]:
                self.v_cups_anexo.set(TODOS)
        self._pendientes.add("costes")
        self._mostrar_anexos()

    # ------------------------------------------------------------------ anexos
    def _anexo_actual(self):
        """(estudio, escenarios) del anexo; None = suma de todos los CUPS."""
        if not self.multipunto:
            s = self.suministros[0]
            return (s.estudio, s.escenarios) if s.escenarios else None
        cups = self.v_cups_anexo.get()
        s = next((x for x in self.suministros if x.cups == cups), None)
        return (s.estudio, s.escenarios) if s and s.escenarios else None

    def _mostrar_anexos(self):
        if not self.hay_resultados():
            return
        self.anexo = self._anexo_actual()
        if self.anexo is None and not self.multipunto:
            return
        est, escs = self.anexo if self.anexo else (self.resumen, self.resumen.escenarios)
        esc = self._escala()

        e_kwh = est.energia_kwh()
        cols = ["Mes"] + [f"P{i}" for i in range(1, 7)] + ["Total"]
        filas = [[m] + [fmt(v) for v in e_kwh[i]] + [fmt(e_kwh[i].sum())] for i, m in enumerate(est.etiquetas_meses)]
        tot = e_kwh.sum(0)
        filas.append(["Total"] + [fmt(v) for v in tot] + [fmt(tot.sum())])
        filas.append(["%"] + [f"{fmt(100 * v / tot.sum(), 1)} %" if tot.sum() else "-" for v in tot] + [""])
        self._rellenar(self.tabla_energia, cols, filas, [int(x * esc) for x in [70] + [100] * 7], totales=2)

        if self.anexo is not None:
            maximos = est.maximos()
            cols = ["Mes"] + [f"P{i}" for i in range(1, 7)] + ["Máximo"]
            filas = [[m] + [fmt(v) for v in maximos[i]] + [fmt(maximos[i].max())]
                     for i, m in enumerate(est.etiquetas_meses)]
            filas.append(["Máximo"] + [fmt(v) for v in maximos.max(0)] + [fmt(maximos.max())])
            self._rellenar(self.tabla_max, cols, filas, [int(x * esc) for x in [70] + [95] * 7], totales=1)
        else:
            # suma de todos: potencia máxima anual de cada CUPS por periodo
            cols = ["CUPS"] + [f"P{i}" for i in range(1, 7)] + ["Máximo"]
            filas = []
            for s in self.suministros:
                m = s.estudio.maximos().max(0)
                filas.append([s.cups] + [fmt(v) for v in m] + [fmt(m.max())])
            self._rellenar(self.tabla_max, cols, filas, [int(x * esc) for x in [190] + [85] * 7])

        self.combo_det.configure(values=[e.nombre for e in escs])
        if self.v_det.get() not in [e.nombre for e in escs]:
            self.v_det.set(escs[0].nombre)
        self._mostrar_detalle()

        meses = ["Año completo"] + (est.etiquetas_meses if self.anexo else [])
        self.combo_sel_mes.configure(values=meses)
        if self.v_sel_mes.get() not in meses:
            self.v_sel_mes.set("Año completo")
        self._pendientes |= {"max", "curva"}
        self._dibujar_pendientes()

    def _mostrar_detalle(self):
        if not self.hay_resultados():
            return
        est, escs = self.anexo if self.anexo else (self.resumen, self.resumen.escenarios)
        esc = next((e for e in escs if e.nombre == self.v_det.get()), escs[0])
        c = esc.coste
        cols = (["Mes", "Días"] + [f"Fijo P{i}" for i in range(1, 7)] + ["Total fijo"] +
                [f"Exceso P{i}" for i in range(1, 7)] + ["Total excesos", "TOTAL"])
        filas = []
        for i, m in enumerate(est.etiquetas_meses):
            filas.append([m, est.dias_mes[i]] + [fmt(v, 2) for v in c.fijo[i]] + [fmt(c.fijo[i].sum(), 2)] +
                         [fmt(v, 2) for v in c.exceso[i]] + [fmt(c.exceso[i].sum(), 2), fmt(c.total_mes[i], 2)])
        filas.append(["Total", est.dias_totales] + [fmt(v, 2) for v in c.fijo.sum(0)] + [fmt(c.total_fijo, 2)] +
                     [fmt(v, 2) for v in c.exceso.sum(0)] + [fmt(c.total_exceso, 2), fmt(c.total, 2)])
        anchos = [7, 4] + [8] * 6 + [10] + [9] * 6 + [12, 10]     # en caracteres
        # columnas de totales con colores suaves distintos: total fijo, total excesos y TOTAL
        colores = {8: ("#FFF7DC", "#FBE7A8"), 15: ("#FDE9E7", "#F6C9C4"), 16: ("#E3EEF9", "#BFD7EE")}
        self.tabla_det.rellenar(cols, filas, anchos, colores)

    # ------------------------------------------------------------------ PDF
    def exportar_pdf(self):
        if not self.hay_resultados() or any(s.escenarios is None for s in self.suministros):
            messagebox.showwarning("Sin resultados", "Pulsa CALCULAR antes de exportar el informe.")
            return
        from .informe_pdf import generar_pdf, generar_pdf_multipunto
        d = {k: v.get().strip() for k, v in self.v_datos.items()}
        if self.multipunto:
            nombre = f"Estudio potencia multipunto {d.get('titular') or ''}".strip()
        else:
            d["tarifa"] = self.v_tarifa.get()
            d["zona"] = self.zona
            nombre = f"Estudio potencia {d.get('titular') or ''} ({d.get('instalacion') or ''})".strip()
        nombre = "".join(ch for ch in nombre if ch not in '\\/:*?"<>|') + ".pdf"
        ruta = filedialog.asksaveasfilename(title="Guardar informe PDF", defaultextension=".pdf",
                                            initialfile=nombre, filetypes=[("PDF", "*.pdf")])
        if not ruta:
            return
        anexos = messagebox.askyesno("Anexos", "¿Incluir los anexos (energía, potencias máximas, coste mensual y "
                                               "curva de carga)" + (" de cada CUPS" if self.multipunto else "") + "?")
        self.config(cursor="watch")
        self.update_idletasks()
        normativa = self.precios.get("normativa", [])
        try:
            if self.multipunto:
                suministros = [{"datos": {"titular": d.get("titular", ""), "fecha": d.get("fecha", ""),
                                          "cups": s.cups, "tarifa": s.v_tarifa.get(),
                                          "instalacion": s.v_denominacion.get().strip(),
                                          "direccion": s.v_direccion.get().strip(), "zona": s.v_zona.get()},
                                "estudio": s.estudio, "escenarios": s.escenarios, "curva": s.curva}
                               for s in self.suministros]
                generar_pdf_multipunto(ruta, d, suministros, self.resumen, self._filas_cups(), normativa,
                                       incluir_anexos=anexos, seleccion_curva=self._seleccion_curva(etiqueta=True))
            else:
                s = self.suministros[0]
                generar_pdf(ruta, d, s.estudio, s.escenarios, s.curva, normativa, incluir_anexos=anexos,
                            seleccion_curva=self._seleccion_curva(etiqueta=True))
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

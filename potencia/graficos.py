"""Gráficos compartidos por la interfaz y el informe PDF (matplotlib sin pyplot)."""

import numpy as np
from matplotlib.ticker import FuncFormatter

import matplotlib.dates as mdates

from .calculo import MESES_ABR, fmt

AZUL_OSCURO = "#1F3864"
ROJO_GEYPE = "#9B1C1F"
AZUL_BOTON = "#1976D2"
# Actual, Propuesta 1, Propuesta 2, ...
COLORES = ["#00A651", "#E26B0A", "#00B0F0", "#7030A0", "#BF8F00", "#C00000", "#5B9BD5"]
COLORES_SUAVES = ["#E2EFDA", "#FCE4D6", "#DDEBF7", "#E4DFEC", "#FFF2CC", "#F8CBAD", "#D9E1F2"]


def color(i):
    return COLORES[i % len(COLORES)]


def dibujar_costes(fig, estudio, escenarios, titulo="Coste de la potencia facturada (€)"):
    fig.clear()
    ax = fig.add_subplot(111)
    x = np.arange(len(estudio.meses))
    for i, esc in enumerate(escenarios):
        ax.plot(x, esc.coste.total_mes, color=color(i), lw=2, label=esc.nombre)
    ax.set_xticks(x)
    ax.set_xticklabels(estudio.etiquetas_meses, fontsize=7, rotation=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{fmt(v)} €"))
    ax.tick_params(axis="y", labelsize=7)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#D9D9D9", lw=0.6)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.set_title(titulo, fontsize=10, fontweight="bold", color="#222222")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=min(len(escenarios), 4),
              fontsize=7, frameon=False)


def dibujar_curva(fig, estudio, escenarios, titulo="Curva de carga y potencias contratadas"):
    """Curva cuartohoraria completa con la potencia contratada aplicable en cada cuarto."""
    fig.clear()
    ax = fig.add_subplot(111)
    t = estudio.curva["inicio"].to_numpy()
    ax.plot(t, estudio.kw, color="#A6A6A6", lw=0.4, label="Potencia demandada")
    for i, esc in enumerate(escenarios):
        ax.plot(t, esc.pc[estudio.periodo - 1], color=color(i), lw=0.9, drawstyle="steps-post",
                label=f"{esc.nombre} (potencia contratada)")
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{MESES_ABR[mdates.num2date(v).month - 1]}-{mdates.num2date(v).year % 100:02d}"))
    ax.set_ylabel("kW", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#D9D9D9", lw=0.6)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.set_title(titulo, fontsize=10, fontweight="bold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=min(len(escenarios) + 1, 4),
              fontsize=7, frameon=False)


def dibujar_maximos(fig, estudio, pc_actual=None):
    """Potencia máxima registrada por mes y periodo."""
    fig.clear()
    ax = fig.add_subplot(111)
    maximos = estudio.maximos()
    x = np.arange(len(estudio.meses))
    ancho = 0.13
    colores_p = ["#C00000", "#E26B0A", "#FFC000", "#70AD47", "#5B9BD5", "#7F7F7F"]
    for p in range(6):
        ax.bar(x + (p - 2.5) * ancho, maximos[:, p], ancho, color=colores_p[p], label=f"P{p + 1}")
    if pc_actual is not None:
        for p in range(6):
            ax.axhline(pc_actual[p], color=colores_p[p], lw=0.8, ls="--")
    ax.set_xticks(x)
    ax.set_xticklabels(estudio.etiquetas_meses, fontsize=7)
    ax.set_ylabel("kW", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", color="#D9D9D9", lw=0.6)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    ax.set_title("Potencia máxima demandada por mes y periodo (líneas: potencia actual)", fontsize=10,
                 fontweight="bold")
    ax.legend(ncol=6, fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08))

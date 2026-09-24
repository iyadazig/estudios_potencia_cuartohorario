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


ESTILOS_LINEA = ["-", (0, (6, 3)), (0, (2, 2)), (0, (6, 2, 2, 2)), (0, (10, 3)), (0, (1, 1)), (0, (4, 4))]
COLOR_DEMANDA = "#9E9E9E"
COLOR_EXCESO = "#C00000"
# fondo suave de cada periodo (P1 más oscuro -> P6 más claro)
FONDO_PERIODO = ["#F4CCCC", "#FCE5CD", "#FFF2CC", "#D9EAD3", "#CFE2F3", "#EEEEEE"]


def _formato_meses(ax, fontsize=7):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{MESES_ABR[mdates.num2date(v).month - 1]}-{mdates.num2date(v).year % 100:02d}"))
    ax.tick_params(axis="x", labelsize=fontsize)


def _ejes_limpios(ax):
    ax.grid(axis="y", color="#E0E0E0", lw=0.6)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)


def _leyenda_escenarios(escenarios, con_exceso=True, demanda_linea=False):
    from matplotlib.lines import Line2D
    if demanda_linea:
        h = [Line2D([], [], color="#707070", lw=1, label="Potencia demandada")]
    else:
        h = [Line2D([], [], color=COLOR_DEMANDA, marker="o", ls="", ms=4, label="Potencia demandada (cuarto de hora)")]
    if con_exceso:
        h.append(Line2D([], [], color=COLOR_EXCESO, marker="o", ls="", ms=4,
                        label="Cuartos de hora que superan la potencia actual"))
    h += [Line2D([], [], color=color(i), lw=1.8, ls=ESTILOS_LINEA[i % len(ESTILOS_LINEA)],
                 label=f"Potencia contratada – {e.nombre}") for i, e in enumerate(escenarios)]
    return h


def dibujar_curva_paneles(fig, estudio, escenarios, titulo="Potencia demandada frente a potencias contratadas, por periodo"):
    """Un panel por periodo: cuartos de hora de ese periodo y la potencia de cada escenario."""
    fig.clear()
    axs = fig.subplots(2, 3, sharex=True)
    t = estudio.curva["inicio"].to_numpy()
    actual = escenarios[0].pc
    for p, ax in enumerate(axs.flat):
        m = estudio.periodo == p + 1
        tp, kp = t[m], estudio.kw[m]
        exceso = kp > actual[p]
        ax.scatter(tp[~exceso], kp[~exceso], s=1.2, color=COLOR_DEMANDA, lw=0, rasterized=True)
        ax.scatter(tp[exceso], kp[exceso], s=2.5, color=COLOR_EXCESO, lw=0, rasterized=True)
        tope = max([kp.max() if len(kp) else 0] + [e.pc[p] for e in escenarios])
        for i, esc in enumerate(escenarios):
            ax.axhline(esc.pc[p], color=color(i), lw=1.6, ls=ESTILOS_LINEA[i % len(ESTILOS_LINEA)])
            ax.text(1.01, esc.pc[p], fmt(esc.pc[p]), transform=ax.get_yaxis_transform(), color=color(i),
                    fontsize=6.5, va="center", fontweight="bold")
        ax.set_ylim(0, tope * 1.1 if tope else 1)
        n_exc = int(exceso.sum())
        maximo = fmt(kp.max()) if len(kp) else "-"
        ax.set_title(f"P{p + 1}  ·  máx. {maximo} kW", fontsize=8.5, fontweight="bold", loc="left")
        ax.set_title(f"{fmt(n_exc)} cuartos con exceso (actual)", fontsize=7, loc="right",
                     color=COLOR_EXCESO if n_exc else "#555555")
        ax.tick_params(axis="y", labelsize=7)
        _formato_meses(ax, 6)
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        _ejes_limpios(ax)
        if p % 3 == 0:
            ax.set_ylabel("kW", fontsize=8)
    fig.suptitle(titulo, fontsize=10, fontweight="bold")
    fig.legend(handles=_leyenda_escenarios(escenarios), loc="outside lower center",
               ncol=min(len(escenarios) + 2, 4), fontsize=7, frameon=False)


def dibujar_curva_selector(fig, estudio, escenarios, periodo=0, mes=None,
                           titulo="Curva de carga y potencias contratadas"):
    """
    Curva filtrada por periodo (0 = todos) y mes (índice de estudio.meses o None = año completo).
    Con todos los periodos, la potencia contratada es la del periodo de cada cuarto de hora.
    """
    fig.clear()
    ax = fig.add_subplot(111)
    sel = np.ones(len(estudio.kw), bool) if mes is None else (estudio.idx_mes == mes)
    t = estudio.curva["inicio"].to_numpy()[sel]
    kw = estudio.kw[sel]
    per = estudio.periodo[sel]
    actual = escenarios[0].pc

    if periodo:
        y = np.where(per == periodo, kw, np.nan)
        lim = actual[periodo - 1]
        ax.plot(t, y, color=COLOR_DEMANDA, lw=0.7)
        ax.fill_between(t, lim, y, where=y > lim, color=COLOR_EXCESO, alpha=0.6, lw=0, interpolate=True)
        for i, esc in enumerate(escenarios):
            ax.axhline(esc.pc[periodo - 1], color=color(i), lw=1.6, ls=ESTILOS_LINEA[i % len(ESTILOS_LINEA)])
            ax.text(1.005, esc.pc[periodo - 1], fmt(esc.pc[periodo - 1]), transform=ax.get_yaxis_transform(),
                    color=color(i), fontsize=7, va="center", fontweight="bold")
        tope = max([np.nanmax(y) if np.isfinite(y).any() else 0] + [e.pc[periodo - 1] for e in escenarios])
    else:
        if mes is not None:
            # fondo coloreado según el periodo de cada tramo
            cambios = np.flatnonzero(np.diff(per)) + 1
            ini = np.concatenate([[0], cambios])
            fin = np.concatenate([cambios, [len(per)]])
            paso = np.timedelta64(15, "m")
            for a, b in zip(ini, fin):
                ax.axvspan(t[a], t[b - 1] + paso, color=FONDO_PERIODO[per[a] - 1], lw=0, zorder=0)
        lim = actual[per - 1]
        ax.plot(t, kw, color="#707070", lw=0.6, zorder=2)
        ax.fill_between(t, lim, kw, where=kw > lim, color=COLOR_EXCESO, alpha=0.6, lw=0, step="post", zorder=3)
        for i, esc in enumerate(escenarios):
            ax.plot(t, esc.pc[per - 1], color=color(i), lw=1.4, drawstyle="steps-post",
                    ls=ESTILOS_LINEA[i % len(ESTILOS_LINEA)], zorder=4)
        tope = max(kw.max() if len(kw) else 0, max(e.pc.max() for e in escenarios))

    ax.set_ylim(0, tope * 1.08 if tope else 1)
    ax.set_ylabel("kW", fontsize=8)
    ax.tick_params(axis="y", labelsize=7)
    if mes is None:
        _formato_meses(ax)
    else:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d"))
        ax.tick_params(axis="x", labelsize=7)
        ax.set_xlabel(f"Día ({estudio.etiquetas_meses[mes]})", fontsize=8)
    _ejes_limpios(ax)
    texto_p = f"P{periodo}" if periodo else "todos los periodos"
    texto_m = estudio.etiquetas_meses[mes] if mes is not None else "año completo"
    ax.set_title(f"{titulo} – {texto_p} – {texto_m}", fontsize=10, fontweight="bold")
    handles = _leyenda_escenarios(escenarios, con_exceso=False, demanda_linea=True)
    from matplotlib.patches import Patch
    handles.insert(1, Patch(color=COLOR_EXCESO, alpha=0.6, label="Exceso sobre la potencia actual"))
    if not periodo and mes is not None:
        handles += [Patch(color=FONDO_PERIODO[k], label=f"P{k + 1}") for k in range(6)]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.12 if mes is None else -0.16),
              ncol=min(len(handles), 5), fontsize=7, frameon=False)


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

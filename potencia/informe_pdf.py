"""Informe PDF del estudio de optimización de potencia (formato GE&PE)."""

import io

import pandas as pd

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .calculo import MESES_NOMBRE, fmt, fmt_pot, ruta_recurso, texto_conceptos
from .graficos import (AZUL_OSCURO, COLORES_SUAVES, color, dibujar_costes, dibujar_curva,
                       dibujar_maximos)

GRIS = colors.HexColor("#D9D9D9")
AZUL = colors.HexColor(AZUL_OSCURO)
FILA_CLARA = colors.HexColor("#DCE6F1")
ROJO = colors.HexColor("#C00000")

_E = {
    "normal": ParagraphStyle("n", fontName="Helvetica", fontSize=7.5, leading=9.5),
    "negrita": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=7.5, leading=9.5),
    "titulo": ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=11, leading=13),
    "celda": ParagraphStyle("c", fontName="Helvetica-Bold", fontSize=7, leading=8.2, alignment=TA_CENTER,
                            textColor=colors.white),
    "celda_n": ParagraphStyle("cn", fontName="Helvetica-Bold", fontSize=7, leading=8.2, alignment=TA_CENTER),
    "pie": ParagraphStyle("p", fontName="Helvetica", fontSize=6.5, leading=8),
    "subrayado": ParagraphStyle("s", fontName="Helvetica", fontSize=7.5, leading=9.5, underlineWidth=0.5),
}


def _figura_png(dibujar, ancho_mm, alto_mm, *args):
    fig = Figure(figsize=(ancho_mm / 25.4, alto_mm / 25.4), dpi=200, layout="constrained")
    FigureCanvasAgg(fig)
    dibujar(fig, *args)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200)
    buf.seek(0)
    return Image(buf, width=ancho_mm * mm, height=alto_mm * mm)


def _logo(alto_mm):
    ruta = ruta_recurso("assets/logo_geype.png")
    if not ruta.exists():
        return Spacer(1, alto_mm * mm)
    from PIL import Image as PILImage
    with PILImage.open(ruta) as im:
        w, h = im.size
    return Image(str(ruta), width=alto_mm * mm * w / h, height=alto_mm * mm)


def _cabecera(datos, titulo):
    banda = Table([[Paragraph(titulo, _E["titulo"])]], colWidths=[100 * mm],
                  style=[("BACKGROUND", (0, 0), (-1, -1), GRIS), ("TOPPADDING", (0, 0), (-1, -1), 3),
                         ("BOTTOMPADDING", (0, 0), (-1, -1), 4)])
    t = Table([[banda, _logo(14),
                Table([[Paragraph("<font color='white'><b>Fecha</b></font>", _E["normal"]),
                        Paragraph(datos.get("fecha", ""), _E["normal"])]],
                      colWidths=[18 * mm, 22 * mm],
                      style=[("BACKGROUND", (0, 0), (0, 0), AZUL), ("ALIGN", (0, 0), (-1, -1), "CENTER")])]],
              colWidths=[105 * mm, 67 * mm, 105 * mm])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "CENTER"),
                           ("ALIGN", (2, 0), (2, 0), "RIGHT"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    t.hAlign = "LEFT"
    return t


def _datos_cliente(datos):
    filas = [("Titular", datos.get("titular", "")), ("CUPS", datos.get("cups", "")),
             ("Tarifa", datos.get("tarifa", "")), ("Instalación", datos.get("instalacion", "")),
             ("Dirección", datos.get("direccion", "")), ("Zona", datos.get("zona", ""))]
    t = Table([[k, Paragraph(f"<b>{v}</b>" if k in ("Titular", "Tarifa", "Instalación") else v, _E["normal"])]
               for k, v in filas], colWidths=[22 * mm, 150 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7.5), ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5), ("TOPPADDING", (0, 0), (-1, -1), 0.5)]))
    return t


def _tabla_mensual(estudio, escenarios, ancho_mm):
    n = len(escenarios)
    prop = escenarios[1:]
    cab1 = [Paragraph("Mes", _E["celda"]), Paragraph("Coste potencia facturada (€)<br/>"
                                                     "<font color='#FFFF00'>(sin i.e.)</font>", _E["celda"])]
    cab1 += [""] * (n - 1)
    cab1 += [Paragraph("Ahorro anual (€)<br/><font color='#FFFF00'>(sin i.e.)</font>", _E["celda"])] + \
        [""] * (len(prop) - 1)
    cab2 = [""] + [Paragraph(e.nombre, _E["celda"]) for e in escenarios] + \
        [Paragraph(f"Actual -<br/>{e.nombre}", _E["celda_n"]) for e in prop]
    filas = [cab1, cab2]
    for i, mes in enumerate(estudio.etiquetas_meses):
        fila = [mes] + [fmt(e.coste.total_mes[i]) for e in escenarios]
        fila += [fmt(escenarios[0].coste.total_mes[i] - e.coste.total_mes[i]) for e in prop]
        filas.append(fila)
    filas.append(["Total"] + [fmt(e.coste.total) for e in escenarios] + [fmt(e.ahorro) for e in prop])

    w_mes = 16
    w = (ancho_mm - w_mes) / (n + len(prop))
    t = Table(filas, colWidths=[w_mes * mm] + [w * mm] * (n + len(prop)), repeatRows=2)
    est = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (1, 0), (n, 0)), ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (0, 0), (-1, 0), AZUL), ("BACKGROUND", (0, 1), (0, 1), AZUL),
        ("GRID", (0, 0), (-1, -2), 0.4, colors.white),
        ("BACKGROUND", (0, 2), (-1, -2), FILA_CLARA),
        ("FONTNAME", (0, 2), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, AZUL),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
    ]
    if prop:
        est.append(("SPAN", (n + 1, 0), (-1, 0)))
    for i in range(n):
        est.append(("BACKGROUND", (1 + i, 1), (1 + i, 1), colors.HexColor(color(i))))
    for j, e in enumerate(prop):
        c = n + 1 + j
        est.append(("BACKGROUND", (c, 1), (c, 1), colors.HexColor(COLORES_SUAVES[(j + 1) % len(COLORES_SUAVES)])))
        est.append(("BACKGROUND", (c, 2), (c, -2), colors.HexColor(COLORES_SUAVES[(j + 1) % len(COLORES_SUAVES)])))
        est.append(("BACKGROUND", (c, -1), (c, -1), colors.HexColor(color(j + 1))))
        est.append(("TEXTCOLOR", (c, -1), (c, -1), colors.white))
        for i in range(len(estudio.meses)):
            if escenarios[0].coste.total_mes[i] - e.coste.total_mes[i] < 0:
                est.append(("TEXTCOLOR", (c, 2 + i), (c, 2 + i), ROJO))
    t.setStyle(TableStyle(est))
    return t


def _tabla_optimizacion(escenarios):
    cab0 = [Paragraph("OPTIMIZACIÓN DE POTENCIA <font color='#FFFF00'>(sin i.e)</font>", _E["celda"])] + [""] * 14
    cab1 = ["", Paragraph("Potencias contratadas (kW)", _E["celda"]), "", "", "", "", "",
            Paragraph("Coste de la potencia facturada (€)", _E["celda"]), "", "",
            Paragraph("Ahorro estimado (€) (*)", _E["celda"]), "",
            Paragraph("Inversión (**)", _E["celda"]), Paragraph("PRS (años)", _E["celda"]), ""]
    cab2 = [Paragraph("Tipo", _E["celda"])] + [f"P{i}" for i in range(1, 7)] + \
        [Paragraph("T. Fijo", _E["celda"]), Paragraph("T. Excesos", _E["celda"]),
         Paragraph("Total", _E["celda"]), Paragraph("Total (€)", _E["celda"]), "%", "", "", ""]
    filas = [cab0, cab1, cab2]
    for i, e in enumerate(escenarios):
        fila = [e.nombre] + [fmt_pot(p) for p in e.pc] + \
            [fmt(e.coste.total_fijo), fmt(e.coste.total_exceso), fmt(e.coste.total)]
        if i == 0:
            fila += ["-", "-", "", "", ""]
        else:
            prs = e.prs
            fila += [fmt(e.ahorro), f"{fmt(100 * e.ahorro_pct, 1)}%",
                     fmt(e.inversion.get("total", 0), 2) if e.inversion.get("total") else "-",
                     fmt(prs, 2) if prs is not None else "-", ""]
        filas.append(fila)
    anchos = [24] + [19] * 6 + [21, 21, 21, 21, 15, 21, 21, 4]
    t = Table(filas, colWidths=[a * mm for a in anchos])
    est = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN", (0, 0), (-2, 0)), ("SPAN", (1, 1), (6, 1)), ("SPAN", (7, 1), (9, 1)),
        ("SPAN", (10, 1), (11, 1)), ("SPAN", (12, 1), (12, 2)), ("SPAN", (13, 1), (13, 2)),
        ("SPAN", (0, 1), (0, 1)),
        ("BACKGROUND", (0, 0), (-2, 2), AZUL), ("TEXTCOLOR", (0, 0), (-2, 2), colors.white),
        ("BACKGROUND", (7, 2), (7, 2), colors.HexColor("#948A54")),
        ("BACKGROUND", (8, 2), (8, 2), colors.HexColor("#E26B6B")),
        ("GRID", (0, 1), (-2, -1), 0.4, colors.white),
        ("BACKGROUND", (1, 3), (-2, -1), FILA_CLARA),
        ("FONTNAME", (0, 3), (0, -1), "Helvetica-Bold"), ("TEXTCOLOR", (0, 3), (0, -1), colors.white),
        ("FONTNAME", (10, 4), (10, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.3), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.3),
    ]
    for i in range(len(escenarios)):
        est.append(("BACKGROUND", (0, 3 + i), (0, 3 + i), colors.HexColor(color(i))))
    t.setStyle(TableStyle(est))
    return t


def _tabla_anexo(titulo, estudio, matriz, dec, fila_extra, etiqueta_extra, max_col=False):
    cab = [Paragraph(titulo, _E["celda"])] + [""] * 7
    cab2 = ["Desde", "Hasta"] + [f"P{i}" for i in range(1, 7)] + (["Máximo"] if max_col else ["Total"])
    filas = [cab + [""], cab2]
    for i, m in enumerate(estudio.meses):
        fila = [m.start_time.strftime("%d/%m/%Y"), m.end_time.strftime("%d/%m/%Y")]
        fila += [fmt(v, dec) for v in matriz[i]]
        fila.append(fmt(matriz[i].max() if max_col else matriz[i].sum(), dec))
        filas.append(fila)
    filas.append(["", "Total" if not max_col else "Máximo"] +
                 [fmt(v, dec) for v in fila_extra[0]] + [fmt(fila_extra[1], dec)])
    filas.append(["", etiqueta_extra] + [f"{fmt(100 * v, 1)}%" for v in fila_extra[2]] + [""])
    t = Table(filas, colWidths=[20 * mm, 20 * mm] + [22 * mm] * 6 + [24 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 1), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 1), colors.white), ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (-1, -3), FILA_CLARA), ("GRID", (0, 1), (-1, -3), 0.4, colors.white),
        ("FONTNAME", (0, -2), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.1),
    ]))
    return t


def generar_pdf(ruta, datos, estudio, escenarios, curva, normativa, incluir_anexos=True):
    """
    datos: dict con titular, cups, tarifa, instalacion, direccion, zona, fecha.
    escenarios: [Actual, Propuesta 1, ...] (calculo.Escenario).
    curva: potencia.lector_curva.CurvaCargada (para las notas).
    """
    doc = SimpleDocTemplate(str(ruta), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=8 * mm, bottomMargin=8 * mm,
                            title="Optimización de la potencia contratada", author="GE&PE Ingeniería")
    historia = [_cabecera(datos, "Optimización de la potencia contratada"), Spacer(1, 1 * mm),
                _datos_cliente(datos), Spacer(1, 2 * mm)]

    ancho_tabla = 120 if len(escenarios) <= 3 else 150
    ancho_graf = 277 - ancho_tabla - 5
    historia.append(Table([[_tabla_mensual(estudio, escenarios, ancho_tabla),
                            _figura_png(dibujar_costes, ancho_graf, 68, estudio, escenarios)]],
                          colWidths=[(ancho_tabla + 3) * mm, (ancho_graf + 2) * mm],
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)],
                          hAlign="LEFT"))
    historia += [Spacer(1, 2 * mm), _tabla_optimizacion(escenarios), Spacer(1, 1 * mm)]

    notas = ["* Este porcentaje es sobre el coste de potencia actual"]
    for e in escenarios[1:]:
        if e.inversion.get("total"):
            notas.append(f"** Inversión en concepto de {texto_conceptos(e.inversion['conceptos'])} ({e.nombre})")
    if any(max(e.pc) > max(escenarios[0].pc) for e in escenarios[1:]):
        notas.append("(1) Las propuestas con potencia máxima superior a la actual requieren modificación técnica "
                     "(ampliación de la potencia asociada a la acometida).")
    izquierda = [Paragraph(n, _E["pie"]) for n in notas]

    ini, fin = estudio.meses[0], estudio.meses[-1]
    tipo = "horaria (cuartos de hora estimados con la potencia media horaria)" if curva.es_horaria         else "cuartohoraria"
    derecha = [Paragraph("<u>Normativa de referencia:</u>", _E["normal"])]
    derecha += [Paragraph(n, _E["pie"]) for n in normativa]
    derecha += [Spacer(1, 1.5 * mm), Paragraph("<u>Notas:</u>", _E["normal"]), Paragraph(
        f"Estudio realizado utilizando la curva {tipo} de potencia correspondiente al periodo de consumo entre "
        f"{MESES_NOMBRE[ini.month - 1]} {ini.year} y {MESES_NOMBRE[fin.month - 1]} {fin.year}. "
        f"Curva de carga utilizada: desde {curva.fecha_inicio:%d/%m/%Y} hasta "
        f"{(curva.fecha_fin - pd.Timedelta(days=1)):%d/%m/%Y}.", _E["pie"])]
    historia.append(Table([[izquierda, derecha]], colWidths=[118 * mm, 159 * mm], hAlign="LEFT",
                          style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    if incluir_anexos:
        energia = estudio.energia_kwh()
        maximos = estudio.maximos()
        historia += [PageBreak(), _cabecera(datos, "ANEXO: Energía y potencia registradas"), Spacer(1, 4 * mm)]
        tot_e = energia.sum(0)
        historia.append(_tabla_anexo("PERFIL DE CONSUMO (kWh)", estudio, energia, 0,
                                     (tot_e, tot_e.sum(), tot_e / tot_e.sum() if tot_e.sum() else tot_e * 0),
                                     "Porcentaje"))
        historia.append(Spacer(1, 5 * mm))
        max_p = maximos.max(0)
        historia.append(_tabla_anexo("POTENCIAS MÁXIMAS DEMANDADAS (kW)", estudio, maximos, 0,
                                     (max_p, max_p.max(), max_p / max_p.max() if max_p.max() else max_p * 0),
                                     "Porcentaje", max_col=True))
        historia += [PageBreak(), _cabecera(datos, "ANEXO: Curva de carga"), Spacer(1, 3 * mm),
                     _figura_png(dibujar_curva, 270, 85, estudio, escenarios[:3]), Spacer(1, 2 * mm),
                     _figura_png(dibujar_maximos, 270, 75, estudio, escenarios[0].pc)]

    doc.build(historia)

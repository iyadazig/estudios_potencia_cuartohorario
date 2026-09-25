"""Estudio de optimización de la potencia contratada (6.1TD / 3.0TD) – GE&PE."""

import sys


def comprobar(ruta_curva, ruta_pdf, tarifa="6.1TD", zona="Península"):
    """
    Comprobación sin ventanas (útil para verificar el ejecutable en otro equipo):
        EstudioPotencia.exe --prueba curva.xlsx informe.pdf
    Lee la curva, calcula la potencia óptima, genera el PDF y deja el resultado en informe.pdf.txt.
    """
    from potencia.calculo import Estudio, Tarifa, cargar_precios, evaluar, fmt, opciones_inversion_defecto
    from potencia.informe_pdf import generar_pdf
    from potencia.lector_curva import LectorCurva

    lineas = []
    try:
        curva = LectorCurva(ruta_curva).procesar(zona)
        precios = cargar_precios()
        estudio = Estudio(curva.datos, zona, Tarifa.desde_precios(precios, tarifa), precios.get("festivos"))
        optimo = estudio.optimo()
        actual = [max(1, int(estudio.max_demanda() * 0.8))] * 6
        escenarios = evaluar(estudio, [("Propuesta 1", optimo, opciones_inversion_defecto(optimo, actual))], actual)
        generar_pdf(ruta_pdf, {"titular": "Comprobación", "tarifa": tarifa, "zona": zona}, estudio, escenarios,
                    curva, precios.get("normativa", []))
        lineas += ["OK", f"Hoja: {curva.hoja}", f"Unidad: {curva.descripcion_unidad}",
                   f"Potencia óptima: {[int(p) for p in optimo]}",
                   f"Coste óptimo: {fmt(escenarios[1].coste.total, 2)} EUR", f"PDF: {ruta_pdf}"]
        codigo = 0
    except Exception as e:  # se informa en el fichero de resultado
        import traceback
        lineas += ["ERROR", str(e), traceback.format_exc()]
        codigo = 1
    with open(str(ruta_pdf) + ".txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    return codigo


def comprobar_gemweb(cups, ruta_txt):
    """
    Comprobación de la conexión con Gemweb (credenciales guardadas o variables GEMWEB_CLIENT_ID/SECRET):
        EstudioPotencia.exe --prueba-gemweb CUPS resultado.txt
    Descarga la última semana del CUPS y deja el resultado en resultado.txt.
    """
    from datetime import date, timedelta

    from potencia import gemweb

    try:
        credenciales = gemweb.cargar_credenciales()
        if not credenciales:
            raise gemweb.GemwebError("No hay credenciales de Gemweb configuradas.")
        cliente = gemweb.ClienteGemweb(*credenciales)
        s = cliente.buscar_suministro(cups)
        if s is None:
            raise gemweb.GemwebError(f"{cups} no está en el inventario de Gemweb.")
        hasta = date.today() - timedelta(days=30)
        df, fallidos = cliente.descargar_curva(s["id"], hasta - timedelta(days=7), hasta)
        lineas = ["OK", f"Suministro {s['id']} · {s.get('tarifa_acces')} · {s.get('nom')}",
                  f"{len(df)} cuartos de hora descargados", *fallidos]
        codigo = 0
    except Exception as e:
        lineas, codigo = ["ERROR", str(e)], 1
    with open(ruta_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    return codigo


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "--prueba":
        sys.exit(comprobar(sys.argv[2], sys.argv[3]))
    if len(sys.argv) >= 4 and sys.argv[1] == "--prueba-gemweb":
        sys.exit(comprobar_gemweb(sys.argv[2], sys.argv[3]))
    from potencia.gui import main
    main()

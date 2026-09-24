# Estudio de optimización de la potencia contratada (GE&PE)

Programa de escritorio en Python (tkinter) que, a partir de la **curva de carga de 12 meses** de un
suministro eléctrico con peaje **6.1TD** o **3.0TD > 50 kW**, calcula:

- El coste actual del término de potencia (término fijo + excesos cuarto a cuarto), mes a mes.
- La **potencia óptima** por periodo (Propuesta 1), en kW enteros y con P1 ≤ P2 ≤ … ≤ P6.
- Cualquier otra combinación de potencias que se quiera comparar (Propuesta 2, 3, …, editables con el botón
  **Calcular**; el desplegable **➕ Propuestas** añade más).
- El ahorro anual, la inversión en derechos de acometida/enganche y el periodo de retorno simple (PRS).
- Anexos: energía y potencias máximas por mes y periodo; detalle de costes (término fijo, excesos y total, con
  desglose por periodos); curva de carga en 6 paneles (uno por periodo) y curva con selector de periodo y mes.
- Exportación a **PDF** con el logotipo de GE&PE (los anexos incluyen el coste mensual fijo/excesos/total por escenario).

## Instalación y uso

```bash
pip install -r requirements.txt
python main.py
```

1. Al arrancar se elige la **zona** (Península, Illes Balears, Canarias, Ceuta o Melilla).
2. Se rellenan los datos del suministro y la tarifa.
3. **Cargar curva de carga…**: se muestra cómo se ha interpretado el fichero (columnas, unidad, convenio horario,
   huecos, cambios de hora) y se pueden corregir los ajustes antes de aceptar.
4. Se introducen las potencias actuales y se pulsa **CALCULAR**.
5. **EXPORTAR PDF** genera el informe (con o sin anexos).

## Ficheros de curva admitidos

El lector (`potencia/lector_curva.py`) detecta automáticamente:

| Aspecto | Opciones |
|---|---|
| Formato | CSV/TXT (separador `;` `,` tabulador `\|`), Excel `.xlsx/.xlsm/.xls` (elige la hoja con la curva) |
| Cabecera | Con o sin cabecera (p. ej. ficheros P5D de REE) |
| Fecha y hora | Una columna fecha-hora, o fecha + hora (+ cuarto), o formato ancho (una fila por día y 24/25 columnas) |
| Hora | `HH:MM`, horas enteras 0-23 o 1-24/25, fracciones de día de Excel, ISO 8601 con desfase horario |
| Resolución | Cuartohoraria (15 min) u horaria (60 min) |
| Unidad | kW (potencia media), kWh o Wh (energía del intervalo) |
| Varios CUPS | Se elige cuál estudiar |

**Convenio horario.** Según el Sistema de Medidas de REE (*Ficheros para el intercambio de información de
medida*), la etiqueta de tiempo de cada registro corresponde al **final** del periodo de integración: el primer
cuarto del día es `00:15` y el último `00:00` del día siguiente (`24:00`); en curvas horarias, la hora 1 es de
0 h a 1 h. Si el fichero no aporta pistas claras, se asume este convenio (se puede cambiar en el diálogo de carga).

**Cambios de hora.** Todos los días se normalizan a 96 cuartos de hora:
- día de 23 h (marzo): la hora inexistente se rellena con el promedio de la hora anterior y la posterior;
- día de 25 h (octubre): la hora repetida se sustituye por el promedio de sus dos registros.

**Huecos** sin dato: se rellenan con el promedio de la hora anterior y posterior y se avisa del número de
intervalos estimados.

**Curvas horarias.** Cada cuarto de hora toma la potencia media de su hora (art. 9 de la Circular 3/2020, cuando no
hay registro cuartohorario). Los picos de 15 minutos quedan suavizados, por lo que los excesos reales pueden ser
mayores: el programa lo advierte.

Si la curva abarca más de 12 meses se usan los 12 últimos meses completos.

## Metodología

Circular 3/2020 de la CNMC (art. 7 y 9), con la redacción de la Circular 1/2025, vigente desde el 1/4/2025.

- **Término fijo**: `Σp Pc_p · Tp_p · días / 365`, donde `Tp` = peajes de transporte y distribución + cargos.
- **Excesos** (puntos de medida tipo 1, 2 y 3; 3.0TD > 50 kW es tipo 3), por mes y periodo:
  `FEP = Σp tep_p · √( Σj (Pd_j − Pc_p)² )`, sumando solo los cuartos de hora con `Pd_j > Pc_p`.
- **Periodos**: temporadas, tipos de día y horarios del art. 7 para cada sistema eléctrico. Los sábados, domingos,
  el 6 de enero y los festivos nacionales de fecha fija son P6 todo el día.
- **Óptimo**: el coste de cada periodo es convexo en su potencia; se evalúan todas las potencias enteras y se
  aplica el algoritmo *pool adjacent violators* para imponer P1 ≤ … ≤ P6 (óptimo entero exacto).
- **Inversión**: si la potencia máxima propuesta supera a la actual, derechos de acceso y extensión (€/kW sobre el
  aumento) más el enganche; si no, solo el enganche. Se puede ajustar con las casillas de cada propuesta.

## Actualizar precios

Todos los precios están en [`config/precios.json`](config/precios.json) (2026: Resolución CNMC de 18/12/2025 y
Orden TED/1524/2025). Cada año hay que actualizar los peajes, cargos, `tep` y, si cambian, los derechos de acometida.
En ese fichero se pueden añadir también festivos (`adicionales`) o excluirlos (`excluidos`).

## Estructura

```
main.py                    arranque
config/precios.json        precios regulados y festivos
assets/logo_geype.png      logotipo del informe
potencia/
  calendario.py            periodos P1-P6 por zona, festivos y cambios de hora
  lector_curva.py          lectura robusta y normalización de curvas
  calculo.py               costes, óptimo, inversión y escenarios
  graficos.py              gráficos (interfaz y PDF)
  informe_pdf.py           informe PDF
  gui.py                   interfaz tkinter
tests/                     pruebas con curvas sintéticas en 6 formatos distintos
```

## Pruebas

```bash
python -m pytest
```

Las pruebas usan curvas **sintéticas** generadas por `tests/generador.py`. No se deben subir al repositorio curvas ni
informes de clientes (el `.gitignore` excluye `*.csv`, `*.xlsx`, `*.pdf`…).

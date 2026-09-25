# Estudio de optimización de la potencia contratada (GE&PE)

Programa de escritorio en Python (tkinter) que, a partir de la **curva de carga de 12 meses** de un
suministro eléctrico con peaje **6.1TD** o **3.0TD > 50 kW**, calcula:

- El coste actual del término de potencia (término fijo + excesos cuarto a cuarto), mes a mes.
- La **potencia óptima** por periodo (Propuesta 1), en kW enteros y con P1 ≤ P2 ≤ … ≤ P6.
- Cualquier otra combinación de potencias que se quiera comparar (Propuesta 2, 3, …, editables con el botón
  **Calcular**; el desplegable **➕ Propuestas** añade más).
- El ahorro anual, la inversión en derechos de acometida/enganche y el periodo de retorno simple (PRS).
- Anexos: energía y potencias máximas por mes y periodo; detalle de costes (fijo por periodo, total fijo, excesos
  por periodo, total excesos y TOTAL); curva de carga con selector de periodo y mes (el PDF usa la misma selección).
- Exportación a **PDF** con el logotipo de GE&PE (los anexos incluyen el coste mensual fijo/excesos/total por escenario).

## Instalación y uso

```bash
pip install -r requirements.txt
python main.py
```

1. Al arrancar se elige el **tipo de estudio** (individual o multipunto) y la **zona** (Península, Illes Balears,
   Canarias, Ceuta o Melilla).
2. Se rellenan los datos del suministro y la tarifa.
3. **Cargar curva de carga…**: se muestra cómo se ha interpretado el fichero (columnas, unidad, convenio horario,
   huecos, cambios de hora) y se pueden corregir los ajustes antes de aceptar.
4. Se introducen las potencias actuales y se pulsa **CALCULAR**.
5. **EXPORTAR PDF** genera el informe (con o sin anexos).

## Estudio multipunto

En la ventana inicial se elige **Multipunto** para estudiar varios suministros a la vez:

1. Se carga **un único fichero** con la curva de todos los CUPS (debe tener una columna con el CUPS de cada registro).
2. Aparece un bloque por CUPS donde se indican su denominación, dirección, **tarifa**, **zona** y potencias actuales.
   Cada CUPS tiene su Propuesta 1 (óptima), su Propuesta 2 editable y su propio menú **➕ Propuestas**.
3. Arriba se muestra el **resumen conjunto** (situación actual frente a la óptima de cada CUPS, mes a mes) y una
   tabla con una fila por CUPS (coste actual, óptimo, ahorro, inversión y PRS) y el total.
4. En los anexos se elige un CUPS concreto o **Todos (suma)**.
5. El PDF incluye la página de resumen conjunto y, a continuación, las páginas de cada CUPS (con sus anexos si se
   piden).

## Descarga desde Gemweb

El botón **🌐 Descargar de Gemweb…** descarga la curva cuartohoraria de los CUPS indicados directamente de la API
de Gemweb (en multipunto, varios CUPS de una vez), sin tener que preparar ningún fichero:

1. La primera vez se piden las credenciales de la API (Client ID y Client secret; se pueden importar del
   `.streamlit/secrets.toml` del proyecto API_Gemweb). Se validan y se guardan en `%APPDATA%\EstudioPotencia` con la
   clave cifrada para el usuario de Windows.
2. Se indican los CUPS y el periodo (por defecto, los 12 últimos meses completos).
3. Para cada CUPS se busca su id en el inventario de Gemweb y se descarga el consumo cuartohorario (kWh) en tramos
   mensuales; el programa lo convierte a potencia como cualquier fichero de curva (hora de fin del cuarto).
4. Opcionalmente se rellenan la **tarifa**, las **potencias contratadas**, la denominación, la dirección y (en
   multipunto) la **zona** según el código postal, con los datos del inventario de Gemweb.
5. Se avisa si Gemweb no tiene datos de todo el periodo o si el suministro tiene lectura **horaria** (los cuartos de
   hora son entonces un reparto de la energía horaria).

## Ficheros de curva admitidos

El lector (`potencia/lector_curva.py`) detecta automáticamente:

| Aspecto | Opciones |
|---|---|
| Formato | CSV/TXT (separador `;` `,` tabulador `\|`), Excel `.xlsx/.xlsm/.xls` (elige la hoja con la curva) |
| Cabecera | Con o sin cabecera (p. ej. ficheros P5D de REE) |
| Fecha y hora | Una columna fecha-hora, o fecha + hora (+ cuarto), o formato ancho (una fila por día y 24/25 columnas) |
| Hora | `HH:MM`, horas enteras 0-23 o 1-24/25, fracciones de día de Excel, ISO 8601 con desfase horario |
| Resolución | Cuartohoraria (15 min) u horaria (60 min) |
| Unidad | kW, MW o W (potencia media: se usa tal cual) o kWh, MWh o Wh (energía del intervalo: se convierte a kW) |
| Varios CUPS | Se elige cuál estudiar |

**Unidad.** Se lee de los títulos de las columnas y del resto del fichero, por este orden: el título de la columna de
valores (`Potencia (kW)`, `AE_kWh`, `Consumo [MWh]`…, incluida una fila de unidades debajo de los títulos), una
columna de unidades (`Unidad`, `Magnitud`), una nota encima de la tabla (`Unidades: kW`) y, si no hay símbolo, las
palabras del título («potencia» → kW; «consumo», «energía» → kWh). El diálogo de carga indica de dónde se ha sacado
la unidad y si los valores se usan como potencia o se convierten; se puede cambiar a mano.

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
  gemweb.py                conexión con la API de Gemweb (inventario y telelecturas)
  gui_gemweb.py            ventanas de credenciales y descarga de Gemweb
tests/                     pruebas con curvas sintéticas en 6 formatos distintos
```

## Ejecutable de Windows (.exe)

```bash
python -m venv .venv_exe
.venv_exe\Scripts\python -m pip install numpy pandas matplotlib openpyxl xlrd reportlab pillow requests pyinstaller
.venv_exe\Scripts\python construir_exe.py
```

`construir_exe.py` genera `dist/EstudioPotencia.exe` (unos 55 MB; conviene compilar desde un entorno limpio y no
desde Anaconda, que da un ejecutable de más de 200 MB) y copia junto a él `config/precios.json` (si existe, el
programa usa esos precios, así que se pueden actualizar sin regenerarlo) y `LEEME.txt`.

**Credenciales de Gemweb incluidas.** El script mete en el ejecutable las credenciales de la API de Gemweb de GE&PE,
para que los compañeros no tengan que introducirlas. Las lee de un `secrets.toml` local (argumento,
`credenciales_gemweb.toml` en el proyecto o `..\API_Gemweb\.streamlit\secrets.toml`), comprueba que funcionan y
las escribe ofuscadas en `potencia/_credenciales_incluidas.py` solo durante la compilación: ese módulo está en
`.gitignore` (el script se detiene si no lo estuviera) y se borra al terminar junto con la carpeta `build`.
**Nunca hay credenciales en el repositorio.** Un usuario puede usar las suyas con «Usar otras credenciales…».

Comprobaciones sin ventanas: `EstudioPotencia.exe --prueba curva.xlsx informe.pdf` (resultado en `informe.pdf.txt`)
y `EstudioPotencia.exe --prueba-gemweb CUPS resultado.txt`.

## Pruebas

```bash
python -m pytest
```

Las pruebas usan curvas **sintéticas** generadas por `tests/generador.py`. No se deben subir al repositorio curvas ni
informes de clientes (el `.gitignore` excluye `*.csv`, `*.xlsx`, `*.pdf`…).

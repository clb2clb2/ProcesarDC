# ProcesarDC - Guion de pruebas con archivos reales de ej

Esta guia usa archivos ya disponibles en la carpeta ej y fixtures generados en ej/fixtures.

## Archivos a usar

Origen:
- ej/fixtures/origen_contenedor_ok.pdf
- ej/fixtures/origen_contenedor_normal_completo.pdf
- ej/fixtures/origen_conflicto_texto_duplicado.pdf
- ej/fixtures/origen_conflicto_jg_duplicado.pdf
- ej/fixtures/ANEXO.pdf

JP y Excel:
- ej/JP536.pdf
- ej/DATOS JG.xlsx

## Escenario A - Exito rapido en modo sin justificantes

Objetivo:
- Validar extraccion en una sola pasada de marcadores no numericos y numericos.

Pasos:
1. Abrir ProcesarDC.
2. Activar la casilla DC sin justificantes de pago.
3. Cargar como PDFs origen solo ej/fixtures/origen_contenedor_ok.pdf.
4. Pulsar Procesar y elegir carpeta destino.
5. Si pide ano, confirmar 2026.

Salida esperada:
- DC1234.pdf
- CJ5678.pdf
- RT9001.pdf
- ANEXO.pdf
- JG5270.pdf
- JG5283.pdf

Validacion:
- El contenedor origen_contenedor_ok.pdf no debe copiarse al destino.
- No deben aparecer errores de conflicto.

## Escenario B - Error por marcador no numerico duplicado

Objetivo:
- Verificar que duplicados de texto detienen el proceso.

Pasos:
1. Activar modo sin justificantes.
2. Cargar como origen solo ej/fixtures/origen_conflicto_texto_duplicado.pdf.
3. Intentar procesar.

Resultado esperado:
- Error y detencion del proceso por conflicto/duplicado.
- No debe generarse salida final valida.

## Escenario C - Error por marcador numerico duplicado

Objetivo:
- Verificar que dos marcadores JG iguales detienen el proceso.

Pasos:
1. Activar modo sin justificantes.
2. Cargar como origen solo ej/fixtures/origen_conflicto_jg_duplicado.pdf.
3. Intentar procesar.

Resultado esperado:
- Error y detencion del proceso por conflicto/duplicado de JG.

## Escenario D - Error por conflicto marcador vs archivo directo

Objetivo:
- Verificar que si coincide nombre de seccion extraida con archivo directo, hay error.

Pasos:
1. Activar modo sin justificantes.
2. Cargar como origen estos dos PDFs a la vez:
   - ej/fixtures/origen_contenedor_ok.pdf
   - ej/fixtures/ANEXO.pdf
3. Intentar procesar.

Resultado esperado:
- Error por conflicto de nombres (ANEXO extraido por marcador y ANEXO directo).

## Escenario E - Modo normal con JP y Excel (integracion)

Objetivo:
- Probar el flujo completo Analizar + Procesar con contenedor mixto.

Pasos:
1. Desactivar modo sin justificantes.
2. Cargar como origen ej/fixtures/origen_contenedor_normal_completo.pdf.
3. Cargar JP: ej/JP536.pdf.
4. Cargar Excel: ej/DATOS JG.xlsx.
5. Pulsar Analizar.
6. Revisar tabla y completar manualmente cualquier JG vacio o dudoso.
7. Pulsar Procesar.

Resultado esperado:
- La salida contiene DC1234.pdf, CJ5678.pdf y multiples JG<n>.pdf.
- Cada pagina JP asignada se anade al JG correspondiente.

Nota:
- En este escenario la validacion exige que todas las paginas JP queden con JG asignado valido y sin duplicados.

## Registro minimo recomendado

Para cada escenario:
- Fecha y hora.
- Escenario (A, B, C, D, E).
- Resultado obtenido (OK o ERROR esperado).
- Mensaje mostrado por la app.
- Diferencias observadas.

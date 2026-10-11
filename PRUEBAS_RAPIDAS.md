# ProcesarDC - Pruebas Rapidas del Nuevo Flujo de Marcadores

Objetivo: validar que la extraccion desde uno o varios PDFs origen funciona con marcadores numericos y no numericos en una sola pasada.

## Escenario 1: Contenedor unico mixto (caso ideal)

Preparacion:
- Un PDF origen con marcadores: `DC1234`, `CJ5678`, `RT9001`, `ANEXO`, `10001`, `10002`.
- Modo normal: cargar tambien PDF JP y Excel validos para asignar JG `10001` y `10002`.

Pasos:
1. Cargar el PDF origen en la zona de PDFs origen.
2. Cargar JP y Excel.
3. Pulsar Analizar y comprobar que no hay incidencias bloqueantes.
4. Pulsar Procesar y elegir carpeta destino.

Resultado esperado:
- Se crea la carpeta de salida con formato de ano y tipo.
- Se generan: `DC1234.pdf`, `CJ5678.pdf`, `RT9001.pdf`, `ANEXO.pdf`, `JG10001.pdf`, `JG10002.pdf`.
- `JG10001.pdf` y `JG10002.pdf` incluyen al final las paginas JP asignadas.
- El PDF contenedor original NO se copia a destino.

Criterio de exito:
- Salida completa sin errores y nombres coherentes con marcadores.

## Escenario 2: Conflicto por duplicado (debe fallar)

Preparacion:
- Opcion A: un PDF con dos marcadores no numericos iguales (ejemplo: dos `RT9001`).
- Opcion B: dos PDFs origen distintos con el mismo marcador numerico (ejemplo: `10001` en ambos).
- Opcion C: un archivo directo `ANEXO.pdf` y otro PDF con marcador `ANEXO`.

Pasos:
1. Cargar los PDFs origen conflictivos.
2. Intentar procesar (en modo normal o sin JP).

Resultado esperado:
- La app muestra error de conflicto/duplicado y detiene el proceso.
- No debe generarse salida parcial silenciosa.

Criterio de exito:
- La aplicacion detecta conflicto y bloquea de forma consistente.

## Escenario 3: Multiples JG numericos + modo sin justificantes

Preparacion:
- Uno o varios PDFs origen con marcadores: `DC1234`, `CJ5678`, `10001`, `10002`, `10003`.
- Sin JP ni Excel.

Pasos:
1. Activar checkbox "DC sin justificantes de pago".
2. Cargar PDFs origen.
3. Pulsar Procesar y confirmar ano si se solicita.

Resultado esperado:
- Se generan `DC1234.pdf`, `CJ5678.pdf`, `JG10001.pdf`, `JG10002.pdf`, `JG10003.pdf`.
- No se exige JP/Excel.
- Los JG se extraen correctamente por rango de marcador.

Criterio de exito:
- Proceso completado sin analisis y con salida coherente.

## Verificaciones rapidas en cada prueba

- Revisar que no existan paginas vacias en PDFs extraidos.
- Revisar que cada bloque extraido corresponde al tramo correcto entre marcadores.
- Revisar que DC/CJ queden en singular (exactamente uno de cada en salida).
- Revisar que, si hay conflicto, el proceso se detiene antes de escribir resultados inconsistentes.

## Registro sugerido (2 minutos)

Para cada escenario, anotar:
- Entrada usada.
- Resultado (OK/ERROR esperado).
- Mensaje mostrado por la app.
- Diferencias observadas frente a lo esperado.

# orderflow-engine-tools

[English](README.md)

Generadores y verificaciones de la documentación de Orderflow Engine. Las herramientas viven aquí, así nunca se mezclan con los documentos que producen. Sus resultados se guardan en el repositorio `orderflow-engine-docs`.

## Cómo ejecutarlo

Cada herramienta se ejecuta desde la raíz del espacio de trabajo, con los repositorios hermanos (`orderflow-engine-api`, `orderflow-engine-docs`, …) clonados uno al lado del otro.

| Requisito | Versión |
|-----------|---------|
| Node | 18 o superior (sin paquetes) |
| Python | 3.11 o superior, con `pip install -r orderflow-engine-tools/requirements.txt` |
| LibreOffice | Cualquier versión reciente, para la conversión a PDF |

### Con Docker

La imagen contiene Node, Python y los paquetes de Python. Las herramientas se ejecutan desde el espacio de trabajo montado, así que editar una herramienta no exige reconstruir la imagen. Desde la raíz del espacio de trabajo:

```bash
docker build -t orderflow-engine-tools orderflow-engine-tools
```

```bash
docker run --rm -v "$PWD":/workspace orderflow-engine-tools
```

El comando por defecto ejecuta la verificación de la documentación y la de integridad. Cualquier otra herramienta se ejecuta agregando su comando, por ejemplo `python orderflow-engine-tools/diagrams/generate_diagrams.py`. La conversión a PDF se queda en el equipo anfitrión, porque necesita LibreOffice y la fuente Arial de la plantilla de impresión.

## Herramientas

| Carpeta | Qué hace | Comando | Escribe en |
|---------|----------|---------|------------|
| `docs-check/` | Verificación de la documentación: ubicaciones, índice, pares de idioma, enlaces, front matter, encabezados obligatorios, extensión del ADR, claves i18n, gráfica de avance, líneas de commit y fuentes de los entregables | `node orderflow-engine-tools/docs-check/check-docs.mjs` | — |
| `integrity/` | Integridad de los repositorios: entradas obligatorias de `.gitignore`, `.dockerignore` y `.gitattributes`, `.env.example` donde un repositorio corre con Docker, archivos Docker que no salen de su repositorio, y ningún secreto | `node orderflow-engine-tools/integrity/check-integrity.mjs` | — |
| `progress/` | Gráfica de avance de tareas, construida desde la tabla de tareas del HANDOFF | `node orderflow-engine-tools/progress/progress.mjs` | `orderflow-engine-docs/handoff/progress.svg` |
| `diagrams/` | Las figuras de arquitectura, verificadas contra textos desbordados, etiquetas encimadas, líneas cruzadas y líneas que atraviesan cajas | `python orderflow-engine-tools/diagrams/generate_diagrams.py` | `orderflow-engine-docs/diagrams/` |
| `render/` | Word y PDF con la plantilla de impresión (A4, Arial 12, negro): el ADR, de una página como máximo, y el manual de usuario, el manual técnico, el informe de arquitectura y el recorrido de la solución, en inglés y español | `python orderflow-engine-tools/render/build_deliverables.py` | `orderflow-engine-docs/deliverables/` |
| `render/` | Las presentaciones (PowerPoint, 16:9, Arial), una por idioma, con notas del orador | `python orderflow-engine-tools/render/build_presentation.py` | `orderflow-engine-docs/deliverables/delivery/` |
| `screenshots/` | Capturas de pantalla del cliente web en español e inglés, y una imagen PNG de cada figura de arquitectura, para los documentos de entrega | `node /e2e/screenshots/capture.mjs`, dentro de la imagen del ejecutor de pruebas de punta a punta (ver abajo) | `orderflow-engine-docs/delivery/screenshots/`, `orderflow-engine-docs/delivery/figures/` |
| `consistency/` | Referencias cruzadas, cifras declaradas, fugas de idioma y paridad inglés/español | `python orderflow-engine-tools/consistency/<check>.py` | — |

El generador de Word lee el front matter, los encabezados, los párrafos con negrita y código en línea, las viñetas `- `, los pasos numerados `1. `, las tablas con barras, los bloques de código cercados, los avisos (una cita que empieza con una etiqueta en negrita, como `> **Note:**`) y las imágenes en su propia línea, `![caption](path.png)`. La ruta de una imagen es relativa a su archivo Markdown, y la imagen debe ser PNG o JPEG. Se escala al ancho útil, con 18 cm de alto como máximo, y el generador la numera ("Figure N." en inglés, "Figura N." en español), así que los pies de figura no llevan número. Un documento de `orderflow-engine-docs/delivery/` lleva además un bloque de título con su título, el autor que nombra `LICENSE` y su fecha `last-reviewed`. Una imagen que no existe, una imagen en otro formato o un bloque de código sin cerrar detienen la generación con el archivo y la línea.

El generador de presentaciones lee una diapositiva por cada encabezado `##`: viñetas, pasos numerados, como máximo una imagen, y las notas del orador en un último bloque `> **Notes:**` (`> **Notas:**` en español). Escribe los mismos bytes para la misma fuente, y se detiene antes de escribir cualquier presentación cuando falta una imagen o la fuente rompe el formato.

Las capturas necesitan el stack completo en ejecución (el cliente web en el puerto 8081 del equipo anfitrión) y la imagen del ejecutor de pruebas de punta a punta de `orderflow-engine-infra`, que contiene Node, Playwright y Chromium. Desde la raíz del espacio de trabajo:

```bash
docker build --tag ofe-e2e-runner orderflow-engine-infra/e2e
```

```bash
docker run --rm --init --ipc=host --add-host=host.docker.internal:host-gateway \
  -v "$PWD/orderflow-engine-tools/screenshots:/e2e/screenshots:ro" \
  -v "$PWD/orderflow-engine-docs:/docs" \
  ofe-e2e-runner node /e2e/screenshots/capture.mjs
```

La captura de la confirmación registra un pedido por idioma, a crédito de la primera tienda. `CONFIRM=0` (con `-e CONFIRM=0`) no registra ningún pedido y omite esa captura, y `ONLY=screens` u `ONLY=figures` toma solo uno de los dos conjuntos. El encabezado de `screenshots/capture.mjs` lista todas las opciones.

## Origen de cada resultado

| Resultado | Se genera desde |
|-----------|-----------------|
| Figuras | Las definiciones de figuras en `diagrams/generate_diagrams.py`. Cada figura cita su sección de la especificación en el pie |
| Gráfica de avance | La tabla de tareas de `orderflow-engine-docs/handoff/HANDOFF.md` |
| Word y PDF | El ADR en `orderflow-engine-api/docs/adr/` y los documentos de entrega en `orderflow-engine-docs/delivery/`. `deliverables/manifest.json` registra cada fuente y su SHA-256, y el SHA-256 de cada imagen que una fuente incluye |
| Presentaciones | `orderflow-engine-docs/delivery/presentation.md` y `presentation.es.md` |
| Capturas e imágenes de las figuras | El cliente web en ejecución, y las figuras SVG de `orderflow-engine-docs/diagrams/` |

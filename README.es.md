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
| `render/` | El ADR en Word y PDF con la plantilla de impresión (A4, Arial 12, negro), de una página como máximo | `python orderflow-engine-tools/render/build_deliverables.py` | `orderflow-engine-docs/deliverables/` |
| `consistency/` | Referencias cruzadas, cifras declaradas, fugas de idioma y paridad inglés/español | `python orderflow-engine-tools/consistency/<check>.py` | — |

## Origen de cada resultado

| Resultado | Se genera desde |
|-----------|-----------------|
| Figuras | Las definiciones de figuras en `diagrams/generate_diagrams.py`. Cada figura cita su sección de la especificación en el pie |
| Gráfica de avance | La tabla de tareas de `orderflow-engine-docs/handoff/HANDOFF.md` |
| Word y PDF | El ADR en `orderflow-engine-api/docs/adr/`. `deliverables/manifest.json` registra cada fuente y su SHA-256 |

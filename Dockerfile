# Tools image: Python and Node for the documentation generators and checks.
# The image holds only the runtimes and the Python packages. The tools themselves run from the mounted
# workspace (every orderflow-engine-* repository side by side), so a change to a tool needs no rebuild.
# PDF conversion stays on the host: it needs LibreOffice and the Arial font (see README).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# git lets the integrity check verify that no .env is tracked. The mounted workspace belongs to the host
# user, so git is told to trust it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends nodejs git \
 && rm -rf /var/lib/apt/lists/* \
 && git config --system safe.directory '*'

COPY requirements.txt /opt/orderflow-engine-tools/requirements.txt
RUN pip install -r /opt/orderflow-engine-tools/requirements.txt

RUN useradd --create-home --uid 1000 tools
USER tools
WORKDIR /workspace

CMD ["sh", "-c", "node orderflow-engine-tools/docs-check/check-docs.mjs && node orderflow-engine-tools/integrity/check-integrity.mjs"]

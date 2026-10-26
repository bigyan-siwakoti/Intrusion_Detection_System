# Public demo image for triage.bigyan.work: the triage engine + web UI + Suricata 8, in one container.
#
# Large data is NOT baked in (it is not in git): the ET Open ruleset, the extra open rulesets, the local NVD copy and
# the demo capture slices are bind-mounted from ~/triage-data on the server (see docker-compose.yml).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Suricata 8 from the OISF stable PPA (the same source as the development machine), jq for the eve.json tools.
RUN apt-get update \
 && apt-get install -y --no-install-recommends software-properties-common ca-certificates curl \
 && add-apt-repository -y ppa:oisf/suricata-stable \
 && apt-get update \
 && apt-get install -y --no-install-recommends suricata jq python3 python3-venv \
 && apt-get purge -y software-properties-common && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

# The frozen Suricata configs use absolute paths under /home/bigyan/capstone-ids, so the app lives at that path.
ENV APP=/home/bigyan/capstone-ids
WORKDIR $APP

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/ src/
COPY config/ config/
COPY rules/generated/ rules/generated/
COPY demo/ demo/
COPY scripts/demo_entrypoint.sh scripts/

# Run as an unprivileged user; it owns only the app folder (logs and the demo rule files are written at runtime).
RUN useradd --create-home --uid 10001 app \
 && mkdir -p logs rules/extra data/kb data/slices demo-runs /var/lib/suricata/cache \
 && chown -R app:app $APP /var/lib/suricata \
 && chmod -R a+rX /etc/suricata \
 && chmod +x scripts/demo_entrypoint.sh
USER app

ENV TRIAGE_PUBLIC=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl -fs http://127.0.0.1:8000/api/config || exit 1
CMD ["scripts/demo_entrypoint.sh"]

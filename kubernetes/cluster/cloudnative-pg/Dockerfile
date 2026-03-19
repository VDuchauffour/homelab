# Build:
#   docker build -t homelab/cnpg-vectorchord-timescaledb:18 kubernetes/cluster/cloudnative-pg/
#   docker save homelab/cnpg-vectorchord-timescaledb:18 | sudo ctr -n k8s.io images import -
FROM ghcr.io/tensorchord/cloudnative-vectorchord:18-1.1.0

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        lsb-release \
    && echo "deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/timescaledb.list \
    && curl -fsSL https://packagecloud.io/timescale/timescaledb/gpgkey \
        | gpg --dearmor -o /usr/share/keyrings/timescaledb-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/timescaledb-archive-keyring.gpg] https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/timescaledb.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        timescaledb-2-postgresql-18 \
    && apt-get purge -y --auto-remove curl gnupg lsb-release \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER postgres

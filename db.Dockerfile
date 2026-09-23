FROM pgvector/pgvector:pg16

ENV DEBIAN_FRONTEND=noninteractive

# --- Runtime deps ---
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        pgbackrest bzip2 zstd \
        freetds-bin libsybdb5 \
    && rm -rf /var/lib/apt/lists/*

# --- Build tds_fdw and clean up build deps in the same layer ---
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential ca-certificates git \
        postgresql-server-dev-16 freetds-dev; \
    git clone --depth 1 --branch v2.0.4 \
        https://github.com/tds-fdw/tds_fdw.git /tmp/tds_fdw; \
    make -C /tmp/tds_fdw USE_PGXS=1; \
    make -C /tmp/tds_fdw USE_PGXS=1 install; \
    # remove build-only deps
    apt-get purge -y --auto-remove \
        build-essential ca-certificates git \
        postgresql-server-dev-16 freetds-dev; \
    rm -rf /tmp/tds_fdw /var/lib/apt/lists/*

VOLUME /var/lib/pgbackrest
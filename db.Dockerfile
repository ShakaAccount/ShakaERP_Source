FROM pgvector/pgvector:pg16

ENV DEBIAN_FRONTEND=noninteractive

# pgBackRest from the PGDG repo already configured in the base image
RUN apt-get update \
    && apt-get install -y --no-install-recommends pgbackrest bzip2 zstd \
    && rm -rf /var/lib/apt/lists/*

VOLUME /var/lib/pgbackrest
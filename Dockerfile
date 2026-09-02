FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

# 1. Install prerequisites for adding external APT repositories
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    git \
    curl \
    gosu \
    lsb-release \
    gnupg2 \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    nodejs \
    npm \
    fontconfig \
    xfonts-75dpi \
    xfonts-base \
    libjpeg62-turbo \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 2. Add PostgreSQL official repository and install postgresql-client-16
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg \
    && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

# 3. Install rtlcss for Right-To-Left UI support
RUN npm install -g rtlcss

# 4. Install patched wkhtmltopdf (0.12.6.1-3) for proper Odoo PDF reports
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends ./wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/odoo

# 5. Pre-install Python dependencies
COPY requirements.txt /opt/odoo/requirements.txt
RUN pip install --no-cache-dir -r /opt/odoo/requirements.txt

# 6. Create unprivileged odoo user and directories
RUN useradd -m -U -s /bin/bash odoo \
    && mkdir -p /var/lib/odoo /home/odoo/.local \
    && chown -R odoo:odoo /var/lib/odoo /home/odoo

# 7. Copy Entrypoint
# Strip CR *before* chmod: a Windows checkout with core.autocrlf=true gives CRLF + mode 644,
# which yields "exec format error". chmod after sed guarantees the exec bit.
COPY entrypoint.sh /entrypoint.sh
RUN sed -i -e 's/\r$//' -e '1s|^#!/bin/bash|#!/usr/bin/env bash|' /entrypoint.sh && chmod 755 /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8069 8072
CMD ["python3", "odoo-bin"]

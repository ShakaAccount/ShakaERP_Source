FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

# 1. Install system tools, compilation libraries, Node.js, and postgresql-client
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    git \
    curl \
    gosu \
    postgresql-client \
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

# 2. Install rtlcss for Right-To-Left UI support (Persian, Arabic, Hebrew, etc.)
RUN npm install -g rtlcss

# 3. Install patched wkhtmltopdf (0.12.6.1-3) for proper Odoo PDF reports
RUN wget -q https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && apt-get update \
    && apt-get install -y ./wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm wkhtmltox_0.12.6.1-3.bookworm_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/odoo

# 4. Pre-install Python dependencies (leveraging layer caching)
COPY requirements.txt /opt/odoo/requirements.txt
RUN pip install --no-cache-dir -r /opt/odoo/requirements.txt

# 5. Create unprivileged odoo user and directories
RUN useradd -m -U -s /bin/bash odoo \
    && mkdir -p /var/lib/odoo /home/odoo/.local \
    && chown -R odoo:odoo /var/lib/odoo /home/odoo

# 6. Copy Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Entrypoint handles host volume permissions & drops root privilege down to 'odoo'
ENTRYPOINT ["/entrypoint.sh"]

EXPOSE 8069 8072
CMD ["python3", "odoo-bin"]

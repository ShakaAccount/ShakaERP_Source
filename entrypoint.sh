#!/bin/bash
set -e

# Fix ownership for runtime mounted volumes so the 'odoo' user can write to them
mkdir -p /var/lib/odoo/sessions /var/lib/odoo/filestore
chown -R odoo:odoo /var/lib/odoo /home/odoo /opt/odoo

# Windows checkouts can deliver CRLF odoo-bin through the bind mount; the CR in
# the shebang makes exec fail instantly (empty logs, exit 126/127). entrypoint.sh
# itself is CR-stripped at build time (Dockerfile), odoo-bin is not - strip here.
sed -i 's/\r$//' /opt/odoo/odoo-bin 2>/dev/null || true

# Drop root privileges and execute the main container command as 'odoo' user
exec gosu odoo "$@"

#!/bin/bash
set -e

# Fix ownership only for runtime-writable volumes.  /opt/odoo is a bind mount
# of the whole source tree on the host; recursively chowning it makes startup
# extremely slow on Windows and can leave the container stuck before Odoo
# starts listening on port 8069.
mkdir -p /var/lib/odoo/sessions /var/lib/odoo/filestore /home/odoo/.local
chown -R odoo:odoo /var/lib/odoo /home/odoo

# Windows checkouts can deliver CRLF odoo-bin through the bind mount; the CR in
# the shebang makes exec fail instantly (empty logs, exit 126/127). entrypoint.sh
# itself is CR-stripped at build time (Dockerfile), odoo-bin is not - strip here.
sed -i 's/\r$//' /opt/odoo/odoo-bin 2>/dev/null || true

# Drop root privileges and execute the main container command as 'odoo' user
exec gosu odoo "$@"

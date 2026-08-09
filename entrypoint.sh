#!/bin/bash
set -e

# Fix ownership for runtime mounted volumes so the 'odoo' user can write to them
mkdir -p /var/lib/odoo/sessions /var/lib/odoo/filestore
chown -R odoo:odoo /var/lib/odoo /home/odoo /opt/odoo

# Drop root privileges and execute the main container command as 'odoo' user
exec gosu odoo "$@"

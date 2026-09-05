FROM alpine:3.20
RUN apk add --no-cache rsync
# default job: mirror the Odoo filestore (odoo_19_data mounted at /data) to /backup.
# mkdir first: fresh volumes have no filestore/ yet and rsync exits 23 on missing src.
# Override by passing rsync args after the image name: docker run ... image -avh /src /dst
ENTRYPOINT ["/bin/sh", "-c", "mkdir -p /data/filestore && exec /usr/bin/rsync \"$@\"", "rsync-entry"]
CMD ["-a", "--delete", "/data/filestore/", "/backup/"]

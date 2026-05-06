# syntax=docker/dockerfile:1.7
FROM alpine:3.20

# postgresql16-client matches the pg16 server image we run.
RUN apk add --no-cache postgresql16-client tini bash gzip findutils

RUN addgroup -S backup && adduser -S -G backup backup \
 && mkdir -p /backups \
 && chown backup:backup /backups

COPY backup.sh     /usr/local/bin/backup.sh
COPY restore.sh    /usr/local/bin/restore.sh
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh /usr/local/bin/entrypoint.sh

USER backup
WORKDIR /backups
VOLUME ["/backups"]

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/local/bin/entrypoint.sh"]

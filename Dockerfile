FROM alpine:3.24.3
RUN apk add --no-cache apk-tools cpio gzip xorriso syslinux
WORKDIR /src
COPY image/ /src/image/
COPY fixtures/ /src/fixtures/
COPY scripts/make-iso.sh scripts/demo-agent.sh scripts/slack-mock.py /src/scripts/
ENTRYPOINT ["/bin/sh", "/src/scripts/make-iso.sh"]

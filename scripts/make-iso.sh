#!/bin/sh
set -eu
[ "${1:-x86_64}" = x86_64 ] || { echo 'Only x86_64 BIOS is implemented and tested' >&2; exit 2; }
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1793232000}
root=/tmp/kiosk-root
iso=/tmp/kiosk-iso
mkdir -p "$root/etc/apk/keys" "$iso/boot/isolinux" /output
# Only public distribution signing keys; no host keys or account configuration.
cp /etc/apk/keys/* "$root/etc/apk/keys/"
printf '%s\n' https://dl-cdn.alpinelinux.org/alpine/v3.24/main https://dl-cdn.alpinelinux.org/alpine/v3.24/community > "$root/etc/apk/repositories"
apk --root "$root" --arch x86_64 --initdb --no-cache add $(cat /src/image/packages.txt)
mkdir -p "$root/opt/kiosk" "$root/home/kiosk/demo" "$root/etc/X11" "$root/proc" "$root/sys" "$root/dev" "$root/tmp" "$root/run"
chroot "$root" addgroup -g 1000 kiosk
chroot "$root" adduser -D -u 1000 -G kiosk -h /home/kiosk kiosk
# Both accounts locked; no login daemon runs.
chroot "$root" passwd -l root
grep -q '^kiosk:!' "$root/etc/shadow"
cp /src/image/init "$root/init"
cp /src/image/start-kiosk.sh /src/image/emacs-init.el /src/scripts/demo-agent.sh /src/scripts/slack-mock.py "$root/opt/kiosk/"
cp /src/fixtures/slack-events.json "$root/opt/kiosk/slack-events.json"
cp /src/image/README.txt "$root/home/kiosk/demo/README.txt"
cp /src/image/xorg.conf "$root/etc/X11/xorg.conf"
chmod 755 "$root/init" "$root/opt/kiosk/"*.sh
chown -R 1000:1000 "$root/home/kiosk"
apk --root "$root" info -v | LC_ALL=C sort > /output/packages-resolved.txt
cp /src/image/packages.txt /output/packages-requested.txt
cp "$root/boot/vmlinuz-lts" "$iso/boot/vmlinuz"
# No installer or disk probing: all userspace is unpacked into RAM.
rm -rf "$root/boot" "$root/var/cache/apk/"*
(cd "$root" && find . -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} + && find . | LC_ALL=C sort | cpio -o -H newc --quiet | gzip -n -6 > "$iso/boot/initramfs.gz")
cp /usr/share/syslinux/isolinux.bin /usr/share/syslinux/ldlinux.c32 "$iso/boot/isolinux/"
cat > "$iso/boot/isolinux/isolinux.cfg" <<'CFG'
SERIAL 0 115200
DEFAULT kiosk
PROMPT 0
TIMEOUT 1
LABEL kiosk
  KERNEL /boot/vmlinuz
  INITRD /boot/initramfs.gz
  APPEND rdinit=/init console=tty0 console=ttyS0,115200 loglevel=4
CFG
xorriso -as mkisofs -o /output/emacs-kiosk-x86_64.iso -V EMACS_KIOSK -J -R -b boot/isolinux/isolinux.bin -c boot/isolinux/boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table "$iso"
(cd /output && sha256sum emacs-kiosk-x86_64.iso packages-resolved.txt packages-requested.txt > SHA256SUMS)

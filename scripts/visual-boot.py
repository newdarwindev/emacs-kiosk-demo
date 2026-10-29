#!/usr/bin/env python3
"""Boot the ISO, inject real QEMU keyboard events and OCR the guest framebuffer."""
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import time

from PIL import Image

ROOT = Path.cwd()
EVIDENCE = ROOT / 'evidence'
EVIDENCE.mkdir(exist_ok=True)
REPORT = {'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
          'architecture': 'x86_64', 'transport': 'QMP keyboard and guest framebuffer',
          'network': 'none', 'checks': [], 'passed': False}


def normalized(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())


class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(10)
        self.sock.connect(str(path))
        self.file = self.sock.makefile('rwb')
        self.file.readline()
        self.call('qmp_capabilities')

    def call(self, command, **arguments):
        self.file.write((json.dumps({'execute': command, 'arguments': arguments}) + '\n').encode())
        self.file.flush()
        while True:
            reply = json.loads(self.file.readline())
            if 'error' in reply:
                raise RuntimeError(reply['error'])
            if 'return' in reply:
                return reply['return']

    def key(self, *keys):
        self.call('send-key', keys=[{'type': 'qcode', 'data': k} for k in keys], **{'hold-time': 40})
        time.sleep(.09)

    def type(self, text):
        names = {' ': 'spc', '/': 'slash', '.': 'dot', '-': 'minus', '\n': 'ret'}
        for char in text:
            if char.isupper():
                self.key('shift', char.lower())
            else:
                self.key(names.get(char, char))

    def capture(self, name):
        ppm = EVIDENCE / (name + '.ppm')
        png = EVIDENCE / (name + '.png')
        self.call('screendump', filename=str(ppm))
        with Image.open(ppm) as image:
            image.save(png)
        ppm.unlink()
        result = subprocess.check_output(['tesseract', str(png), 'stdout'], text=True, stderr=subprocess.DEVNULL)
        (EVIDENCE / (name + '-ocr.txt')).write_text(result)
        return result

    def expect(self, name, phrase, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = self.capture(name)
            if normalized(phrase) in normalized(text):
                REPORT['checks'].append({'name': name, 'assertion': phrase, 'passed': True})
                print('PASS', name, flush=True)
                return
            time.sleep(2)
        raise AssertionError(f'{name}: expected visible text {phrase!r}; inspect screenshot/OCR')


def main():
    for cmd in ('qemu-system-x86_64', 'tesseract'):
        if not shutil.which(cmd):
            raise RuntimeError(f'{cmd} is required; never substitute static UI rendering')
    iso = ROOT / 'build/emacs-kiosk-x86_64.iso'
    if not iso.is_file():
        raise RuntimeError('Build the actual ISO with make image first')
    # Only a newly created disposable socket is removed, never host files.
    qmp_path = EVIDENCE / 'qmp.sock'
    if qmp_path.exists():
        raise RuntimeError('Existing qmp.sock: check for a running previous test')
    args = ['qemu-system-x86_64', '-machine', 'pc,accel=tcg', '-m', '4096', '-smp', '2',
            '-vga', 'std', '-cdrom', str(iso), '-boot', 'd', '-display', 'none',
            '-nic', 'none', '-serial', f'file:{EVIDENCE}/qemu-serial.log',
            '-qmp', f'unix:{qmp_path},server=on,wait=off', '-no-reboot']
    (EVIDENCE / 'qemu-command.json').write_text(json.dumps(args, indent=2))
    with (EVIDENCE / 'qemu.log').open('w') as output:
        proc = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT)
        try:
            for _ in range(50):
                if qmp_path.exists():
                    break
                if proc.poll() is not None:
                    raise RuntimeError('QEMU exited before monitor initialization')
                time.sleep(.1)
            qmp = QMP(qmp_path)
            qmp.expect('01-boot-emacs', 'Nothing connected', timeout=300)
            serial = (EVIDENCE / 'qemu-serial.log').read_text(errors='replace')
            for marker in ['KIOSK_LINUX_BOOT', 'KIOSK_X_READY', 'Loaded 2 synthetic offline events',
                           'Synthetic agent task ready', 'KIOSK_FIXTURES_COMPLETE']:
                assert marker in serial, f'Missing guest boot assertion: {marker}'
            REPORT['checks'].append({'name': 'guest-boot-and-offline-integrations', 'passed': True})
            qmp.key('ctrl', 'home')
            qmp.type('visual input verified 2026\n')
            qmp.expect('02-typed-marker', 'visual input verified 2026')
            qmp.key('ctrl', 'x'); qmp.key('ctrl', 'f')
            qmp.type('/tmp/cancelled-demo')
            qmp.key('ctrl', 'g'); qmp.key('ctrl', 'g')
            qmp.type('cancel recovered\n')
            qmp.expect('03-cancel-recovery', 'cancel recovered')
            for _ in range(2):
                qmp.key('ctrl', 'x'); qmp.key('b'); qmp.type('repeat-demo\n')
                qmp.type('buffer switch verified\n')
                qmp.expect('04-buffer-switch', 'buffer switch verified')
                qmp.key('ctrl', 'x'); qmp.key('b'); qmp.type('README.txt\n')
                qmp.expect('05-return-to-editor', 'visual input verified 2026')
            qmp.key('alt', 'x'); qmp.type('shell\n'); time.sleep(2)
            qmp.type('python3 /opt/kiosk/slack-mock.py\n')
            qmp.expect('06-slack-fixture', 'Loaded 2 synthetic offline events')
            qmp.type('tmux capture-pane -pt demo\n')
            qmp.expect('07-tmux-output', 'Synthetic agent task ready')
            REPORT['passed'] = True
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
            qmp_path.unlink(missing_ok=True)


try:
    main()
except Exception as exc:
    REPORT['error'] = str(exc)
    raise
finally:
    (EVIDENCE / 'test-report.json').write_text(json.dumps(REPORT, indent=2) + '\n')

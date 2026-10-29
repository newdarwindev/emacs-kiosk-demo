import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PolicyTests(unittest.TestCase):
    def test_fixture_is_synthetic(self):
        data = json.loads((ROOT / 'fixtures/slack-events.json').read_text())
        self.assertEqual(len(data), 2)
        self.assertTrue(all(e['user'] == 'SYNTHETIC_USER' for e in data))

    def test_actions_are_pinned_and_least_privilege(self):
        data = (ROOT / '.github/workflows/linux-image.yml').read_text()
        self.assertIn('permissions:\n  contents: read', data)
        self.assertEqual(len(re.findall(r'uses: \S+@[0-9a-f]{40}', data)), 5)
        self.assertNotIn('secrets.', data)
        self.assertIn('if: always()', data)

    def test_actual_boot_gate(self):
        test = (ROOT / 'scripts/visual-boot.py').read_text()
        self.assertIn("'-cdrom', str(iso)", test)
        self.assertIn("'-nic', 'none'", test)
        self.assertIn("'send-key'", test)
        self.assertIn("'screendump'", test)
        self.assertIn('tesseract', test)
        self.assertIn('cancel-recovery', test)

    def test_build_context_allowlist(self):
        rules = (ROOT / '.dockerignore').read_text().splitlines()
        self.assertEqual([r for r in rules if not r.startswith('#')][0], '*')
        docker = (ROOT / 'Dockerfile').read_text()
        self.assertNotIn('COPY . ', docker)
        self.assertNotIn('--privileged', (ROOT / 'scripts/build-image.sh').read_text())

    def test_no_credential_files(self):
        for path in ROOT.rglob('*'):
            if '.git' in path.parts or 'build' in path.parts or 'evidence' in path.parts:
                continue
            self.assertNotIn(path.suffix, {'.pem', '.key', '.token', '.secret'}, str(path))
            self.assertFalse(path.name == '.env' or path.name.startswith('.env.'), str(path))

    def test_manifest_and_no_real_accounts(self):
        packages = (ROOT / 'image/packages.txt').read_text().splitlines()
        for p in ['linux-lts', 'emacs-x11', 'tmux', 'xorg-server']:
            self.assertIn(p, packages)
        self.assertIn('/opt/kiosk/slack-events.json', (ROOT / 'scripts/slack-mock.py').read_text())
        self.assertNotIn('requests', (ROOT / 'scripts/slack-mock.py').read_text())

    def test_unsupported_arch_fails_explicitly(self):
        self.assertIn('Only x86_64', (ROOT / 'scripts/build-image.sh').read_text())

    def test_evidence_does_not_hash_itself(self):
        self.assertIn('! -name EVIDENCE-SHA256SUMS', (ROOT / 'scripts/package-evidence.sh').read_text())


if __name__ == '__main__':
    unittest.main()

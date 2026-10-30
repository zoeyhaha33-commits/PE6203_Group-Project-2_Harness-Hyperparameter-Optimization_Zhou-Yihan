"""Offline failure-injection checks; no downloads or model requests."""
import subprocess
import tempfile
from pathlib import Path
import shlex
import unittest
from bench_hardened import harden


class InstallTests(unittest.TestCase):
    def test_first_failure_prevents_second_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / 'unexpected'
            command = ('exit 7; # @earendil-works/pi-coding-agent@0.81.0 pi-acp@0.0.34\n'
                       ' && export DEBIAN_FRONTEND=noninteractive; touch ' + shlex.quote(str(sentinel)))
            result = subprocess.run(['sh', '-c', harden(command)])
            self.assertEqual(result.returncode, 7)
            self.assertFalse(sentinel.exists())

    def test_unexpected_installer_refused(self):
        with self.assertRaises(RuntimeError):
            harden('echo unknown installer')


if __name__ == '__main__':
    unittest.main()

"""Tester l'environnement Bash et la saisie masquée sans token réel."""

import errno
import os
import pty
import select
import subprocess
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts/auth.sh"
SECRET = "fixture-$quote'and\\backslash!"


class AuthenticationTests(unittest.TestCase):
    def run_auth(self, input_text, expected, trace=False):
        command = ('set -x; ' if trace else '') + (
            'if source "$1"; then result=0; else result=1; fi; set +x; '
            '[[ ${PROXMOX_VE_API_TOKEN:-} == "$EXPECTED" ]] || exit 99; exit "$result"'
        )
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", command, "bash", str(SCRIPT)],
            input=input_text, capture_output=True, text=True, timeout=5,
            env=dict(os.environ, EXPECTED=expected, PROXMOX_VE_API_TOKEN="previous"),
        )

    def test_source_exports_token_without_tracing_secret(self):
        """Le token est exporté dans le shell appelant, sans fuite même avec set -x."""
        result = self.run_auth("\n" + SECRET + "\n", "iac-postgres@pve!opentofu=" + SECRET, trace=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn(SECRET, result.stdout + result.stderr)

    def test_custom_identity_and_special_characters(self):
        result = self.run_auth("custom@pam!test\n" + SECRET + "\n", "custom@pam!test=" + SECRET)
        self.assertEqual(result.returncode, 0)

    def test_cancel_invalid_identity_and_empty_secret_preserve_environment(self):
        for value in ("", "invalid\n", "custom@pve!test\n", "\n\n", "\nwith spaces\n"):
            with self.subTest(input=value):
                result = self.run_auth(value, "previous")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_execution_explains_source(self):
        result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("source scripts/auth.sh", result.stderr)

    def test_secret_is_not_echoed_on_terminal(self):
        """Un pseudo-terminal confirme que read -s masque réellement la saisie."""
        master, slave = pty.openpty()
        process = subprocess.Popen(
            ["bash", "--noprofile", "--norc", "-c", 'source "$1"', "bash", str(SCRIPT)],
            stdin=slave, stdout=slave, stderr=slave,
        )
        os.close(slave)
        output = b""
        identity_sent = secret_sent = False
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if not select.select([master], [], [], 0.1)[0]:
                    if process.poll() is not None:
                        break
                    continue
                try:
                    chunk = os.read(master, 4096)
                except OSError as error:
                    if error.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output += chunk
                if b"Identifiant du token" in output and not identity_sent:
                    os.write(master, b"\n")
                    identity_sent = True
                if b"Secret du token" in output and not secret_sent:
                    os.write(master, SECRET.encode() + b"\n")
                    secret_sent = True
            self.assertTrue(secret_sent)
            self.assertEqual(process.wait(timeout=1), 0)
            self.assertNotIn(SECRET.encode(), output)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)


if __name__ == "__main__":
    unittest.main()

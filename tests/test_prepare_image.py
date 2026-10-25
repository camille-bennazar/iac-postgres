"""Vérifier la préparation de l'image avec une API et des commandes simulées."""

import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "prepare_image", PROJECT_ROOT / "scripts/prepare_image.py"
)
image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image)

IMAGE_FILENAME = "debian-13-genericcloud-amd64-20261021-2638.qcow2"
IMAGE_VOLUME = f"local:import/{IMAGE_FILENAME}"
IMAGE_CONFIGURATION = {
    "endpoint": "https://pve.example:8006/",
    "node": "pve1",
    "storage": "local",
    "insecure": True,
    "image": {
        "filename": IMAGE_FILENAME,
        "url": f"https://cloud.debian.org/images/cloud/trixie/20261021-2638/{IMAGE_FILENAME}",
    },
}


class ImagePreparationTests(unittest.TestCase):
    def setUp(self):
        """Isoler les fichiers, les appels externes et le token pour chaque test."""
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.terraform_directory = Path(temporary)
        self.enterContext(patch.object(image, "TERRAFORM_DIR", self.terraform_directory))

        self.configuration = self.enterContext(
            patch.object(image, "configuration", return_value=IMAGE_CONFIGURATION)
        )
        self.fetch = self.enterContext(patch.object(image, "fetch"))
        self.run_tofu = self.enterContext(patch.object(image, "run_tofu", return_value=""))
        self.fetch.return_value = (
            {},
            json.dumps({"data": [{"volid": IMAGE_VOLUME}]}).encode(),
        )

        self.enterContext(
            patch.dict(os.environ, {"PROXMOX_VE_API_TOKEN": "fixture-token"}, clear=True)
        )
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_unmanaged_image_is_rejected_without_import(self):
        with self.assertRaisesRegex(image.ImageError, "adoption automatique refusée"):
            image.prepare("tofu")
        self.run_tofu.assert_not_called()
        self.fetch.assert_called_once_with(
            "https://pve.example:8006/api2/json/nodes/pve1/storage/local/content?content=import",
            token="fixture-token",
            insecure=True,
        )

    def test_absent_or_different_file_leaves_download_to_provider(self):
        cases = [
            ("empty storage", []),
            ("different filename", [{"volid": "local:import/other.qcow2"}]),
            ("different storage", [{"volid": f"other:import/{IMAGE_FILENAME}"}]),
        ]
        for name, entries in cases:
            with self.subTest(name=name):
                self.fetch.return_value = ({}, json.dumps({"data": entries}).encode())

                image.prepare("tofu")

                self.run_tofu.assert_not_called()

    def test_existing_state_never_imports_twice(self):
        (self.terraform_directory / "terraform.tfstate").write_text("{}")
        self.run_tofu.return_value = image.RESOURCE + "\n"

        image.prepare("tofu")

        self.run_tofu.assert_called_once_with("tofu", "state", "list")

    def test_api_failure_does_not_trigger_import(self):
        self.fetch.side_effect = image.ImageError("HTTP 403")

        with self.assertRaisesRegex(image.ImageError, "403"):
            image.prepare("tofu")

        self.run_tofu.assert_not_called()

    def test_missing_token_never_contacts_api(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(image.ImageError, "PROXMOX_VE_API_TOKEN"):
                image.prepare("tofu")
        self.fetch.assert_not_called()
        self.run_tofu.assert_not_called()

    def test_malformed_api_payload_never_imports(self):
        for payload in (b"not-json", b"{}", b"null", b'{"data": null}', b'{"data": [null]}'):
            with self.subTest(payload=payload):
                self.fetch.return_value = ({}, payload)
                with self.assertRaises(image.ImageError):
                    image.prepare("tofu")
                self.run_tofu.assert_not_called()


class ImageHelpersTests(unittest.TestCase):
    def test_command_error_hides_stdout_stderr_and_token(self):
        result = type("Result", (), {"returncode": 1, "stdout": "private-output", "stderr": "private-token"})()
        with patch.object(image.subprocess, "run", return_value=result):
            with self.assertRaises(image.ImageError) as raised:
                image.run_tofu("tofu", "console")
        self.assertNotIn("private", str(raised.exception))

    def test_http_failures_hide_response_bodies_and_tokens(self):
        errors = [HTTPError("https://pve.example/secret", 403, "private-token", {}, None),
                  URLError("private-token"), TimeoutError("private-token")]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(image, "build_opener") as build:
                    build.return_value.open.side_effect = error
                    with self.assertRaises(image.ImageError) as raised:
                        image.fetch("https://pve.example/", token="private-token")
                    self.assertNotIn("private-token", str(raised.exception))

    def test_console_reads_effective_variables_without_parsing_tfvars(self):
        console_output = json.dumps(json.dumps(IMAGE_CONFIGURATION))
        with patch.object(image, "run_tofu", return_value=console_output) as run_tofu:
            self.assertEqual(image.configuration("tofu"), IMAGE_CONFIGURATION)
            self.assertIn("local.debian_image", run_tofu.call_args.kwargs["input_text"])

    def test_http_is_refused_and_redirects_cannot_forward_token(self):
        with self.assertRaises(image.ImageError):
            image.fetch("http://pve.example/", token="fixture-token")

        with self.assertRaises(image.ImageError):
            image.NoRedirect().redirect_request(
                None, None, 302, "redirect", {}, "https://other/"
            )


if __name__ == "__main__":
    unittest.main()

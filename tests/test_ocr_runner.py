from __future__ import annotations

import importlib
import ssl
import subprocess
from urllib.error import URLError


class _FakeResponse:
    def __init__(self, payload: bytes, headers: dict[str, str]) -> None:
        self._payload = payload
        self.headers = headers

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_ocr_runner_retries_without_ssl_verification_on_cert_error(tmp_path, monkeypatch) -> None:
    ocr_runner = importlib.import_module("app.skills.ocr.ocr_runner")
    calls = []

    def fake_urlopen(request, timeout=30, context=None):
        _ = request
        _ = timeout
        calls.append(context)
        if len(calls) == 1:
            raise URLError(ssl.SSLCertVerificationError("certificate verify failed"))
        return _FakeResponse(b"fake-image", {"Content-Type": "image/png"})

    monkeypatch.setattr(ocr_runner, "urlopen", fake_urlopen)

    image_path, used_insecure_ssl = ocr_runner._download_image(
        "https://example.com/demo.png",
        1,
        str(tmp_path),
    )

    assert image_path.exists()
    assert image_path.read_bytes() == b"fake-image"
    assert used_insecure_ssl is True
    assert calls[0] is None
    assert calls[1] is not None


def test_ocr_runner_does_not_install_when_dependencies_exist(monkeypatch) -> None:
    ocr_runner = importlib.import_module("app.skills.ocr.ocr_runner")

    def fake_import_module(name: str):
        if name == "rapidocr_onnxruntime":
            return object()
        if name == "PIL":
            return object()
        raise AssertionError(f"unexpected import: {name}")

    def fake_run(*args, **kwargs):
        raise AssertionError("依赖已存在时不应该执行 pip install")

    monkeypatch.setattr(ocr_runner.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(ocr_runner.subprocess, "run", fake_run)

    ocr_runner._ensure_runtime_dependencies()


def test_ocr_runner_installs_dependencies_only_when_missing(monkeypatch) -> None:
    ocr_runner = importlib.import_module("app.skills.ocr.ocr_runner")
    imported_names = []
    commands = []

    def fake_import_module(name: str):
        imported_names.append(name)
        if name == "rapidocr_onnxruntime":
            raise ImportError("missing rapidocr")
        if name == "PIL":
            return object()
        raise AssertionError(f"unexpected import: {name}")

    def fake_run(command, **kwargs):
        commands.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(ocr_runner.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(ocr_runner.subprocess, "run", fake_run)

    ocr_runner._ensure_runtime_dependencies()

    assert imported_names == ["rapidocr_onnxruntime", "PIL"]
    assert len(commands) == 1
    assert commands[0][0] == [
        ocr_runner.sys.executable,
        "-m",
        "pip",
        "install",
        "rapidocr_onnxruntime",
        "pillow",
    ]

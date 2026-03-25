from __future__ import annotations

import importlib
import json
import mimetypes
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

USER_AGENT = "EnterpriseDataAgent/1.0"
OCR_DEPENDENCIES = ("rapidocr_onnxruntime", "pillow")


def _ensure_runtime_dependencies() -> None:
    missing_packages: list[str] = []
    for package_name, import_name in (
        ("rapidocr_onnxruntime", "rapidocr_onnxruntime"),
        ("pillow", "PIL"),
    ):
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing_packages.append(package_name)

    if not missing_packages:
        return

    subprocess.run(
        [sys.executable, "-m", "pip", "install", *OCR_DEPENDENCIES],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _build_ocr_engine():
    _ensure_runtime_dependencies()
    rapidocr_module = importlib.import_module("rapidocr_onnxruntime")
    return rapidocr_module.RapidOCR()


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"只支持 http/https 图片 URL: {url}")


def _infer_suffix(url: str, content_type: str | None) -> str:
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed

    path_suffix = Path(urlparse(url).path).suffix
    return path_suffix or ".img"


def _is_certificate_verify_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return True
    if isinstance(exc, ssl.SSLError):
        return "CERTIFICATE_VERIFY_FAILED" in str(exc)
    if isinstance(exc, URLError) and exc.reason is not None:
        return _is_certificate_verify_error(exc.reason)
    return False


def _open_url_with_ssl_fallback(request: Request) -> tuple[object, bool]:
    try:
        return urlopen(request, timeout=30), False
    except URLError as exc:
        if not _is_certificate_verify_error(exc):
            raise

    # 某些公网 OSS 地址会返回带自签链的证书。
    # 这里先尝试标准校验，失败后仅对“证书校验失败”场景回退一次。
    insecure_context = ssl._create_unverified_context()
    return urlopen(request, timeout=30, context=insecure_context), True


def _download_image(url: str, index: int, temp_dir: str) -> tuple[Path, bool]:
    _validate_url(url)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    response, used_insecure_ssl = _open_url_with_ssl_fallback(request)
    with response:
        content_type = response.headers.get("Content-Type")
        if content_type and not content_type.startswith("image/"):
            raise ValueError(f"URL 返回的不是图片内容: {content_type}")

        payload = response.read()
        target = Path(temp_dir) / f"image_{index}{_infer_suffix(url, content_type)}"
        target.write_bytes(payload)
        return target, used_insecure_ssl


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise ValueError("至少需要传入一个图片 URL")

    ocr = _build_ocr_engine()
    items: list[dict[str, str | int]] = []

    with tempfile.TemporaryDirectory(prefix="enterprise-agent-ocr-", dir="/tmp") as temp_dir:
        for index, url in enumerate(argv[1:], start=1):
            image_path, used_insecure_ssl = _download_image(url, index, temp_dir)
            result, _ = ocr(str(image_path))
            texts = [line[1] for line in result] if result else []
            item = {
                "image_index": index,
                "url": url,
                "file_name": image_path.name,
                "raw_text": "\n".join(texts),
            }
            if used_insecure_ssl:
                item["download_warning"] = "SSL 证书校验失败，已回退到不校验证书下载"
            items.append(item)

    print(json.dumps({"items": items}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as exc:
        print(f"OCR 脚本执行失败: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

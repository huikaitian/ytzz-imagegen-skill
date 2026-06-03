#!/usr/bin/env python3
"""Generate and edit images through the YTZZ SubRouter GPT Image gateway."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import http.client
import json
import mimetypes
import os
import re
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://ytzz.subrouter.ai/v1"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_RATIO = "16:9"
DEFAULT_QUALITY = "high"
DEFAULT_RESPONSE_FORMAT = "url"
DEFAULT_DOWNLOAD_RETRIES = 4
IMAGE2_MAX_EDGE = 3840
IMAGE2_MIN_PIXELS = 655_360
IMAGE2_MAX_PIXELS = 8_294_400
EDIT_UPLOAD_MAX_EDGE = 1536
EDIT_UPLOAD_MAX_BYTES = 2_500_000
FOUR_K_RATIO_PRESETS = {
    "1:1": "2880x2880",
    "5:4": "3200x2560",
    "4:5": "2560x3200",
    "4:3": "3264x2448",
    "3:4": "2448x3264",
    "3:2": "3504x2336",
    "2:3": "2336x3504",
    "16:10": "3584x2240",
    "10:16": "2240x3584",
    "16:9": "3840x2160",
    "9:16": "2160x3840",
    "21:9": "3696x1584",
    "9:21": "1584x3696",
    "2:1": "3840x1920",
    "1:2": "1920x3840",
    "3:1": "3840x1280",
    "1:3": "1280x3840",
}


class GatewayError(RuntimeError):
    def __init__(self, url: str, status: int | None, detail: Any):
        self.url = url
        self.status = status
        self.detail = detail
        super().__init__(f"HTTP {status} at {safe_url_for_log(url)}: {detail}")


def env_value(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
        value = windows_env_value(name)
        if value:
            return value
    return None


def windows_env_value(name: str) -> str | None:
    if os.name != "nt":
        return None
    try:
        import winreg

        locations = (
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        )
        for root, subkey in locations:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    value, _ = winreg.QueryValueEx(key, name)
                    if value:
                        return str(value)
            except OSError:
                continue
    except Exception:
        return None
    return None


def normalize_base_url(base_url: str | None) -> str:
    value = DEFAULT_BASE_URL.rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if "/v1" in parsed.path:
        prefix = parsed.path.split("/v1", 1)[0]
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, f"{prefix}/v1", "", "", "")).rstrip("/")
    return f"{value}/v1"


def endpoint(base_url: str, path: str, async_mode: bool = False) -> str:
    base = normalize_base_url(base_url)
    if base.endswith("/v1") and path.startswith("/v1/"):
        url = base + path[3:]
    else:
        url = base + path
    if async_mode:
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}async=true"
    return url


def safe_url_for_log(url: str | None) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    safe_query = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        if "key" in key.lower() or "token" in key.lower():
            value = "***"
        safe_query.append((key, value))
    return urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        urllib.parse.urlencode(safe_query),
        "",
    ))


def ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if os.environ.get("YTZZ_IMAGEGEN_INSECURE_SSL") == "1":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def api_key_from_args(args: argparse.Namespace) -> str:
    key = getattr(args, "api_key", None) or env_value("YTZZ_SUBROUTER_API_KEY", "SUBROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing API key. Register or sign in at https://ytzz.subrouter.ai, create an API key, "
            "then provide it to the agent for this run or set YTZZ_SUBROUTER_API_KEY locally."
        )
    return key


def parse_error_body(exc: urllib.error.HTTPError) -> Any:
    raw = exc.read().decode("utf-8", errors="replace")
    if not raw:
        return ""
    try:
        return json.loads(raw)
    except Exception:
        return raw


def request_json(
    url: str,
    method: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 900,
) -> tuple[int, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "ytzz-imagegen/1.0",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise GatewayError(url, exc.code, parse_error_body(exc)) from exc
    except urllib.error.URLError as exc:
        raise GatewayError(url, None, str(exc.reason)) from exc


def multipart_body(fields: dict[str, Any], files: list[dict[str, Any]]) -> tuple[bytes, str]:
    boundary = f"----ytzzimagegen{int(time.time() * 1000)}"
    chunks: list[bytes] = []

    def add_line(value: bytes | str = b"") -> None:
        if isinstance(value, str):
            value = value.encode("utf-8")
        chunks.append(value + b"\r\n")

    for name, value in fields.items():
        if value is None or value == "":
            continue
        add_line(f"--{boundary}")
        add_line(f'Content-Disposition: form-data; name="{name}"')
        add_line()
        add_line(str(value))

    for item in files:
        name = item.get("field") or "image[]"
        path = Path(item["path"])
        filename = item.get("filename") or path.name
        content_type = item.get("content_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        add_line(f"--{boundary}")
        add_line(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"')
        add_line(f"Content-Type: {content_type}")
        add_line()
        chunks.append(path.read_bytes() + b"\r\n")

    add_line(f"--{boundary}--")
    return b"".join(chunks), boundary


def request_multipart(
    url: str,
    fields: dict[str, Any],
    files: list[dict[str, Any]],
    api_key: str,
    timeout: int = 900,
) -> tuple[int, Any]:
    body, boundary = multipart_body(fields, files)
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
        "User-Agent": "ytzz-imagegen/1.0",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise GatewayError(url, exc.code, parse_error_body(exc)) from exc
    except urllib.error.URLError as exc:
        raise GatewayError(url, None, str(exc.reason)) from exc


def normalize_image_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(json.dumps(payload["error"], ensure_ascii=False))
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return payload["data"]
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        inner = payload["data"]
        if isinstance(inner.get("data"), list):
            return inner["data"]
        for key in ("result", "output"):
            if isinstance(inner.get(key), dict):
                return normalize_image_items(inner[key])
    if isinstance(payload, dict):
        for key in ("result", "output"):
            if isinstance(payload.get(key), dict):
                return normalize_image_items(payload[key])
        for key in ("url", "image_url"):
            if payload.get(key):
                return [{"url": payload[key]}]
        for key in ("b64_json", "image", "base64"):
            if payload.get(key):
                return [{"b64_json": payload[key]}]
        for key in ("task_id", "id"):
            if payload.get(key) and "task" in key:
                raise RuntimeError(f"Gateway returned async task {payload[key]} without image data.")
    raise RuntimeError("Image response did not contain image data.")


def extract_task_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in ("task_id", "taskId"):
        if payload.get(key):
            return str(payload[key])
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("task_id", "taskId", "id"):
            if data.get(key):
                return str(data[key])
    if payload.get("id") and not payload.get("data"):
        return str(payload["id"])
    return None


def extract_task_status(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    candidates = [payload]
    if isinstance(payload.get("data"), dict):
        candidates.append(payload["data"])
    for item in candidates:
        for key in ("status", "state"):
            if item.get(key):
                return str(item[key]).lower()
    return ""


def poll_task_result(base_url: str, api_key: str, initial_payload: Any, timeout: int) -> Any:
    task_id = extract_task_id(initial_payload)
    if not task_id:
        return initial_payload
    deadline = time.time() + timeout
    task_url = endpoint(base_url, f"/v1/images/tasks/{urllib.parse.quote(task_id)}")
    last_payload = initial_payload
    while time.time() < deadline:
        status, payload = request_json(task_url, "GET", api_key, timeout=min(60, timeout))
        last_payload = payload
        try:
            normalize_image_items(payload)
            return payload
        except Exception:
            pass
        state = extract_task_status(payload)
        if state in {"failed", "failure", "error", "cancelled", "canceled"}:
            raise RuntimeError(f"Async image task failed: {json.dumps(payload, ensure_ascii=False)}")
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for async image task {task_id}: {last_payload}")


def read_prompt(args: argparse.Namespace, job: dict[str, Any] | None = None) -> str:
    job = job or {}
    prompt = job.get("prompt") or getattr(args, "prompt", None)
    prompt_file = job.get("prompt_file") or getattr(args, "prompt_file", None)
    if prompt and prompt_file:
        raise ValueError("Use either prompt or prompt_file, not both.")
    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")
    if prompt:
        return str(prompt)
    raise ValueError("Missing prompt.")


def validate_size(size: str | None, model: str) -> None:
    if model != "gpt-image-2" or not size or size == "auto":
        return
    if not isinstance(size, str) or "x" not in size.lower():
        raise ValueError("Image size must be auto or WIDTHxHEIGHT, for example 1024x1024.")
    try:
        width, height = [int(part) for part in size.lower().split("x", 1)]
    except ValueError as exc:
        raise ValueError("Image size must use numeric WIDTHxHEIGHT format.") from exc
    pixels = width * height
    if width <= 0 or height <= 0:
        raise ValueError("Image size edges must be positive.")
    if width % 16 or height % 16:
        raise ValueError("gpt-image-2 custom size edges must be multiples of 16.")
    if max(width, height) > IMAGE2_MAX_EDGE:
        raise ValueError("gpt-image-2 max edge must be <= 3840.")
    if max(width, height) / min(width, height) > 3:
        raise ValueError("gpt-image-2 long-to-short ratio must be <= 3:1.")
    if pixels < IMAGE2_MIN_PIXELS or pixels > IMAGE2_MAX_PIXELS:
        raise ValueError("gpt-image-2 total pixels must be between 655360 and 8294400.")


def payload_from_args(args: argparse.Namespace, prompt: str, job: dict[str, Any] | None = None) -> dict[str, Any]:
    job = job or {}
    model = job.get("model") or getattr(args, "model", DEFAULT_MODEL) or DEFAULT_MODEL
    ratio = str(job.get("ratio") or getattr(args, "ratio", DEFAULT_RATIO) or DEFAULT_RATIO)
    size = job.get("size") or getattr(args, "size", None) or FOUR_K_RATIO_PRESETS.get(ratio)
    if not size:
        raise ValueError(f"Unsupported ratio: {ratio}. Use one of: {', '.join(FOUR_K_RATIO_PRESETS)}")
    background = job.get("background") or getattr(args, "background", None)
    if model == "gpt-image-2" and background == "transparent":
        raise ValueError("gpt-image-2 does not support background=transparent. Use chroma-key generation plus local removal.")
    validate_size(size, model)

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": int(job.get("n") or getattr(args, "n", 1) or 1),
        "quality": DEFAULT_QUALITY,
    }
    for key in ("output_format", "response_format", "moderation", "background"):
        value = job.get(key)
        if value is None:
            value = getattr(args, key, None)
        if key == "response_format" and value in (None, ""):
            value = DEFAULT_RESPONSE_FORMAT
        if value not in (None, "", "auto"):
            payload[key] = value
    return payload


def suffix_for_output(args: argparse.Namespace, job: dict[str, Any] | None = None) -> str:
    job = job or {}
    fmt = job.get("output_format") or getattr(args, "output_format", None) or "png"
    fmt = str(fmt).lower().lstrip(".")
    if fmt not in {"png", "jpg", "jpeg", "webp"}:
        fmt = "png"
    if fmt == "jpeg":
        fmt = "jpg"
    return f".{fmt}"


def default_out_path(args: argparse.Namespace, suffix: str) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path.cwd() / "output" / "imagegen" / f"ytzz-gpt-image-2-{stamp}{suffix}"


def output_paths(
    args: argparse.Namespace,
    count: int,
    suffix: str,
    job: dict[str, Any] | None = None,
    index: int | None = None,
) -> list[Path]:
    job = job or {}
    out = job.get("out") or getattr(args, "out", None)
    out_dir = job.get("out_dir") or getattr(args, "out_dir", None)

    if out_dir:
        out_dir_path = Path(out_dir)
        if out:
            base = Path(out)
            if base.is_absolute():
                first = base
            else:
                first = out_dir_path / base
        else:
            stem = f"image_{index}" if index is not None else "image"
            first = out_dir_path / f"{stem}{suffix}"
    elif out:
        first = Path(out)
    else:
        first = default_out_path(args, suffix)

    if count == 1:
        return [first]
    stem = first.stem
    return [first.with_name(f"{stem}_{i + 1}{first.suffix or suffix}") for i in range(count)]


def ensure_writable(paths: list[Path], force: bool) -> None:
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not force:
            raise FileExistsError(f"Output already exists: {path}. Use --force to overwrite.")


def b64_to_bytes(value: str) -> bytes:
    text = value.strip()
    if "," in text and text.startswith("data:"):
        text = text.split(",", 1)[1]
    return base64.b64decode(text)


def download_bytes(url: str, timeout: int, retries: int = DEFAULT_DOWNLOAD_RETRIES) -> bytes:
    attempts = max(1, retries)
    retryable_http = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, headers={"User-Agent": "ytzz-imagegen/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
                data = resp.read()
                content_length = resp.headers.get("Content-Length")
                if content_length:
                    expected = int(content_length)
                    if len(data) != expected:
                        raise http.client.IncompleteRead(data, expected - len(data))
                return data
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in retryable_http or attempt == attempts:
                raise
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == attempts:
                raise
        time.sleep(min(2**attempt, 30))
    raise RuntimeError(f"Failed to download image after {attempts} attempts: {last_error}")


def write_image_items(
    items: list[dict[str, Any]],
    paths: list[Path],
    timeout: int,
    force: bool,
    download_retries: int = DEFAULT_DOWNLOAD_RETRIES,
) -> list[str]:
    ensure_writable(paths, force)
    written = []
    for item, path in zip(items, paths):
        if item.get("b64_json"):
            data = b64_to_bytes(str(item["b64_json"]))
        elif item.get("url"):
            data = download_bytes(str(item["url"]), timeout, download_retries)
        else:
            raise RuntimeError("Image item did not contain b64_json or url.")
        path.write_bytes(data)
        written.append(str(path.resolve()))
    return written


def request_summary(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint": safe_url_for_log(url),
        "model": payload.get("model"),
        "size": payload.get("size"),
        "quality": payload.get("quality"),
        "n": payload.get("n"),
        "output_format": payload.get("output_format"),
        "response_format": payload.get("response_format"),
    }


def print_result(result: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for path in result.get("files", []):
            print(path)


def command_models(args: argparse.Namespace) -> int:
    base_url = normalize_base_url(DEFAULT_BASE_URL)
    api_key = api_key_from_args(args)
    url = endpoint(base_url, "/v1/models")
    status, result = request_json(url, "GET", api_key, timeout=args.timeout)
    models = []
    if isinstance(result, dict):
        for item in result.get("data") or []:
            model_id = item.get("id") if isinstance(item, dict) else None
            if model_id:
                models.append(model_id)
    payload = {
        "ok": True,
        "status": status,
        "base_url": base_url,
        "count": len(models),
        "has_gpt_image_2": "gpt-image-2" in models,
        "models": sorted(set(models)),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for model in payload["models"]:
            print(model)
    return 0


def command_generate(args: argparse.Namespace) -> int:
    prompt = read_prompt(args)
    payload = payload_from_args(args, prompt)
    api_key = api_key_from_args(args)
    base_url = normalize_base_url(DEFAULT_BASE_URL)
    url = endpoint(base_url, "/v1/images/generations", async_mode=args.async_mode)
    status, result = request_json(url, "POST", api_key, payload, timeout=args.timeout)
    if args.async_mode:
        result = poll_task_result(base_url, api_key, result, args.timeout)
    items = normalize_image_items(result)
    suffix = suffix_for_output(args)
    paths = output_paths(args, len(items), suffix)
    files = write_image_items(items, paths, args.timeout, args.force, args.download_retries)
    print_result({
        "ok": True,
        "status": status,
        "base_url": base_url,
        "request": request_summary(url, payload),
        "files": files,
    }, args.json)
    return 0


def prepare_image_for_upload(path: Path, tmpdir: Path) -> Path:
    if path.stat().st_size <= EDIT_UPLOAD_MAX_BYTES:
        try:
            from PIL import Image

            with Image.open(path) as image:
                if max(image.width, image.height) <= EDIT_UPLOAD_MAX_EDGE:
                    return path
        except Exception:
            return path
    try:
        from PIL import Image, ImageOps
    except Exception:
        return path

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        working = image.copy()
        if max(working.width, working.height) > EDIT_UPLOAD_MAX_EDGE:
            resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            working.thumbnail((EDIT_UPLOAD_MAX_EDGE, EDIT_UPLOAD_MAX_EDGE), resampling)
        has_alpha = "A" in working.getbands() or "transparency" in getattr(working, "info", {})
        if has_alpha:
            if working.mode not in {"RGBA", "LA"}:
                working = working.convert("RGBA")
            out = tmpdir / f"{path.stem}_upload.png"
            working.save(out, format="PNG", optimize=True)
        else:
            if working.mode != "RGB":
                working = working.convert("RGB")
            out = tmpdir / f"{path.stem}_upload.jpg"
            working.save(out, format="JPEG", quality=92, optimize=True)
        return out


def image_files_from_args(args: argparse.Namespace, tmpdir: Path) -> list[dict[str, Any]]:
    files = []
    for image in args.image or []:
        path = Path(image).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        files.append({"field": "image[]", "path": prepare_image_for_upload(path, tmpdir)})
    if args.mask:
        path = Path(args.mask).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Mask not found: {path}")
        files.append({"field": "mask", "path": path})
    if not files:
        raise ValueError("Pass at least one --image for edit mode.")
    return files


def command_edit(args: argparse.Namespace) -> int:
    prompt = read_prompt(args)
    payload = payload_from_args(args, prompt)
    if payload.get("size") == "auto":
        payload.pop("size", None)
    api_key = api_key_from_args(args)
    base_url = normalize_base_url(DEFAULT_BASE_URL)
    with tempfile.TemporaryDirectory(prefix="ytzz-imagegen-edit-") as tmp:
        files = image_files_from_args(args, Path(tmp))
        url = endpoint(base_url, "/v1/images/edits", async_mode=args.async_mode)
        status, result = request_multipart(url, payload, files, api_key, timeout=args.timeout)
    if args.async_mode:
        result = poll_task_result(base_url, api_key, result, args.timeout)
    items = normalize_image_items(result)
    suffix = suffix_for_output(args)
    paths = output_paths(args, len(items), suffix)
    written = write_image_items(items, paths, args.timeout, args.force, args.download_retries)
    print_result({
        "ok": True,
        "status": status,
        "base_url": base_url,
        "request": request_summary(url, payload),
        "files": written,
    }, args.json)
    return 0


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    jobs = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            job = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at line {line_no}: {exc}") from exc
        if not isinstance(job, dict):
            raise ValueError(f"JSONL line {line_no} must be an object.")
        jobs.append(job)
    return jobs


def run_batch_job(args: argparse.Namespace, job: dict[str, Any], index: int, base_url: str, api_key: str) -> dict[str, Any]:
    prompt = read_prompt(args, job)
    payload = payload_from_args(args, prompt, job)
    url = endpoint(base_url, "/v1/images/generations", async_mode=bool(job.get("async") or args.async_mode))
    status, result = request_json(url, "POST", api_key, payload, timeout=args.timeout)
    items = normalize_image_items(result)
    suffix = suffix_for_output(args, job)
    job = dict(job)
    job["out_dir"] = str(args.out_dir)
    paths = output_paths(args, len(items), suffix, job, index=index)
    files = write_image_items(items, paths, args.timeout, args.force, args.download_retries)
    return {
        "ok": True,
        "status": status,
        "index": index,
        "request": request_summary(url, payload),
        "files": files,
    }


def command_generate_batch(args: argparse.Namespace) -> int:
    jobs = load_jsonl(Path(args.input))
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    api_key = api_key_from_args(args)
    base_url = normalize_base_url(DEFAULT_BASE_URL)
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        future_map = {
            executor.submit(run_batch_job, args, job, index, base_url, api_key): index
            for index, job in enumerate(jobs, 1)
        }
        for future in concurrent.futures.as_completed(future_map):
            index = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append({"ok": False, "index": index, "error": str(exc)})
                if args.fail_fast:
                    break

    payload = {
        "ok": not errors,
        "base_url": base_url,
        "jobs": len(jobs),
        "results": sorted(results, key=lambda item: item["index"]),
        "errors": sorted(errors, key=lambda item: item["index"]),
    }
    if args.json or errors:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in payload["results"]:
            for path in result["files"]:
                print(path)
    return 1 if errors else 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--api-key", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--json", action="store_true")


def add_image_args(parser: argparse.ArgumentParser, include_out_dir: bool = True) -> None:
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ratio", choices=list(FOUR_K_RATIO_PRESETS), default=DEFAULT_RATIO)
    parser.add_argument("--size")
    parser.add_argument("--quality", choices=["high"], default=DEFAULT_QUALITY)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--output-format", choices=["png", "jpeg", "webp"])
    parser.add_argument("--response-format")
    parser.add_argument("--download-retries", type=int, default=DEFAULT_DOWNLOAD_RETRIES)
    parser.add_argument("--moderation")
    parser.add_argument("--background")
    parser.add_argument("--out")
    if include_out_dir:
        parser.add_argument("--out-dir")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--async", dest="async_mode", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate images through the YTZZ SubRouter GPT Image gateway.")
    sub = parser.add_subparsers(dest="command", required=True)

    models = sub.add_parser("models", help="List available models.")
    add_common_args(models)
    models.set_defaults(func=command_models)

    generate = sub.add_parser("generate", help="Generate images from a prompt.")
    add_common_args(generate)
    add_image_args(generate)
    generate.set_defaults(func=command_generate)

    edit = sub.add_parser("edit", help="Edit or reference local images.")
    add_common_args(edit)
    add_image_args(edit)
    edit.add_argument("--image", action="append")
    edit.add_argument("--mask")
    edit.set_defaults(func=command_edit)

    batch = sub.add_parser("generate-batch", help="Generate many images from a JSONL file.")
    add_common_args(batch)
    add_image_args(batch, include_out_dir=False)
    batch.add_argument("--input", required=True)
    batch.add_argument("--out-dir", required=True)
    batch.add_argument("--concurrency", type=int, default=3)
    batch.add_argument("--fail-fast", action="store_true")
    batch.set_defaults(func=command_generate_batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        else:
            print(f"ytzz-imagegen error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

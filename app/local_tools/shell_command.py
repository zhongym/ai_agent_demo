from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
VENV_PIP = PROJECT_ROOT / ".venv" / "bin" / "pip"
DEFAULT_TIMEOUT_SECONDS = 120
MIN_TIMEOUT_SECONDS = 5
MAX_TIMEOUT_SECONDS = 600


class RunShellCommandInput(BaseModel):
    """bash 命令执行工具的入参。"""

    commands: list[str] = Field(
        min_length=1,
        description="按顺序执行的命令列表。每条命令必须命中白名单前缀。",
    )
    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        ge=MIN_TIMEOUT_SECONDS,
        le=MAX_TIMEOUT_SECONDS,
        description="单条命令超时时间，单位秒。",
    )
    working_directory: str | None = Field(
        default=None,
        description="命令执行目录。为空时默认使用 `/tmp` 临时目录；仅允许项目目录或 `/tmp` 下的路径。",
    )


def _resolve_executable(executable: str) -> Path | str:
    if executable == ".venv/bin/python":
        return VENV_PYTHON
    if executable == ".venv/bin/pip":
        return VENV_PIP
    return executable


def _validate_and_tokenize(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"命令解析失败: {exc}") from exc

    if not tokens:
        raise ValueError("命令不能为空")

    executable = tokens[0]
    if executable not in {"curl", ".venv/bin/python", ".venv/bin/pip"}:
        raise ValueError(f"不允许的命令前缀: {executable}")

    if executable == ".venv/bin/pip" and (len(tokens) < 2 or tokens[1] != "install"):
        raise ValueError("当前只允许 `.venv/bin/pip install ...`")

    tokens[0] = str(_resolve_executable(executable))
    return tokens


def _build_result_item(
    *,
    command: str,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
) -> dict[str, Any]:
    return {
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }


def _resolve_working_directory(working_directory: str | None, temp_dir: str) -> Path:
    if working_directory is None:
        return Path(temp_dir)

    candidate = Path(working_directory)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    allowed_roots = [PROJECT_ROOT, Path("/tmp")]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise ValueError("working_directory 只允许项目目录或 /tmp 下的路径")
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"working_directory 不存在或不是目录: {resolved}")
    return resolved


@tool(
    "run_shell_command",
    description=(
        "在受限白名单内顺序执行本地命令。"
        "当前只允许 `curl`、`.venv/bin/pip install ...`、`.venv/bin/python ...`。"
        "默认在临时目录 `/tmp` 下执行，也可以显式指定项目目录或 `/tmp` 目录作为 working_directory。"
        "返回每条命令的 stdout、stderr、exit_code。"
    ),
    args_schema=RunShellCommandInput,
    parse_docstring=False,
    extras={"local_tool": {"kind": "local", "tool_result": "identity"}},
)
async def run_shell_command(
    commands: list[str],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    working_directory: str | None = None,
) -> dict[str, Any]:
    """受限命令执行工具。

    它的目标不是提供完全自由的 shell，而是给 skill 一个可审计、可测试的命令执行入口。
    所有命令都在临时目录中运行，避免把 OCR 中间文件写到仓库目录里。
    """

    environment = os.environ.copy()
    items: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="enterprise-agent-shell-", dir="/tmp") as temp_dir:
        try:
            current_working_directory = _resolve_working_directory(working_directory, temp_dir)
        except ValueError as exc:
            items.append(
                _build_result_item(
                    command="__working_directory__",
                    exit_code=-1,
                    stderr=str(exc),
                )
            )
            return {"success": False, "items": items}

        for command in commands:
            try:
                tokens = _validate_and_tokenize(command)
            except ValueError as exc:
                items.append(
                    _build_result_item(
                        command=command,
                        exit_code=-1,
                        stderr=str(exc),
                    )
                )
                return {"success": False, "items": items}

            try:
                completed = subprocess.run(
                    tokens,
                    cwd=current_working_directory,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                items.append(
                    _build_result_item(
                        command=command,
                        exit_code=-1,
                        stdout=exc.stdout or "",
                        stderr=f"命令执行超时: {timeout_seconds} 秒",
                    )
                )
                return {"success": False, "items": items}
            except OSError as exc:
                items.append(
                    _build_result_item(
                        command=command,
                        exit_code=-1,
                        stderr=f"命令执行失败: {exc}",
                    )
                )
                return {"success": False, "items": items}

            item = _build_result_item(
                command=command,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            items.append(item)
            if completed.returncode != 0:
                return {"success": False, "items": items}

    return {"success": True, "items": items}

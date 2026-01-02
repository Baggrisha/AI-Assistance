from __future__ import annotations

import os
import os
import subprocess
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel


def read_env(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}

    data: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def write_env(path: str | Path, updates: dict[str, str]) -> None:
    p = Path(path)
    lines = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    index: dict[str, int] = {}

    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _ = s.split("=", 1)
        index[k.strip()] = i

    for k, v in updates.items():
        new_line = f'{k}="{v}"'
        if k in index:
            lines[index[k]] = new_line
        else:
            lines.append(new_line)

    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def get_ollama_models() -> list[str]:
    """
    Возвращает список имён моделей из `ollama list` (первый столбец).
    """
    try:
        p = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return []

    out: list[str] = []
    lines = p.stdout.splitlines()

    # Пропускаем заголовок (NAME / ID / SIZE / MODIFIED)
    for line in lines[1:]:
        s = line.strip()
        if not s:
            continue
        out.append(s.split()[0])

    # unique preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for m in out:
        if m not in seen:
            seen.add(m)
            uniq.append(m)
    return uniq


def _resolve_default_env_path() -> Optional[Path]:
    """
    Пытаемся найти .env:
    1) рядом с проектом (на уровень выше папки gui)
    2) рядом с этим файлом
    3) текущая рабочая директория
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parent.parent / ".env",
        here.parent / ".env",
        Path.cwd() / ".env",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# Загружаем .env один раз при импорте модуля (если найден).
_env_path = _resolve_default_env_path()
if _env_path is not None:
    load_dotenv(dotenv_path=_env_path, override=False)
else:
    # fallback: dotenv сам попробует найти .env по стандартным правилам
    load_dotenv(override=False)


class Settings(BaseModel):
    main_model: str = ""
    mini_model: str = ""
    hf_token: str | None = None


def load_settings() -> Settings:
    return Settings(
        main_model=os.getenv("MAIN_MODEL", ""),
        mini_model=os.getenv("MINI_MODEL", ""),
        hf_token=os.getenv("HF_TOKEN"),
    )

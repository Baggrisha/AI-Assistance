import json
import datetime
import re
import subprocess
from typing import Union, Literal
from zoneinfo import ZoneInfo

import Foundation

RU_DOW = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def _fmt_dt(ts: int, tz: ZoneInfo) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(ts, tz=tz)

def normalize_execution_results(execution_results, tz_name="Europe/Moscow"):
    tz = ZoneInfo(tz_name)
    out = []

    for item in execution_results:
        action = item.get("action")
        args = item.get("args", {})
        success = item.get("success", True)
        result = item.get("result")

        new_item = {"action": action, "args": args, "success": success, "result": result}

        if action == "get_events" and isinstance(result, list):
            norm_events = []
            for e in result:
                sdt = _fmt_dt(e["start_epoch"], tz)
                edt = _fmt_dt(e["end_epoch"], tz)

                e2 = dict(e)
                e2["start"] = sdt.strftime("%d.%m.%Y %H:%M")
                e2["end"] = edt.strftime("%d.%m.%Y %H:%M")
                e2["date"] = sdt.strftime("%d.%m.%Y")
                e2["dow"] = RU_DOW[sdt.weekday()]  # Пн..Вс
                norm_events.append(e2)

            new_item["result"] = norm_events

        out.append(new_item)

    return out

def _resolve_weather_days(when: str | int | None) -> int:
    if when is None:
        return 0

    if isinstance(when, (int, float)) and not isinstance(when, bool):
        return int(when)

    w = str(when).lower().strip()
    if not w or w in ("current", "now", "сейчас", "today", "сегодня", "0"):
        return 0
    if w in ("tomorrow", "завтра", "1"):
        return 1
    if w in ("послезавтра", "day after tomorrow", "2"):
        return 2
    if "недел" in w or "week" in w:
        return 7
    if w.isdigit():
        return int(w)

    digit_match = re.search(r"(\d+)", w)
    if digit_match:
        return int(digit_match.group(1))

    word_numbers = [
        ("четырнадц", 14),
        ("тринадц", 13),
        ("двенадц", 12),
        ("одиннадц", 11),
        ("десят", 10),
        ("девят", 9),
        ("восем", 8),
        ("сем", 7),
        ("шест", 6),
        ("пят", 5),
        ("четыр", 4),
        ("три", 3),
        ("две", 2),
        ("два", 2),
        ("одну", 1),
        ("один", 1),
    ]
    for key, val in word_numbers:
        if key in w:
            return val

    return 0

Section = Literal["all", "cpu", "memory", "disk", "battery", "wifi", "gpu", "hardware"]


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()


def _osascript(script: str) -> str:
    return _run(["osascript", "-e", script])


def _do_shell(cmd: str) -> str:
    cmd_escaped = cmd.replace("\\", "\\\\").replace('"', '\\"')
    return _osascript(f'do shell script "{cmd_escaped}"')


def _safe_int(x: str) -> int | None:
    try:
        return int(x)
    except Exception:
        return None


def _safe_float(x: str) -> float | None:
    try:
        return float(x)
    except Exception:
        return None

def _nsdate_from_dt(dt: datetime.datetime) -> Foundation.NSDate:
    # NSDate живёт в секундах от Unix epoch
    return Foundation.NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())

def parse_dt(value: Union[str, datetime.date, datetime.datetime], *, start: bool):
    if isinstance(value, datetime.datetime):
        return value

    if isinstance(value, datetime.date):
        return datetime.datetime.combine(
            value,
            datetime.time.min if start else datetime.time.max
        )

    if isinstance(value, str):
        value = value.strip()

        try:
            return datetime.datetime.strptime(value, "%d.%m.%Y %H:%M")
        except ValueError:
            pass

        try:
            d = datetime.datetime.strptime(value, "%d.%m.%Y").date()
            return datetime.datetime.combine(
                d,
                datetime.time.min if start else datetime.time.max
            )
        except ValueError:
            pass

        raise ValueError(f"Неверный формат даты/времени: {value}")

    raise TypeError("Дата должна быть str | date | datetime")

def _normalize_allowlist(calendars_allowlist):
    """
    Приводит calendars_allowlist к одному виду:
    - None / "None" / "" -> None (не фильтровать)
    - "Работа" -> ["Работа"]
    - ["Работа","Учеба"] -> ["Работа","Учеба"]
    - "Работа, Учеба" -> ["Работа","Учеба"]  (на всякий случай)
    """
    if calendars_allowlist is None:
        return None

    if isinstance(calendars_allowlist, str):
        s = calendars_allowlist.strip()
        if s.lower() == "none" or s == "":
            return None
        # опционально поддержим "Работа, Учеба"
        if "," in s:
            return [x.strip() for x in s.split(",") if x.strip()]
        return [s]

    # iterable (list/tuple/set)
    try:
        lst = [str(x).strip() for x in calendars_allowlist if str(x).strip()]
        return lst or None
    except TypeError:
        # если прилетело что-то странное
        return [str(calendars_allowlist).strip()]

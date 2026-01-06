import base64
import json
import re
import shutil
import subprocess
import time
from typing import Any, Literal

import requests


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



def _cpu_state() -> dict[str, Any]:
    line = _do_shell(r"top -l 1 -n 0 | awk -F': ' '/^CPU usage/ {print $2}'")
    m_user = re.search(r"([\d.]+)%\s*user", line)
    m_sys = re.search(r"([\d.]+)%\s*sys", line)
    m_idle = re.search(r"([\d.]+)%\s*idle", line)
    user = _safe_float(m_user.group(1)) if m_user else None
    sys = _safe_float(m_sys.group(1)) if m_sys else None
    idle = _safe_float(m_idle.group(1)) if m_idle else None
    busy = (100.0 - idle) if idle is not None else None
    return {
        "raw": line,
        "user_pct": user,
        "sys_pct": sys,
        "idle_pct": idle,
        "busy_pct": busy,
    }


def _memory_state() -> dict[str, Any]:
    vm = _do_shell("vm_stat")
    page_size_match = re.search(r"page size of (\d+) bytes", vm)
    page_size = _safe_int(page_size_match.group(1)) if page_size_match else 4096

    def pages(name: str) -> int | None:
        m = re.search(rf"^{re.escape(name)}:\s+(\d+)\.", vm, re.MULTILINE)
        return _safe_int(m.group(1)) if m else None

    free = pages("Pages free")
    active = pages("Pages active")
    inactive = pages("Pages inactive")
    speculative = pages("Pages speculative")
    wired = pages("Pages wired down")
    compressed = pages("Pages occupied by compressor")

    freeish_pages = (free or 0) + (speculative or 0)
    usedish_pages = (active or 0) + (inactive or 0) + (wired or 0) + (compressed or 0)

    return {
        "page_size_bytes": page_size,
        "pages": {
            "free": free,
            "active": active,
            "inactive": inactive,
            "speculative": speculative,
            "wired": wired,
            "compressed": compressed,
        },
        "approx": {
            "free_bytes": freeish_pages * page_size if page_size else None,
            "used_bytes": usedish_pages * page_size if page_size else None,
        },
        "raw": vm,
    }


def _disk_state() -> dict[str, Any]:
    line = _do_shell("df -H / | tail -1")
    parts = line.split()
    out: dict[str, Any] = {"raw": line}
    if len(parts) >= 6:
        out.update({
            "filesystem": parts[0],
            "size": parts[1],
            "used": parts[2],
            "avail": parts[3],
            "capacity": parts[4],
            "mounted_on": parts[-1],
        })
    return out


def _battery_state() -> dict[str, Any]:
    raw = _do_shell("pmset -g batt")
    pct_match = re.search(r"(\d+)%", raw)
    pct = _safe_int(pct_match.group(1)) if pct_match else None
    power_source = _do_shell(r"pmset -g ps | head -n 1 | sed 's/.*\"\(.*\)\".*/\1/'")
    return {
        "percent": pct,
        "power_source": power_source,
        "raw": raw,
    }


def _wifi_state() -> dict[str, Any]:
    iface = _do_shell(r"route get default 2>/dev/null | awk '/interface:/{print $2}' | head -n 1")
    ssid = _do_shell(r"networksetup -getairportnetwork en0 2>/dev/null | sed 's/Current Wi-Fi Network: //'")
    airport = _do_shell(r"/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I 2>/dev/null")

    def _grep_num(key: str) -> int | None:
        m = re.search(rf"^{key}:\s*(-?\d+)", airport, re.MULTILINE)
        return _safe_int(m.group(1)) if m else None

    def _grep_float(key: str) -> float | None:
        m = re.search(rf"^{key}:\s*([\d.]+)", airport, re.MULTILINE)
        return _safe_float(m.group(1)) if m else None

    state_match = re.search(r"^state:\s*(\w+)", airport, re.MULTILINE)
    state = state_match.group(1) if state_match else None

    return {
        "default_interface": iface or None,
        "ssid": ssid if ssid and "You are not" not in ssid else None,
        "state": state,
        "rssi_dbm": _grep_num("agrCtlRSSI"),
        "noise_dbm": _grep_num("agrCtlNoise"),
        "tx_rate_mbps": _grep_float("lastTxRate"),
        "raw_airport": airport,
    }


def _gpu_state() -> dict[str, Any]:
    sp = _do_shell("system_profiler SPDisplaysDataType 2>/dev/null")
    chipset_models = re.findall(r"Chipset Model:\s*(.+)", sp)
    vram = re.findall(r"VRAM.*?:\s*(.+)", sp)
    return {
        "chipset_models": chipset_models,
        "vram": vram,
        "raw": sp,
        "utilization_pct": None,
        "note": "GPU utilization is not reliably exposed without privileged tooling (e.g., powermetrics with sudo) and varies by macOS/hardware.",
    }


def _hardware_state() -> dict[str, Any]:
    sp = _do_shell("system_profiler SPHardwareDataType 2>/dev/null")

    def find(label: str) -> str | None:
        m = re.search(rf"^{re.escape(label)}:\s*(.+)$", sp, re.MULTILINE)
        return m.group(1).strip() if m else None

    return {
        "model_name": find("Model Name"),
        "model_identifier": find("Model Identifier"),
        "chip": find("Chip") or find("Processor Name"),
        "cores": find("Total Number of Cores") or find("Number of Processors"),
        "memory": find("Memory"),
        "raw": sp,
    }


def get_mac_state(section: Section = "all") -> dict[str, Any]:
    if section == "all":
        return {
            "cpu": _cpu_state(),
            "memory": _memory_state(),
            "disk": _disk_state(),
            "battery": _battery_state(),
            "wifi": _wifi_state(),
            "gpu": _gpu_state(),
            "hardware": _hardware_state(),
        }

    if section == "cpu":
        return _cpu_state()
    if section == "memory":
        return _memory_state()
    if section == "disk":
        return _disk_state()
    if section == "battery":
        return _battery_state()
    if section == "wifi":
        return _wifi_state()
    if section == "gpu":
        return _gpu_state()
    if section == "hardware":
        return _hardware_state()

    raise ValueError(f"Unknown section: {section}")


def list_running_apps(app_name: str | None = None) -> dict[str, Any]:
    script = r'''
tell application "System Events"
    set appList to name of every application process whose background only is false
end tell
return appList as string
'''
    raw = _osascript(script)
    apps = [a.strip() for a in raw.split(",") if a.strip()]

    if app_name is None:
        return {"apps": apps}

    q = app_name.strip().lower()
    exact = any(a.lower() == q for a in apps)
    contains = any(q in a.lower() for a in apps)
    running = exact or contains

    return {
        "query": app_name,
        "running": running,
        "match_type": "exact" if exact else ("contains" if contains else None),
        "apps": apps,
    }


def mac_power(action: Literal["shutdown", "restart", "sleep", "hibernate"]) -> None:
    if action in ("shutdown", "restart", "sleep"):
        verb = {"shutdown": "shut down", "restart": "restart", "sleep": "sleep"}[action]
        _osascript(f'tell application "System Events" to {verb}')
        return

    if action == "hibernate":
        cmd = "sudo pmset -a hibernatemode 25 && sudo pmset sleepnow"
        subprocess.run(cmd, shell=True, check=True, text=True)
        return

    raise ValueError(f"Unknown power action: {action}")


def open_app(name: str):
    name = name.strip()
    # Проверяем путь к приложению
    app_path = shutil.which(name)  # для CLI-приложений
    if app_path:
        subprocess.run([app_path])
        return f"{name} открыт."
    else:
        # Для MacOS GUI
        try:
            subprocess.run(["open", "-a", name], check=True)
            return name
        except subprocess.CalledProcessError:
            return f"Не удалось открыть {name}."

def set_volume(level: int):
    level = max(0, min(100, level))
    subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
    return level

def mute_system(status: bool):
    try:
        subprocess.run(["osascript", "-e", f"set volume output muted {str(status).lower()}"], check=True)
        return None  # info в args
    except subprocess.CalledProcessError:
        return None

def play_media():
    subprocess.run(["osascript", "-e", 'tell application "Music" to play'])
    return None

def pause_media():
    subprocess.run(["osascript", "-e", 'tell application "Music" to pause'])
    return None

def next_media():
    subprocess.run(["osascript", "-e", 'tell application "Music" to next track'])
    return None

def previous_media():
    subprocess.run(["osascript", "-e", 'tell application "Music" to previous track'])
    return None

def get_volume():
    out = subprocess.check_output(
        ["osascript", "-e", "output volume of (get volume settings)"]
    )
    return int(out.strip())

def change_volume(delta: int):
    current = get_volume()
    new_level = current + delta
    new_level = min(100, new_level)
    return set_volume(new_level)


def get_local_weather(when: str | int | None = None):
    applescript = 'tell application "Shortcuts Events" to run shortcut "Python Get Location"'

    p = subprocess.run(
        ["osascript", "-e", applescript],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8"
    )

    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "Shortcuts failed via AppleScript")

    out = p.stdout.strip()
    if not out:
        raise RuntimeError("Команда Shortcuts ничего не вернула")

    lat, lon = [c.strip() for c in out.split(",")]

    return get_weather(f"{lat},{lon}", when=when, location=False)


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


def get_weather(city: str, when: str | int | None = None, location: bool = True):
    if location and (not city or not str(city).strip()):
        return get_local_weather(when=when)

    if location:
        geo_url = "https://geocoding-api.open-meteo.com/v1/search"
        geo = requests.get(geo_url, params={
            "name": city,
            "count": 1,
            "language": "ru"
        }).json()

        if "results" not in geo:
            return None

        lat = geo["results"][0]["latitude"]
        lon = geo["results"][0]["longitude"]
    else:
        lat, lon = city.split(",")

    days = _resolve_weather_days(when)
    if days <= 0:
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather = requests.get(weather_url, params={
            "latitude": lat,
            "longitude": lon,
            "current_weather": True
        }).json().get("current_weather")
        return weather

    days = max(1, min(days, 14))
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ["temperature_2m_max", "temperature_2m_min", "weathercode"],
        "timezone": "auto",
    }
    forecast_resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()
    daily = forecast_resp.get("daily")
    if not daily:
        return None

    result = []
    count = min(days, len(daily.get("time", [])))
    for i in range(count):
        result.append({
            "date": daily["time"][i],
            "t_max": daily["temperature_2m_max"][i],
            "t_min": daily["temperature_2m_min"][i],
            "code": daily["weathercode"][i],
        })
    return {"forecast": result}


def get_degrees(city: str):
    return (get_weather(city))["temperature"]


def add_remind(title, notes=None, due_date=None):
    script = f'''
    tell application "Reminders"
        set newReminder to make new reminder with properties {{name:"{title}"}}
        {f'set body of newReminder to "{notes}"' if notes else ''}
        {f'set due date of newReminder to date "{due_date}"' if due_date else ''}
    end tell
    '''
    subprocess.run(["osascript", "-e", script])
    return None

def set_timer(second: int):
    subprocess.run(
        ["shortcuts", "run", "Python Timer"],
        input=str(second),
        text=True,
        check=True
    )


def stopwatch(cmd: str):
    subprocess.run(
        ["shortcuts", "run", "Python Stopwatch"],
        input=cmd.strip(),
        text=True,
        check=True
    )


def send_message(platform: str == "Telegram", to: str, text: str):
    script = f'''
    tell application "{platform}" to activate
    delay 0.5
    tell application "System Events" 
        keystroke "f" using command down 
        delay 0.2
        keystroke "{to}"
        delay 0.5
        keystroke return
        delay 0.5
        keystroke "{text}"
        keystroke return
    end tell
    '''
    s = subprocess.run(["osascript", "-e", script])
    print(s)

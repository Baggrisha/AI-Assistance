import json
import re
import shutil
import subprocess
import time

import requests



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

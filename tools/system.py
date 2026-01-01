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


def get_weather(city: str):
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

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather = requests.get(weather_url, params={
        "latitude": lat,
        "longitude": lon,
        "current_weather": True
    }).json()["current_weather"]
    return weather

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

def set_timer(seconds: int):
    apple_script = f'''
    delay {seconds}
    display notification "Время вышло!" with title "Таймер"
    '''
    subprocess.run(["osascript", "-e", apple_script])
    return None

import requests

def stream_text(text: str, chunk_size: int = 5):
    """
    Разбивает текст на чанки для стриминга в GUI
    """
    for i in range(0, len(text), chunk_size):
        yield text[i:i + chunk_size]



from datetime import datetime

def normalize_weather(result):
    args = result["args"]

    dt = datetime.fromisoformat(args["time"])
    date_str = dt.strftime("%-d %B %Y года")
    time_str = dt.strftime("%H:%M")

    wind_dir_map = {
        (0, 22): "северный",
        (23, 67): "северо-восточный",
        (68, 112): "восточный",
        (113, 157): "юго-восточный",
        (158, 202): "южный",
        (203, 247): "юго-западный",
        (248, 292): "западный",
        (293, 337): "северо-западный",
        (338, 360): "северный",
    }

    wd = args["winddirection"]
    wind_dir = next(v for (a,b),v in wind_dir_map.items() if a <= wd <= b)

    return {
        "time": time_str,
        "temperature": round(args["temperature"], 1),
        "wind_speed": round(args["windspeed"], 1),
        "wind_direction": wind_dir,
        "is_day": "дневное время" if args["is_day"] else "ночное время"
    }

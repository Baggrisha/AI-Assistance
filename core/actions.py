import datetime

from tools.system import open_app, pause_media, set_volume, change_volume, play_media, next_media, previous_media, \
    mute_system, get_weather, get_degrees, add_remind, set_timer, stopwatch, get_local_weather

ACTION_MAP = {
    "open_app": lambda a: open_app(a["name"]),
    "play_media": lambda a: play_media(),
    "pause_media": lambda a: pause_media(),
    "next_media": lambda a: next_media(),
    "previous_media": lambda a: previous_media(),
    "set_volume": lambda a: set_volume(a["level"]),
    "change_volume": lambda a: change_volume(a["delta"]),
    "mute": lambda a: mute_system(True),
    "un_mute": lambda a:  mute_system(False),
    "get_date": lambda a:  mute_system(False),
    "get_time": lambda a:  mute_system(False),
    "get_weather": lambda a:  get_weather(a["city"], a["when"]),
    "get_local_weather": lambda a: get_local_weather(a["when"]),
    "get_degrees": lambda a:  get_degrees(a["city"]),
    "add_remind": lambda a: add_remind(a["title"], a["notes"], a["due_date"]),
    "set_timer": lambda a: set_timer(a["seconds"]),
    "stopwatch": lambda a: stopwatch(a["cmd"]),
}


def execute_actions(intents):
    results = []

    for action, args in intents:
        handler = ACTION_MAP.get(action)
        if not handler:
            continue
        try:
            value = handler(args)
            results.append({
                "action": action,
                "args": value,
                "success": True
            })
        except Exception as e:
            results.append({
                "action": action,
                "args": args,
                "success": False
            })
    return results

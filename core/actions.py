from concurrent.futures import ThreadPoolExecutor

from tools.system import (
    add_remind,
    change_volume,
    get_degrees,
    get_local_weather,
    get_mac_state,
    get_weather,
    list_running_apps,
    mac_power,
    mute_system,
    next_media,
    open_app,
    pause_media,
    play_media,
    previous_media,
    send_message,
    set_timer,
    set_volume,
    stopwatch,
)

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
    "send_message": lambda a: send_message(a["platform"], a["to"], a["text"]),
    "get_mac_state": lambda a: get_mac_state(a.get("section", "all")),
    "list_running_apps": lambda a: list_running_apps(a.get("app_name")),
    "mac_power": lambda a: mac_power(a["action"]),
}


def execute_actions(intents):
    def _run(action, args):
        handler = ACTION_MAP.get(action)
        if not handler:
            return {
                "action": action,
                "args": args,
                "result": None,
                "success": False
            }
        try:
            value = handler(args or {})
            return {
                "action": action,
                "args": args,
                "result": value,
                "success": True
            }
        except Exception as e:
            return {
                "action": action,
                "args": args,
                "result": str(e),
                "success": False
            }

    if len(intents) <= 1:
        return [_run(action, args) for action, args in intents]

    with ThreadPoolExecutor(max_workers=min(4, len(intents))) as pool:
        futures = [pool.submit(_run, action, args) for action, args in intents]
        return [f.result() for f in futures]

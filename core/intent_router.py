import json
import re

from tools.promt import SYSTEM_PROMPT_SUPPORT as SYSTEM_PROMPT


def detect_intents_llm(text: str, llm, cancel_event=None):
    if llm is None:
        return []
    if cancel_event and cancel_event.is_set():
        return []

    prompt = f"{SYSTEM_PROMPT}\nПользователь: {text}\nJSON:"

    try:
        raw_parts: list[str] = []
        stream = llm.generate(prompt, stop_event=cancel_event)

        if isinstance(stream, str):
            raw_parts.append(stream)
        else:
            for chunk in stream:
                if cancel_event and cancel_event.is_set():
                    return []
                raw_parts.append(chunk)

        raw = "".join(raw_parts)
        clean = re.sub(r"```json|```", "", raw).strip()

        match = re.search(r"\[\s*\{.*?\}\s*\]", clean, re.DOTALL)
        if not match:
            return []

        data = json.loads(match.group(0))
        actions = []
        for item in data:
            actions.append((
                item.get("action"),
                item.get("args", {})
            ))

        return actions

    except Exception as e:
        return []

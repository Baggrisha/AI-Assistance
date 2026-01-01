import re
import json
from tools.promt import SYSTEM_PROMPT_SUPPORT as SYSTEM_PROMPT


def detect_intents_llm(text: str, llm):
    if llm is None:
        return []

    prompt = f"{SYSTEM_PROMPT}\nПользователь: {text}\nJSON:"

    try:
        raw = ""
        for chunk in llm.generate(prompt):
            raw += chunk

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
        print("[intent_router] error:", e)
        print("RAW:", raw)
        return []

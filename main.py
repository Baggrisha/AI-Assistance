from brain.support_model import MiniCommandModel
from tools.env_tools import load_settings
from brain.client import LLMClient
from core.agent import Agent
from core.stt import GigaAMSpeechToText

from PySide6.QtWidgets import QApplication
from gui.gui import MainWindow

# если у тебя streamer лежит в core/tts_stream.py:
from core.tts import SileroTTSStreamer
# если он у тебя реально в core/tts.py, тогда оставь:
# from core.tts import SileroTTSStreamer


if __name__ == "__main__":
    settings = load_settings()

    llm_client = LLMClient(model=settings.main_model)
    mini_llm = MiniCommandModel(model=settings.mini_model)

    tts = SileroTTSStreamer(
        speaker="kseniya",
        min_chars=8,
        debug=True
    )

    stt = GigaAMSpeechToText()

    agent = Agent(
        llm=llm_client,
        mini_model=mini_llm,
        tts=tts
    )

    app = QApplication([])                # ✅ правильно
    window = MainWindow(agent, env_path=".env", stt_client=stt)
    window.show()
    app.exec()                            # ✅ правильно

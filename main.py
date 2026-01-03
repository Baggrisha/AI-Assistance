import logging
from pathlib import Path
from datetime import datetime

from PySide6 import QtCore
from PySide6.QtWidgets import QApplication

from brain.support_model import MiniCommandModel
from tools.env_tools import load_settings, read_env
from brain.client import LLMClient
from core.agent import Agent
from core.voice import HFWhisperRecognizer
from gui.gui import MainWindow

from core.tts import SileroTTSStreamer

class ResourceLoader(QtCore.QObject):
    recognizer_ready = QtCore.Signal(object)
    warmup_done = QtCore.Signal()
    error = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self, env: dict[str, str], agent: Agent):
        super().__init__()
        self.env = env
        self.agent = agent
        self.logger = logging.getLogger(__name__)

    @QtCore.Slot()
    def run(self):
        try:
            recognizer = HFWhisperRecognizer.from_env(self.env)
            self.recognizer_ready.emit(recognizer)
            self.logger.info("ASR model loaded")
        except Exception as e:
            self.error.emit(f"ASR load failed: {e}")

        try:
            self.warmup_done.emit()
        except Exception as e:
            self.error.emit(f"LLM warmup failed: {e}")
        finally:
            self.finished.emit()


if __name__ == "__main__":
    log_root = Path("logs")
    day_dir = log_root / datetime.now().strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handlers = [
        logging.FileHandler(day_dir / "app.log", encoding="utf-8"),
        logging.FileHandler(day_dir / "error.log", encoding="utf-8"),
        logging.StreamHandler(),
    ]
    handlers[1].setLevel(logging.ERROR)
    handlers[2].setLevel(logging.ERROR)
    logging.basicConfig(level=logging.INFO, handlers=handlers, format="%(message)s")
    for h in handlers:
        h.setFormatter(formatter)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    settings = load_settings()
    env = read_env(".env")

    llm_client = LLMClient(model=settings.main_model)
    mini_llm = MiniCommandModel(model=settings.mini_model)

    def _tts_factory():
        logging.getLogger(__name__).info("Initializing TTS streamer lazily")
        return SileroTTSStreamer(
            speaker="kseniya",
            debug=True,
            block_output=True,
        )

    agent = Agent(
        llm=llm_client,
        mini_model=mini_llm,
        tts=None,
    )

    app = QApplication([])
    window = MainWindow(agent, env_path=".env", recognizer=None)
    window.show()

    loader = ResourceLoader(env, agent)
    loader_thread = QtCore.QThread()
    loader.moveToThread(loader_thread)
    loader_thread.started.connect(loader.run)
    loader.finished.connect(loader_thread.quit)
    loader_thread.finished.connect(loader.deleteLater)
    loader_thread.finished.connect(loader_thread.deleteLater)
    loader.recognizer_ready.connect(window.attach_recognizer)
    loader.error.connect(lambda msg: logging.getLogger(__name__).error(msg))
    loader.warmup_done.connect(lambda: logging.getLogger(__name__).info("Ollama warmup complete"))
    loader_thread.start()

    app.exec()

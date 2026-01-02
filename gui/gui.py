from __future__ import annotations

import io
import math
import wave

import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtGui, QtWidgets

from core.stt import GigaAMSpeechToText
from gui.styles import VIKA_QSS
from tools.env_tools import read_env, write_env, get_ollama_models


class VoiceOrb(QtWidgets.QWidget):
    """
    Круглая Siri-style кнопка озвучки:
    - Светится, когда включена
    - Пульсирует, когда active=True (например, пока идёт ответ/озвучка)
    """
    toggled = QtCore.Signal(bool)

    def __init__(self, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 38)
        self.enabled = enabled
        self.active = False
        self.phase = 0.0

        self.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def set_enabled(self, v: bool):
        self.enabled = bool(v)
        self.update()

    def set_active(self, v: bool):
        self.active = bool(v)
        self.update()

    def mousePressEvent(self, e):
        self.enabled = not self.enabled
        self.toggled.emit(self.enabled)
        self.update()

    def _tick(self):
        if self.active and self.enabled:
            self.phase += 0.14
            self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        r = self.rect()
        cx, cy = r.center().x(), r.center().y()

        if not self.enabled:
            base = QtGui.QColor(242, 242, 247, 70)
            ring = QtGui.QColor(242, 242, 247, 35)
        else:
            base = QtGui.QColor(10, 132, 255, 190)   # Apple blue
            ring = QtGui.QColor(10, 132, 255, 110)

        # glow
        if self.enabled:
            pulse = abs(math.sin(self.phase)) if self.active else 0.0
            glow_radius = 18 + int(5 * pulse)
            grad = QtGui.QRadialGradient(cx, cy, glow_radius)
            grad.setColorAt(0.0, QtGui.QColor(base.red(), base.green(), base.blue(), 110))
            grad.setColorAt(1.0, QtGui.QColor(base.red(), base.green(), base.blue(), 0))
            p.setBrush(grad)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(r.center(), glow_radius, glow_radius)

        # outer soft ring
        p.setPen(QtGui.QPen(ring, 2))
        p.setBrush(QtCore.Qt.NoBrush)
        p.drawEllipse(r.adjusted(6, 6, -6, -6))

        # core
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(base)
        p.drawEllipse(r.adjusted(10, 10, -10, -10))

        # icon (🔊 / 🔇) drawn as simple glyph
        p.setPen(QtGui.QColor(11, 12, 16, 220) if self.enabled else QtGui.QColor(242, 242, 247, 130))
        font = p.font()
        font.setPointSize(12)
        font.setBold(True)
        p.setFont(font)
        p.drawText(r, QtCore.Qt.AlignCenter, "🔊" if self.enabled else "🔇")


class ChatArea(QtWidgets.QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.container = QtWidgets.QWidget()
        self.v = QtWidgets.QVBoxLayout(self.container)
        self.v.setContentsMargins(18, 18, 18, 18)
        self.v.setSpacing(12)
        self.v.addStretch(1)
        self.setWidget(self.container)

    def add_row(self, w: QtWidgets.QWidget, right: bool):
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        if right:
            row.addStretch(1)
            row.addWidget(w, 0)
        else:
            row.addWidget(w, 0)
            row.addStretch(1)
        self.v.insertLayout(self.v.count() - 1, row)
        QtCore.QTimer.singleShot(0, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class Bubble(QtWidgets.QFrame):
    def __init__(self, text: str, is_user: bool):
        super().__init__()
        self.setObjectName("UserBubble" if is_user else "BotBubble")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.label = QtWidgets.QLabel(text)
        self.label.setObjectName("BubbleText")
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.addWidget(self.label)

    def set_max_width(self, w: int):
        # Внятные границы, чтобы не разваливалось на очень узком окне
        self.setMaximumWidth(max(320, int(w)))

    def append(self, chunk: str):
        self.label.setText(self.label.text() + chunk)


class TypingDots(QtWidgets.QWidget):
    """3 точки как в ChatGPT."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 14)
        self._phase = 0
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(220)

    def _tick(self):
        self._phase = (self._phase + 1) % 4
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        base = QtGui.QColor(242, 242, 247, 140)
        hi = QtGui.QColor(242, 242, 247, 235)

        xs = [8, 22, 36]
        for i, x in enumerate(xs):
            c = hi if (i == self._phase - 1) else base
            p.setBrush(c)
            p.setPen(QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(x, 7), 3.2, 3.2)


class TypingBubble(QtWidgets.QFrame):
    """Bubble с тремя точками, визуально идентичный обычному BotBubble."""
    def __init__(self):
        super().__init__()
        self.setObjectName("BotBubble")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.setSpacing(0)

        dots = TypingDots()
        lay.addWidget(dots, alignment=QtCore.Qt.AlignLeft)

    def set_max_width(self, w: int):
        self.setMaximumWidth(max(220, int(w)))


class AudioRecorder(QtCore.QObject):
    error = QtCore.Signal(str)

    def __init__(self, sample_rate: int = 16000, channels: int = 1, parent=None):
        super().__init__(parent)
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    def start(self):
        self._frames = []
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._callback,
            )
            self._stream.start()
        except Exception as e:
            self._stream = None
            self.error.emit(str(e))

    def _callback(self, indata, frames, time_info, status):
        if status:
            # Сохраняем предупреждение, но не останавливаем запись
            print("Audio status:", status)
        self._frames.append(indata.copy())

    def stop(self) -> bytes:
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

        if not self._frames:
            return b""

        audio = np.concatenate(self._frames, axis=0)
        audio = np.clip(audio, -1.0, 1.0)
        audio_int16 = np.int16(audio * 32767)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_int16.tobytes())
        return buf.getvalue()


class TranscribeWorker(QtCore.QObject):
    finished = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, stt_client: GigaAMSpeechToText, audio_bytes: bytes):
        super().__init__()
        self.stt_client = stt_client
        self.audio_bytes = audio_bytes

    @QtCore.Slot()
    def run(self):
        try:
            text = self.stt_client.transcribe(self.audio_bytes)
            self.finished.emit(text)
        except Exception as e:
            self.error.emit(str(e))


class StreamWorker(QtCore.QObject):
    chunk = QtCore.Signal(str)
    done = QtCore.Signal()
    error = QtCore.Signal(str)

    def __init__(self, agent, prompt: str):
        super().__init__()
        self.agent = agent
        self.prompt = prompt
        self._stop = False

    @QtCore.Slot()
    def run(self):
        try:
            for piece in self.agent.handle_stream(self.prompt):
                if self._stop:
                    break
                self.chunk.emit(piece)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop = True
        tts = getattr(self.agent, "tts", None)
        if tts:
            try:
                tts.stop_playback()
            except Exception:
                pass


class SettingsTab(QtWidgets.QWidget):
    def __init__(self, agent, env_path: str = ".env"):
        super().__init__()
        self.agent = agent
        self.env_path = env_path

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        title = QtWidgets.QLabel("Settings")
        title.setObjectName("Title")
        outer.addWidget(title)

        self.msg = QtWidgets.QLabel("")
        self.msg.setObjectName("Warn")

        # Models from Ollama
        self.main_model = QtWidgets.QComboBox()
        self.main_model.setEditable(True)
        self.main_model.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self.mini_model = QtWidgets.QComboBox()
        self.mini_model.setEditable(True)
        self.mini_model.setInsertPolicy(QtWidgets.QComboBox.NoInsert)

        self.btn_save = QtWidgets.QPushButton("Save to .env")

        # Voice (Silero speakers)
        self.voice_combo = QtWidgets.QComboBox()
        self.voice_combo.addItems(["kseniya", "baya", "xenia", "aidar"])

        hint = QtWidgets.QLabel("Модели сохраняются в .env (MAIN_MODEL / MINI_MODEL). После смены моделей лучше перезапуск.")
        hint.setObjectName("Hint")

        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)

        grid.addWidget(QtWidgets.QLabel("MAIN_MODEL"), 0, 0)
        grid.addWidget(self.main_model, 0, 1)

        grid.addWidget(QtWidgets.QLabel("MINI_MODEL"), 1, 0)
        grid.addWidget(self.mini_model, 1, 1)

        grid.addWidget(QtWidgets.QLabel("Voice (Silero)"), 2, 0)
        grid.addWidget(self.voice_combo, 2, 1)

        outer.addLayout(grid)
        outer.addWidget(self.btn_save)
        outer.addWidget(hint)
        outer.addWidget(self.msg)
        outer.addStretch(1)

        self.btn_save.clicked.connect(self.save_env)
        self.voice_combo.currentTextChanged.connect(self.apply_voice)

        self.load_env()
        self.apply_voice()

    def load_env(self):
        env = read_env(self.env_path)
        main_val = env.get("MAIN_MODEL", "").strip()
        mini_val = env.get("MINI_MODEL", "").strip()

        if main_val:
            if self.main_model.findText(main_val) < 0:
                self.main_model.addItem(main_val)
            self.main_model.setCurrentText(main_val)

        if mini_val:
            if self.mini_model.findText(mini_val) < 0:
                self.mini_model.addItem(mini_val)
            self.mini_model.setCurrentText(mini_val)

    def save_env(self):
        main_val = self.main_model.currentText().strip()
        mini_val = self.mini_model.currentText().strip()
        if not main_val or not mini_val:
            self.msg.setText("Выбери MAIN_MODEL и MINI_MODEL.")
            return

        write_env(self.env_path, {"MAIN_MODEL": main_val, "MINI_MODEL": mini_val})
        self.msg.setText("Сохранено в .env. Перезапусти приложение, чтобы точно применилось.")

    def apply_voice(self):
        tts = getattr(self.agent, "tts", None)
        if not tts:
            return
        try:
            tts.speaker = self.voice_combo.currentText()
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, agent, env_path: str = ".env", stt_client: GigaAMSpeechToText | None = None):
        super().__init__()
        self.agent = agent
        self.env_path = env_path
        self.stt_client = stt_client

        self.setWindowTitle("Асистент Вика")
        self.resize(980, 740)

        # Fusion style helps убрать нативные macOS focus rings
        app = QtWidgets.QApplication.instance()
        if app:
            app.setStyle("Fusion")

        root = QtWidgets.QWidget()
        root.setStyleSheet(VIKA_QSS)
        self.setCentralWidget(root)

        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)

        # --- Chat tab ---
        chat_tab = QtWidgets.QWidget()
        chat_l = QtWidgets.QVBoxLayout(chat_tab)
        chat_l.setContentsMargins(18, 18, 18, 18)
        chat_l.setSpacing(14)

        top = QtWidgets.QHBoxLayout()
        self.title = QtWidgets.QLabel("Асистент Вика")
        self.title.setObjectName("Title")
        self.status = QtWidgets.QLabel("Ready")
        self.status.setObjectName("Status")
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(self.status)

        glass = QtWidgets.QFrame()
        glass.setObjectName("Glass")
        glass_l = QtWidgets.QVBoxLayout(glass)
        glass_l.setContentsMargins(10, 10, 10, 10)
        glass_l.setSpacing(10)

        self.chat = ChatArea()
        glass_l.addWidget(self.chat, 1)

        # input pill
        pill = QtWidgets.QFrame()
        pill.setObjectName("InputPill")
        pill_l = QtWidgets.QHBoxLayout(pill)
        pill_l.setContentsMargins(10, 6, 10, 6)
        pill_l.setSpacing(8)

        # load voice enabled from .env
        env = read_env(env_path)
        voice_enabled = (env.get("VOICE_ENABLED", "1") == "1")

        self.voice_orb = VoiceOrb(enabled=voice_enabled)
        pill_l.addWidget(self.voice_orb)

        self.btn_record = QtWidgets.QToolButton()
        self.btn_record.setText("🎙")
        self.btn_record.setToolTip("Голосовой ввод (GigaAM)")
        self.btn_record.setCheckable(True)
        self.btn_record.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_record.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 8px 10px; }"
            "QToolButton:hover { background: rgba(255,255,255,0.10); border-radius: 16px; }"
            "QToolButton:checked { background: rgba(10,132,255,0.14); border-radius: 16px; }"
        )
        pill_l.addWidget(self.btn_record)

        self.input = QtWidgets.QTextEdit()
        self.input.setObjectName("Input")
        self.input.setPlaceholderText("Напиши сообщение…  (Enter=Send, Shift+Enter=новая строка)")
        self.input.setFixedHeight(54)

        self.btn_stop = QtWidgets.QToolButton()
        self.btn_stop.setText("⏹")
        self.btn_stop.setToolTip("Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_stop.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 8px 10px; }"
            "QToolButton:hover { background: rgba(255,255,255,0.10); border-radius: 16px; }"
        )

        self.btn_send = QtWidgets.QToolButton()
        self.btn_send.setText("➤")
        self.btn_send.setToolTip("Send")
        self.btn_send.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_send.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 8px 10px; }"
            "QToolButton:hover { background: rgba(255,255,255,0.10); border-radius: 16px; }"
        )

        pill_l.addWidget(self.input, 1)
        pill_l.addWidget(self.btn_stop)
        pill_l.addWidget(self.btn_send)

        chat_l.addLayout(top)
        chat_l.addWidget(glass, 1)
        chat_l.addWidget(pill)

        # --- Settings tab ---
        settings_tab = SettingsTab(agent, env_path=env_path)

        tabs.addTab(chat_tab, "Chat")
        tabs.addTab(settings_tab, "Settings")

        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)

        # state
        self._active_bot: Bubble | None = None
        self._typing: TypingBubble | None = None
        self._thread: QtCore.QThread | None = None
        self._worker: StreamWorker | None = None
        self._stt_thread: QtCore.QThread | None = None
        self._stt_worker: TranscribeWorker | None = None

        # bubble sizing (75% of chat viewport)
        self._bubble_width_ratio = 0.75

        # voice input
        self.recorder = AudioRecorder(parent=self)
        self.recorder.error.connect(self.on_transcribe_error)
        self._is_recording = False

        # signals
        self.btn_send.clicked.connect(self.on_send)
        self.btn_stop.clicked.connect(self.on_stop)
        self.voice_orb.toggled.connect(self.on_voice_toggle)
        self.btn_record.clicked.connect(self.on_record_toggle)
        self.input.installEventFilter(self)

        # initial tts flag
        setattr(self.agent, "tts_enabled", voice_enabled)

        hello = Bubble("Привет. Чем могу помочь?", is_user=False)
        hello.set_max_width(self._bubble_max_width())
        self.chat.add_row(hello, right=False)

        # apply widths after first layout pass
        QtCore.QTimer.singleShot(0, self._apply_bubble_widths)

    def _bubble_max_width(self) -> int:
        viewport_w = self.chat.viewport().width()
        # запас, чтобы пузырь не упирался в края при очень широком окне
        return int(viewport_w * self._bubble_width_ratio)

    def _apply_bubble_widths(self):
        mw = self._bubble_max_width()

        # В self.chat.v лежат элементы: QHBoxLayout-строки и stretch
        for i in range(self.chat.v.count()):
            item = self.chat.v.itemAt(i)
            if not item:
                continue

            row = item.layout()
            if not row:
                continue

            for j in range(row.count()):
                w = row.itemAt(j).widget()
                if w and hasattr(w, "set_max_width"):
                    w.set_max_width(mw)

        self.chat.container.updateGeometry()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply_bubble_widths()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if event.modifiers() & QtCore.Qt.ShiftModifier:
                    return False
                self.on_send()
                return True
        return super().eventFilter(obj, event)

    def on_voice_toggle(self, enabled: bool):
        setattr(self.agent, "tts_enabled", enabled)
        write_env(self.env_path, {"VOICE_ENABLED": "1" if enabled else "0"})
        self.voice_orb.set_enabled(enabled)
        if not enabled:
            self.voice_orb.set_active(False)
            tts = getattr(self.agent, "tts", None)
            if tts:
                try:
                    tts.stop_playback()
                except Exception:
                    pass

    def on_send(self):
        prompt = self.input.toPlainText().strip()
        self._submit_prompt(prompt)

    def _submit_prompt(self, prompt: str):
        if not prompt:
            return

        user_b = Bubble(prompt, is_user=True)
        user_b.set_max_width(self._bubble_max_width())
        self.chat.add_row(user_b, right=True)

        self.input.clear()

        # typing indicator (3 dots) as a real bubble
        self._typing = TypingBubble()
        self._typing.set_max_width(self._bubble_max_width())
        self.chat.add_row(self._typing, right=False)

        # prepare bot bubble for streaming
        self._active_bot = Bubble("", is_user=False)
        self._active_bot.set_max_width(self._bubble_max_width())

        self.start_stream(prompt)

    def start_stream(self, prompt: str):
        self.status.setText("Thinking…")
        self.btn_send.setEnabled(False)
        self.btn_stop.setEnabled(True)

        # orb pulse while "working"
        if self.voice_orb.enabled:
            self.voice_orb.set_active(True)

        self._thread = QtCore.QThread(self)
        self._worker = StreamWorker(self.agent, prompt)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.chunk.connect(self.on_chunk)
        self._worker.done.connect(self.on_done)
        self._worker.error.connect(self.on_error)

        self._worker.done.connect(self._thread.quit)
        self._worker.done.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def on_record_toggle(self):
        if self._is_recording:
            self._finish_recording()
            return

        if not self.stt_client:
            self.status.setText("Нет настроек GigaAM для распознавания")
            self.btn_record.setChecked(False)
            return

        self.status.setText("Запись…")
        self.btn_record.setText("⏹")
        self._is_recording = True
        self.recorder.start()

    def _finish_recording(self):
        audio = self.recorder.stop()
        self._is_recording = False
        self.btn_record.setChecked(False)
        self.btn_record.setText("🎙")

        if not audio:
            self.status.setText("Нет аудио для распознавания")
            return

        self._start_transcription(audio)

    def _start_transcription(self, audio: bytes):
        if not self.stt_client:
            self.status.setText("GigaAM не настроен")
            return

        if self._stt_thread:
            self._stt_thread.quit()
            self._stt_thread.wait()
            self._stt_thread = None

        self.status.setText("GigaAM: распознаю…")
        self._stt_thread = QtCore.QThread(self)
        self._stt_worker = TranscribeWorker(self.stt_client, audio)
        self._stt_worker.moveToThread(self._stt_thread)

        self._stt_thread.started.connect(self._stt_worker.run)
        self._stt_worker.finished.connect(self.on_transcribed)
        self._stt_worker.error.connect(self.on_transcribe_error)

        self._stt_worker.finished.connect(self._stt_thread.quit)
        self._stt_worker.error.connect(self._stt_thread.quit)
        self._stt_worker.finished.connect(self._stt_worker.deleteLater)
        self._stt_worker.error.connect(self._stt_worker.deleteLater)
        self._stt_thread.finished.connect(self._stt_thread.deleteLater)

        self._stt_thread.start()

    def _remove_typing(self):
        if self._typing:
            self._typing.hide()
            self._typing.deleteLater()
            self._typing = None

    def on_chunk(self, chunk: str):
        # first chunk: swap typing -> bot bubble
        if self._typing:
            self._remove_typing()
            if self._active_bot:
                self.chat.add_row(self._active_bot, right=False)
            self.status.setText("Responding…")

        if self._active_bot:
            self._active_bot.append(chunk)
            self.chat.scroll_to_bottom()

    def on_transcribed(self, text: str):
        self._stt_thread = None
        self._stt_worker = None
        self.status.setText("Готово")
        cleaned = text.strip()
        if cleaned:
            self._submit_prompt(cleaned)
        else:
            self.status.setText("GigaAM не распознал речь")

    def on_transcribe_error(self, msg: str):
        self._stt_thread = None
        self._stt_worker = None
        self.status.setText(f"STT ошибка: {msg}")
        self.btn_record.setChecked(False)
        self.btn_record.setText("🎙")
        self._is_recording = False

    def on_done(self):
        self._remove_typing()
        self.status.setText("Ready")
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.voice_orb.set_active(False)

    def on_error(self, msg: str):
        self._remove_typing()
        self.status.setText("Error")
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.voice_orb.set_active(False)
        if self._active_bot:
            self._active_bot.append(f"\n\nОшибка: {msg}")

    def on_stop(self):
        if self._worker:
            self._worker.stop()
        self._remove_typing()
        self.status.setText("Stopped")
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.voice_orb.set_active(False)
        tts = getattr(self.agent, "tts", None)
        if tts:
            try:
                tts.stop_playback()
            except Exception:
                pass


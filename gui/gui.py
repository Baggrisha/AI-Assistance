from __future__ import annotations

import logging
import math
import threading

from PySide6 import QtCore, QtGui, QtWidgets

from core.voice import VoiceRecorder, HFWhisperRecognizer
from gui.styles import VIKA_QSS
from tools.env_tools import read_env, write_env

logger = logging.getLogger(__name__)


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
            base = QtGui.QColor(10, 132, 255, 190)  # Apple blue
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
        if not bar:
            return

        def _scroll():
            bar.setValue(bar.maximum())

        QtCore.QTimer.singleShot(0, _scroll)
        QtCore.QTimer.singleShot(15, _scroll)  # второй тик после пересчёта лэйаута

    def clear_messages(self):
        # удаляем все строки, кроме финального stretch
        while self.v.count() > 1:
            item = self.v.takeAt(0)
            if not item:
                continue
            lay = item.layout()
            if lay:
                while lay.count():
                    child = lay.takeAt(0)
                    w = child.widget()
                    if w:
                        w.deleteLater()
                lay.deleteLater()
            else:
                w = item.widget()
                if w:
                    w.deleteLater()
        QtCore.QTimer.singleShot(0, self.scroll_to_bottom)


class Bubble(QtWidgets.QFrame):
    def __init__(self, text: str, is_user: bool):
        super().__init__()
        self.setObjectName("UserBubble" if is_user else "BotBubble")
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.label = QtWidgets.QLabel(text)
        self.label.setObjectName("BubbleText")
        self.label.setWordWrap(True)
        self.label.setTextFormat(QtCore.Qt.TextFormat.MarkdownText)
        self.label.setOpenExternalLinks(True)
        self.label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.addWidget(self.label)

    def set_max_width(self, w: int):
        # Даем пузырям ширину ближе к макс. доступной, чтобы текст не ломался каждую строку
        self.setMaximumWidth(max(360, int(w * 0.95)))

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


class StreamWorker(QtCore.QObject):
    chunk = QtCore.Signal(str)
    done = QtCore.Signal()
    error = QtCore.Signal(str)

    def __init__(self, agent, prompt: str):
        super().__init__()
        self.agent = agent
        self.prompt = prompt
        self._stop = False
        self._cancel_event = threading.Event()

    @QtCore.Slot()
    def run(self):
        try:
            for piece in self.agent.handle_stream(self.prompt, cancel_event=self._cancel_event):
                if self._stop or self._cancel_event.is_set():
                    break
                self.chunk.emit(piece)
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop = True
        self._cancel_event.set()
        try:
            self.agent.cancel_generation()
        except Exception:
            pass
        tts = getattr(self.agent, "tts", None)
        if tts:
            try:
                tts.close(wait=False)
            except Exception:
                pass


class TranscribeWorker(QtCore.QObject):
    finished = QtCore.Signal(str)
    error = QtCore.Signal(str)

    def __init__(self, recognizer: HFWhisperRecognizer, audio_bytes: bytes, sample_rate: int):
        super().__init__()
        self.recognizer = recognizer
        self.audio_bytes = audio_bytes
        self.sample_rate = sample_rate

    @QtCore.Slot()
    def run(self):
        try:
            text = self.recognizer.transcribe(self.audio_bytes, self.sample_rate)
            self.finished.emit(text.strip())
        except Exception as e:
            self.error.emit(str(e))


class SettingsTab(QtWidgets.QWidget):
    def __init__(
            self,
            agent,
            env_path: str = ".env",
            hotword_enabled: bool = True,
            on_hotword_toggle=None,
            hotword_available: bool = True,
    ):
        super().__init__()
        self.agent = agent
        self.env_path = env_path
        self._on_hotword_toggle = on_hotword_toggle

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

        # Hotword toggle
        self.hotword_check = QtWidgets.QCheckBox("Активация по \"привет, вика\"")
        self.hotword_check.setChecked(hotword_enabled)
        self.hotword_check.setEnabled(hotword_available)
        self.hotword_check.setToolTip("Пассивная активация по кодовой фразе")

        hint = QtWidgets.QLabel(
            "Модели сохраняются в .env (MAIN_MODEL / MINI_MODEL). После смены моделей лучше перезапуск.")
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

        grid.addWidget(QtWidgets.QLabel("Hotword"), 3, 0)
        grid.addWidget(self.hotword_check, 3, 1)

        outer.addLayout(grid)
        outer.addWidget(self.btn_save)
        outer.addWidget(hint)
        outer.addWidget(self.msg)
        outer.addStretch(1)

        self.btn_save.clicked.connect(self.save_env)
        self.voice_combo.currentTextChanged.connect(self.apply_voice)
        self.hotword_check.toggled.connect(self._emit_hotword_toggle)

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

    def _emit_hotword_toggle(self, enabled: bool):
        if callable(self._on_hotword_toggle):
            self._on_hotword_toggle(enabled)

    def set_hotword_available(self, available: bool):
        self.hotword_check.setEnabled(bool(available))
        if not available:
            self.hotword_check.setToolTip("Горячее слово включится после загрузки ASR")
        else:
            self.hotword_check.setToolTip("Пассивная активация по кодовой фразе")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, agent, env_path: str = ".env", recognizer: HFWhisperRecognizer | None = None):
        super().__init__()
        self.agent = agent
        self.env_path = env_path
        self.recognizer = recognizer

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
        self.btn_reset = QtWidgets.QToolButton()
        self.btn_reset.setText("Reset")
        self.btn_reset.setToolTip("Сбросить диалог и контекст")
        self.btn_reset.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_reset.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 6px 10px; }"
            "QToolButton:hover { background: rgba(255,255,255,0.10); border-radius: 14px; }"
        )
        top.addWidget(self.btn_reset)

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
        hotword_enabled = (env.get("HOTWORD_ENABLED", "1") == "1")

        self.voice_orb = VoiceOrb(enabled=voice_enabled)
        pill_l.addWidget(self.voice_orb)

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

        self.btn_mic = QtWidgets.QToolButton()
        self.btn_mic.setText("🎙")
        self.btn_mic.setToolTip("Запись и распознавание через Hugging Face (ai-sage/GigaAM-v3)")
        self.btn_mic.setCheckable(True)
        self.btn_mic.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_mic.setStyleSheet(
            "QToolButton { background: transparent; border: none; padding: 8px 10px; }"
            "QToolButton:hover { background: rgba(255,255,255,0.10); border-radius: 16px; }"
            "QToolButton:checked { background: rgba(10,132,255,0.15); border-radius: 16px; }"
        )
        if not self.recognizer:
            self.btn_mic.setEnabled(False)
            self.btn_mic.setToolTip("ASR не настроен (проверь HF_ASR_MODEL в .env)")

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
        pill_l.addWidget(self.btn_mic)
        pill_l.addWidget(self.btn_send)

        chat_l.addLayout(top)
        chat_l.addWidget(glass, 1)
        chat_l.addWidget(pill)

        # --- Settings tab ---
        self.settings_tab = SettingsTab(
            agent,
            env_path=env_path,
            hotword_enabled=hotword_enabled,
            on_hotword_toggle=self.on_hotword_toggle,
            hotword_available=self.recognizer is not None,
        )

        tabs.addTab(chat_tab, "Chat")
        tabs.addTab(self.settings_tab, "Settings")

        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)

        # state
        self._active_bot: Bubble | None = None
        self._typing: TypingBubble | None = None
        self._thread: QtCore.QThread | None = None
        self._worker: StreamWorker | None = None
        self.recorder = VoiceRecorder()
        self.hotword_recorder = VoiceRecorder()
        self._asr_thread: QtCore.QThread | None = None
        self._asr_worker: TranscribeWorker | None = None
        self._recording = False
        self._silence_timer = QtCore.QTimer(self)
        self._silence_timer.setInterval(300)
        self._silence_timer.timeout.connect(self._check_silence)
        self._hotword_enabled = hotword_enabled
        self._hotword_listening = False
        self._hotword_timer = QtCore.QTimer(self)
        self._hotword_timer.setInterval(300)
        self._hotword_timer.timeout.connect(self._check_hotword_silence)
        self._hotword_thread: QtCore.QThread | None = None
        self._hotword_worker: TranscribeWorker | None = None
        self._streaming = False
        self._auto_refocus = True
        self._stream_timeout_ms = 60000  # safety net, чтобы запросы не зависали навсегда
        self._stream_timeout = QtCore.QTimer(self)
        self._stream_timeout.setSingleShot(True)
        self._stream_timeout.timeout.connect(self._on_stream_timeout)

        self.focus_shortcuts = [
            QtGui.QShortcut(QtGui.QKeySequence("Meta+Shift+Space"), self),
            QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Space"), self),
        ]
        for sc in self.focus_shortcuts:
            sc.activated.connect(self.bring_to_front)

        app_state = QtWidgets.QApplication.instance()
        if app_state:
            app_state.applicationStateChanged.connect(self._on_app_state_changed)
            app_state.focusChanged.connect(self._on_focus_changed)

        # bubble sizing (75% of chat viewport)
        # Расширяем пузыри до ~90% доступной ширины, чтобы помещалось больше текста на строку
        self._bubble_width_ratio = 0.9

        # signals
        self.btn_send.clicked.connect(self.on_send)
        self.btn_stop.clicked.connect(self.on_stop)
        self.voice_orb.toggled.connect(self.on_voice_toggle)
        self.btn_mic.toggled.connect(self.on_record_toggle)
        self.input.installEventFilter(self)
        self.btn_reset.clicked.connect(self.on_reset_dialog)

        # initial tts flag
        if voice_enabled:
            self.agent.enable_tts()
        else:
            self.agent.disable_tts()

        self._add_greeting()

        # apply widths after first layout pass
        QtCore.QTimer.singleShot(0, self._apply_bubble_widths)

        # start passive hotword listening
        self._start_hotword_listening()

    def attach_recognizer(self, recognizer: HFWhisperRecognizer):
        """Вызывается, когда ASR загрузился в фоне."""
        self.recognizer = recognizer
        self.btn_mic.setEnabled(True)
        self.btn_mic.setToolTip("Запись и распознавание через Hugging Face (готово)")
        if hasattr(self, "settings_tab"):
            self.settings_tab.set_hotword_available(True)
        logger.info("ASR recognizer attached")
        self._start_hotword_listening()

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

    def _flash_mic_indicator(self, duration_ms: int = 1200):
        if self._recording:
            return
        self.btn_mic.blockSignals(True)
        self.btn_mic.setChecked(True)
        self.btn_mic.blockSignals(False)
        QtCore.QTimer.singleShot(duration_ms, self._reset_mic_indicator)

    def _reset_mic_indicator(self):
        if self._recording:
            return
        self.btn_mic.blockSignals(True)
        self.btn_mic.setChecked(False)
        self.btn_mic.blockSignals(False)

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
        if enabled:
            self.agent.enable_tts()
        else:
            self.agent.disable_tts()
        write_env(self.env_path, {"VOICE_ENABLED": "1" if enabled else "0"})
        self.voice_orb.set_enabled(enabled)
        if not enabled:
            self.voice_orb.set_active(False)

    def on_record_toggle(self, recording: bool):
        if not self.recognizer:
            self.status.setText("Голос недоступен")
            self.btn_mic.setChecked(False)
            return

        if recording:
            self._stop_speech_output()
            self._stop_hotword_listening()
            try:
                self.recorder.start()
            except Exception as e:
                self.status.setText(f"Ошибка микрофона: {e}")
                self.btn_mic.setChecked(False)
                return
            self._recording = True
            self.status.setText("Recording…")
            self.btn_send.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self.voice_orb.set_active(True)
            self._silence_timer.start()
            return

        if not self._recording:
            return

        self._recording = False
        self._silence_timer.stop()
        self.voice_orb.set_active(False)
        try:
            audio_bytes, sample_rate = self.recorder.stop()
        except Exception as e:
            self.status.setText(f"Ошибка записи: {e}")
            return

        self.status.setText("Transcribing…")
        self.start_transcription(audio_bytes, sample_rate)

    def start_transcription(self, audio_bytes: bytes, sample_rate: int):
        if not audio_bytes:
            self.status.setText("Пустая запись")
            self.btn_mic.setChecked(False)
            self.btn_send.setEnabled(True)
            return

        if self._asr_thread:
            self._asr_thread.quit()
            self._asr_thread.wait()
            self._asr_thread = None
            self._asr_worker = None

        self._asr_thread = QtCore.QThread(self)
        self._asr_worker = TranscribeWorker(self.recognizer, audio_bytes, sample_rate)
        self._asr_worker.moveToThread(self._asr_thread)

        self._asr_thread.started.connect(self._asr_worker.run)
        self._asr_worker.finished.connect(self.on_transcribe_ready)
        self._asr_worker.error.connect(self.on_transcribe_error)
        self._asr_worker.finished.connect(self._asr_thread.quit)
        self._asr_worker.error.connect(self._asr_thread.quit)
        self._asr_thread.finished.connect(self._asr_worker.deleteLater)
        self._asr_thread.finished.connect(self._asr_thread.deleteLater)

        self._asr_thread.start()

    def on_transcribe_ready(self, text: str):
        self._asr_thread = None
        self._asr_worker = None
        self.btn_mic.setChecked(False)
        self.status.setText("Ready")
        self.voice_orb.set_active(False)
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if not text:
            return

        self.input.setText(text)
        self.on_send()
        self._start_hotword_listening()

    def on_transcribe_error(self, msg: str):
        self._asr_thread = None
        self._asr_worker = None
        self.btn_mic.setChecked(False)
        self.status.setText(f"ASR error: {msg}")
        logger.error("ASR error: %s", msg)
        self.voice_orb.set_active(False)
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._start_hotword_listening()

    def on_send(self):
        prompt = self.input.toPlainText().strip()
        if not prompt:
            return
        self._stop_speech_output()
        logger.info("User prompt queued: %s", prompt[:200])

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
        self._streaming = True

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
        self._worker.error.connect(self._thread.quit)
        self._worker.done.connect(self._worker.deleteLater)
        self._worker.error.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()
        self._stream_timeout.start(self._stream_timeout_ms)

    def _remove_typing(self):
        if self._typing:
            self._typing.hide()
            self._typing.deleteLater()
            self._typing = None

    def _stop_stream_thread(self, wait_ms: int = 350):
        if self._worker:
            self._worker.stop()
        if self._thread and self._thread.isRunning():
            self._thread.requestInterruption()
            self._thread.quit()
            self._thread.wait(wait_ms)
        self._worker = None
        self._thread = None

    def _reset_stream_state(self, status_text: str = "Ready"):
        self._remove_typing()
        self.status.setText(status_text)
        self.btn_send.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.voice_orb.set_active(False)
        self._streaming = False
        self._worker = None
        self._thread = None
        self._stream_timeout.stop()
        self._active_bot = None
        if self._auto_refocus:
            try:
                self.bring_to_front()
            except Exception as e:
                logger.warning("bring_to_front failed: %s", e)

    def on_chunk(self, chunk: str):
        if not self._streaming:
            return
        self._stream_timeout.start(self._stream_timeout_ms)
        # first chunk: swap typing -> bot bubble
        if self._typing:
            self._remove_typing()
            if self._active_bot:
                self.chat.add_row(self._active_bot, right=False)
            self.status.setText("Responding…")

        if self._active_bot:
            self._active_bot.append(chunk)
            self.chat.scroll_to_bottom()

    def on_done(self):
        if not self._streaming:
            return
        self._reset_stream_state("Ready")

    def on_error(self, msg: str):
        if not self._streaming:
            return
        logger.error("Stream worker error: %s", msg)
        if self._active_bot:
            self._active_bot.append(f"\n\nОшибка: {msg}")
        self._reset_stream_state("Error")

    def _on_stream_timeout(self):
        logger.warning("Stream timed out, forcing reset")
        self._stop_stream_thread()
        self._reset_stream_state("Timeout")

    def on_stop(self):
        self._stop_stream_thread()
        self._reset_stream_state("Stopped")
        if self.btn_mic.isChecked():
            self.btn_mic.setChecked(False)

    def _stop_speech_output(self):
        """Глушим текущую озвучку и стрим, если пользователь начал новый ввод."""
        try:
            self.agent.stop_tts()
        except Exception as e:
            logger.warning("stop_tts failed: %s", e)

        if self._streaming:
            self._stop_stream_thread()
            self._reset_stream_state("Stopped")

    def on_reset_dialog(self):
        """Полный сброс диалога и контекста."""
        self._stop_speech_output()
        try:
            self.agent.reset_history()
        except Exception as e:
            logger.warning("reset_history failed: %s", e)
        self.input.clear()
        self.chat.clear_messages()
        self._active_bot = None
        self._typing = None
        self.status.setText("Ready")
        self._add_greeting()
        self._apply_bubble_widths()

    def _add_greeting(self):
        hello = Bubble("Привет. Чем могу помочь?", is_user=False)
        hello.set_max_width(self._bubble_max_width())
        self.chat.add_row(hello, right=False)

    def _check_silence(self):
        if not self._recording:
            self._silence_timer.stop()
            return

        if self.recorder.silence_for() >= 1.5:
            self.status.setText("Auto stop: silence")
            self.btn_mic.setChecked(False)

    # --- Passive hotword listening (always-on "Вика") ---
    def _start_hotword_listening(self):
        if not self._hotword_enabled or self._hotword_listening:
            return
        if self._recording:
            return
        if not self.recognizer:
            return
        if self._hotword_thread:
            return
        try:
            self.hotword_recorder.start()
            self._hotword_listening = True
            self._hotword_timer.start()
        except Exception as e:
            self.status.setText(f"Hotword mic error: {e}")
            self._hotword_listening = False

    def _stop_hotword_listening(self):
        if not self._hotword_listening:
            return
        self._hotword_timer.stop()
        try:
            self.hotword_recorder.stop()
        except Exception:
            pass
        self._hotword_listening = False

    def _check_hotword_silence(self):
        if not self._hotword_listening:
            self._hotword_timer.stop()
            return
        if self._recording:
            return
        if self._hotword_thread:
            return
        # если тишина, завершаем сегмент и пробуем распознать активационное слово
        if self.hotword_recorder.silence_for() >= 1.5:
            try:
                audio_bytes, sample_rate = self.hotword_recorder.stop()
            except Exception as e:
                self.status.setText(f"Hotword stop error: {e}")
                self._hotword_listening = False
                self._hotword_timer.stop()
                self._start_hotword_listening()
                return
            self._hotword_listening = False
            self._hotword_timer.stop()
            if audio_bytes:
                self._start_hotword_asr(audio_bytes, sample_rate)
            else:
                self._start_hotword_listening()

    def bring_to_front(self):
        """Пытаемся вернуть окно на передний план, если система разрешает."""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.setWindowState(self.windowState() & ~QtCore.Qt.WindowMinimized)
        self.window().setWindowFlag(QtCore.Qt.Window, True)
        self.window().show()
        self.window().raise_()
        self.window().activateWindow()
        try:
            handle = self.window().windowHandle()
            if handle:
                QtGui.QGuiApplication.setActiveWindow(handle)
        except Exception:
            pass
        try:
            self.setFocus(QtCore.Qt.ActiveWindowFocusReason)
        except Exception:
            pass
        logger.info("Requested bring_to_front")

    def _on_app_state_changed(self, state):
        logger.info("App state changed: %s", state)

    def _on_focus_changed(self, old, new):
        logger.info("Focus changed: %s -> %s", old, new)

    def _start_hotword_asr(self, audio_bytes: bytes, sample_rate: int):
        if not self.recognizer:
            self._start_hotword_listening()
            return
        if self._hotword_thread:
            return

        self._hotword_thread = QtCore.QThread(self)
        self._hotword_worker = TranscribeWorker(self.recognizer, audio_bytes, sample_rate)
        self._hotword_worker.moveToThread(self._hotword_thread)

        self._hotword_thread.started.connect(self._hotword_worker.run)
        self._hotword_worker.finished.connect(self._on_hotword_ready)
        self._hotword_worker.error.connect(self._on_hotword_error)
        self._hotword_worker.finished.connect(self._hotword_thread.quit)
        self._hotword_worker.error.connect(self._hotword_thread.quit)
        self._hotword_thread.finished.connect(self._hotword_worker.deleteLater)
        self._hotword_thread.finished.connect(self._hotword_thread.deleteLater)

        self._hotword_thread.start()

    def _on_hotword_ready(self, text: str):
        self._hotword_thread = None
        self._hotword_worker = None
        if not text:
            self._start_hotword_listening()
            return

        lowered = text.lower()
        wake_variants = ("привет вика", "вика")
        match_pos = None
        match_len = None
        for w in wake_variants:
            idx = lowered.find(w)
            if idx != -1 and (match_pos is None or idx < match_pos):
                match_pos = idx
                match_len = len(w)

        if match_pos is None:
            # no wake word, just resume listening
            self._start_hotword_listening()
            return

        self._flash_mic_indicator()
        command = text[match_pos + match_len:].strip()
        command = command.lstrip(" .,!?:;-—\"'«»")
        if not command:
            self.status.setText("Слушаю команду после \"Вика\"")
            self._start_hotword_listening()
            return

        self._flash_mic_indicator()
        self.input.setText(command)
        self.on_send()
        self._start_hotword_listening()

    def _on_hotword_error(self, msg: str):
        self._hotword_thread = None
        self._hotword_worker = None
        self.status.setText(f"Hotword ASR error: {msg}")
        self._start_hotword_listening()

    def on_hotword_toggle(self, enabled: bool):
        self._hotword_enabled = bool(enabled)
        write_env(self.env_path, {"HOTWORD_ENABLED": "1" if enabled else "0"})
        if enabled:
            self._start_hotword_listening()
        else:
            self._stop_hotword_listening()

    def closeEvent(self, event):
        """Останавливаем фоновые потоки/аудио перед закрытием, чтобы избежать segfault при выходе."""
        try:
            self._stop_speech_output()
        except Exception as e:
            logger.warning("stop_speech_output failed during close: %s", e)

        try:
            self._stop_hotword_listening()
        except Exception as e:
            logger.warning("hotword stop failed during close: %s", e)

        try:
            self._silence_timer.stop()
            self._hotword_timer.stop()
        except Exception:
            pass

        try:
            if self._asr_thread and self._asr_thread.isRunning():
                self._asr_thread.requestInterruption()
                self._asr_thread.quit()
                self._asr_thread.wait(1000)
        except Exception as e:
            logger.warning("ASR thread shutdown failed: %s", e)

        try:
            if self._hotword_thread and self._hotword_thread.isRunning():
                self._hotword_thread.requestInterruption()
                self._hotword_thread.quit()
                self._hotword_thread.wait(1000)
        except Exception as e:
            logger.warning("Hotword thread shutdown failed: %s", e)

        for rec in (getattr(self, "recorder", None), getattr(self, "hotword_recorder", None)):
            try:
                if rec:
                    rec.stop()
            except Exception:
                pass

        try:
            if getattr(self.agent, "tts", None):
                self.agent.tts.shutdown()
        except Exception as e:
            logger.warning("TTS shutdown failed: %s", e)

        super().closeEvent(event)

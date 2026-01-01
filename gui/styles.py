VIKA_QSS = r"""
/* Global */
QWidget { background: #0b0c10; color: #f2f2f7; font-size: 14px; }
*::focus { outline: none; border: none; }
QAbstractButton:focus { outline: none; border: none; }
QTextEdit:focus, QLineEdit:focus { outline: none; border: none; }

/* Tabs */
QTabWidget::pane { border: none; }
QTabBar::tab {
  background: transparent;
  color: rgba(242,242,247,0.65);
  padding: 10px 12px;
  margin-right: 8px;
}
QTabBar::tab:selected { color: rgba(242,242,247,0.92); }

/* Scroll */
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 10px 2px 10px 2px; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 0.18); border-radius: 5px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

/* Bubbles — БЕЗ ОБВОДКИ */
QFrame#UserBubble {
  background: rgba(10, 132, 255, 0.22);
  border: none;
  border-radius: 18px;
}
QFrame#BotBubble {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  border-radius: 18px;
}
QLabel#BubbleText { background: transparent; border: none; }

/* Main glass panel */
QFrame#Glass {
  background: rgba(255, 255, 255, 0.06);
  border: none;
  border-radius: 24px;
}

/* Input pill */
QFrame#InputPill {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  border-radius: 22px;
}
QTextEdit#Input {
  background: transparent;
  border: none;
  padding: 10px 12px;
  font-size: 14px;
}

/* Settings */
QComboBox, QLineEdit {
  background: rgba(255, 255, 255, 0.08);
  border: none;
  border-radius: 14px;
  padding: 10px 12px;
}
QComboBox::drop-down { border: none; }
QPushButton {
  background: rgba(10, 132, 255, 0.85);
  border: none;
  border-radius: 14px;
  padding: 10px 14px;
  font-weight: 700;
  color: #0b0c10;
}
QPushButton:hover { background: rgba(10, 132, 255, 1.0); }
QPushButton:disabled { background: rgba(255,255,255,0.15); color: rgba(242,242,247,0.35); }

QLabel#Title { font-size: 14px; color: rgba(242,242,247,0.72); }
QLabel#Status { font-size: 12px; color: rgba(242,242,247,0.52); }
QLabel#Hint { font-size: 12px; color: rgba(242,242,247,0.50); }
QLabel#Warn { font-size: 12px; color: rgba(255, 214, 10, 0.85); }
"""
# 🤖 Masha — Local AI Assistant for macOS

<p align="center">
  <a href="#-ru">🇷🇺 RU</a> •
  <a href="#-en">🇬🇧 EN</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" />
  <img src="https://img.shields.io/badge/Ollama-Local_LLM-black.svg" />
  <img src="https://img.shields.io/badge/macOS-supported-silver.svg" />
  <img src="https://img.shields.io/github/stars/Baggrisha/AI-Assistance?style=social" />
</p>

---

## 🇷🇺 RU

[🚀 Возможности](#-возможности) •
[💻 Установка](#-установка) •
[⚙️ Настройка](#-настройка-окружения) •
[▶️ Запуск](#-запуск) •
[🧩 Архитектура](#-архитектура-кратко) •
[⭐ Поддержать](#-поддержать-проект) •
[🇺🇸 EN](#-en)

---

**MASHA** — локальный ИИ-ассистент для macOS,  
ориентированный на приватность, локальное выполнение и гибкую настройку.

Ассистент объединяет:

- 🧠 **Локальные LLM через Ollama**
- 🗣 **TTS (озвучка ответов)**
- 🎤 **Поддержка активации по голосу**
- 🎯 **Интеллектуальный роутинг интентов**
- 🖥 **Графический интерфейс**
- ⚙️ **Модульную и расширяемую архитектуру**

Проект был создан из личного разочарования в возможностях стандартных голосовых ассистентов.  
Цель MASHA — быть умным, гибким и полностью локальным помощником, который даёт пользователю контроль,
а не навязывает ограничения.

---

## 🚀 Возможности

- 💬 Общение в свободной форме
- 🧠 Выполнение системных команд (open app, system actions и др.)
- 🔀 Интеллектуальный роутинг интентов (команда / диалог)
- 🔊 Озвучка ответов
- 🎙 Голосовой ввод через Hugging Face Whisper (ASR), активация по «привет, Маша» или просто «Маша»
- 🪟 GUI в стиле Siri / ChatGPT
- 🧩 Модульная архитектура
- 🛠 Простая замена модели LLM

---

## 📁 Структура проекта

```text
brain/
 ├─ client.py
 └─ support_model.py

core/
 ├─ actions.py
 ├─ agent.py
 ├─ intent_router.py
 └─ tts.py

gui/
 ├─ gui.py
 └─ styles.py

tools/
 ├─ env_tools.py
 ├─ promt.py
 ├─ system.py
 └─ utils.py

.env.example
main.py
````

> ⚠️ Файл `.env` **не хранится в репозитории**
> Используйте `.env.example` как шаблон.

---

## ⚙️ Установка

1) Клонировать репозиторий  
```bash
git clone https://github.com/Baggrisha/AI-Assistance.git
cd AI-Assistance
```
2) Установить зависимости  
```bash
pip install -r requirements.txt
brew install ollama
ollama pull gemma3:4b
```

---

## 🔑 Настройка окружения

1) Создайте `.env` на основе примера  
```bash
cp .env.example .env
```
2) Заполните основные переменные  
```env
MINI_MODEL="gemma3:4b"
MAIN_MODEL="gemma3:4b"
HF_TOKEN=TOKEN
VOICE_ENABLED="0"
HF_ASR_MODEL="ai-sage/GigaAM-v3"
HF_ASR_DEVICE="cpu"
```
3) HuggingFace токен (обязателен для ASR)  
   - Создайте токен: https://huggingface.co/settings/tokens (тип Read)  
   - Примите условия модели: https://huggingface.co/pyannote/segmentation-3.0  
   - Вставьте токен (начинается с `hf_`) в `HF_TOKEN`
4) ASR и микрофон  
   - Укажите `HF_ASR_MODEL` (по умолчанию `ai-sage/GigaAM-v3`) и `HF_TOKEN`, если модель приватная.  
   - Опционально задайте `HF_ASR_DEVICE` (`cpu`/`cuda`).
5) Ярлыки Shortcuts для таймера, секундомера и погоды (установите и выдайте все разрешения):  
   - Python Timer: https://www.icloud.com/shortcuts/dbf0c70ef9e942cb9ede0a7119409874  
   - Python Stopwatch: https://www.icloud.com/shortcuts/e91cb3e7233e48c5a564109d37cd1603  
   - Python Get Location: https://www.icloud.com/shortcuts/d726e7816d304742a3baa7f1d5e031fe

---

## ▶️ Запуск

```bash
python main.py
```

---

## 🧩 Архитектура (кратко)

* **agent.py** — главный контроллер
* **intent_router.py** — определяет: команда или диалог
* **actions.py** — системные действия
* **tts.py** — озвучка
* **gui/** — интерфейс
* **brain/** — работа с LLM
* **main.py** — точка входа

---

## 🛣 Планы развития

* [x] Голосовой ввод
* [x] Память диалога
* [x] Активация по голосу
* [ ] Добавить фоновую активность

---

## ⭐ Поддержать проект

Если вам понравился этот проект — **поставьте ему звездочку ⭐**
Это действительно помогает 🚀


<br>

---

## 🇬🇧 EN

[🚀 Features](#-features) •
[💻 Installation](#-installation) •
[⚙️ Setup](#-environment-setup) •
[▶️ Run](#-run) •
[🧠 Architecture](#-architecture-overview) •
[⭐ Support](#-support-the-project) •
[🇷🇺 RU](#-ru)

---

**MASHA** is a local AI assistant for macOS
focused on privacy, local execution, and full customization.

It combines:

* 🧠 **Local LLMs via Ollama**
* 🗣 **Text-to-Speech**
* 🎤 **Voice activation support**
* 🎯 **Intelligent intent routing**
* 🖥 **Graphical user interface**
* ⚙️ **Modular and extensible architecture**

---

## 🚀 Features

* 💬 Natural conversation
* 🧠 System command execution
* 🔀 Intelligent intent routing
* 🔊 Voice responses
* 🎙 Voice input powered by Hugging Face ASR (GigaAM), activation by "Привет, Маша" or just "Маша"
* 🪟 Siri / ChatGPT–style GUI
* 🧩 Modular architecture
* 🛠 Easy model switching

---

## ⚙️ Installation

1) Clone the repo  
```bash
git clone https://github.com/Baggrisha/AI-Assistance.git
cd AI-Assistance
```
2) Install dependencies  
```bash
pip install -r requirements.txt
brew install ollama
ollama pull gemma3:4b
```

---

## 🔑 Environment Setup

1) Copy the example env  
```bash
cp .env.example .env
```
2) Fill key variables  
```env
MINI_MODEL="gemma3:4b"
MAIN_MODEL="gemma3:4b"
HF_TOKEN=TOKEN
VOICE_ENABLED="0"
HF_ASR_MODEL="ai-sage/GigaAM-v3"
HF_ASR_DEVICE="cpu"  # or cuda, if available
```
3) HuggingFace token (required for ASR)  
   - Create a token: https://huggingface.co/settings/tokens (type Read)  
   - Accept model terms: https://huggingface.co/pyannote/segmentation-3.0  
   - Paste the token (starts with `hf_`) into `HF_TOKEN`
4) ASR and mic  
   - Set `HF_ASR_MODEL` (default `ai-sage/GigaAM-v3`) and `HF_TOKEN` if the model is private.  
   - Optionally set `HF_ASR_DEVICE` (`cpu`/`cuda`).
5) Shortcuts for timer, stopwatch, and local weather — install and grant all permissions:  
   - Python Timer: https://www.icloud.com/shortcuts/dbf0c70ef9e942cb9ede0a7119409874  
   - Python Stopwatch: https://www.icloud.com/shortcuts/e91cb3e7233e48c5a564109d37cd1603  
   - Python Get Location: https://www.icloud.com/shortcuts/d726e7816d304742a3baa7f1d5e031fe


---

## ▶️ Run

```bash
python main.py
```

---

## 🧠 Architecture Overview

* **agent.py** — core orchestrator
* **intent_router.py** — command vs dialogue
* **actions.py** — system actions
* **tts.py** — voice output
* **gui/** — UI layer
* **brain/** — LLM interaction
* **main.py** — entry point

---

## 🛣 Development Plans
* [x] Voice
* [x] Memory of Dialogue
* [x] Voice Activation
* [ ] Add background activity

---

## ⭐ Support the Project

If you like this project — **give it a star ⭐**
It really helps 🚀

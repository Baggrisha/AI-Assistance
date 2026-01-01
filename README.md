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
- 🎯 **Интеллектуальный роутинг интентов**
- 🖥 **Графический интерфейс**
- ⚙️ **Модульную и расширяемую архитектуру**
- ⭐ **Поддержка проекта** — если вам понравился проект, поставьте ему звёздочку на GitHub, это действительно помогает развитию

Проект был создан из личного разочарования в возможностях стандартных голосовых ассистентов.  
Цель MASHA — быть умным, гибким и полностью локальным помощником, который даёт пользователю контроль,
а не навязывает ограничения.

---

## 🚀 Возможности

- 💬 Общение в свободной форме
- 🧠 Выполнение системных команд (open app, system actions и др.)
- 🔀 Интеллектуальный роутинг интентов (команда / диалог)
- 🔊 Озвучка ответов
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

### 1. Клонировать репозиторий

```bash
git clone https://github.com/Baggrisha/AI-Assistance.git
cd AI-Assistance
```

### 2. Установить зависимости

```bash
pip install -r requirements.txt
```

### 3. Установить Ollama

```bash
brew install ollama
```

Скачать модель:

```bash
ollama pull gemma3:4b
```

---

## 🔑 Настройка окружения

Создайте файл `.env` на основе примера:

```bash
cp .env.example .env
```

Пример содержимого:

```env
MINI_MODEL="gemma3:4b"
MAIN_MODEL="gemma3:4b"
HF_TOKEN=TOKEN
VOICE_ENABLED="0"
```

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

* [ ] Голосовой ввод
* [ ] Память диалога
* [ ] Активация по голосу

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
* 🎯 **Intelligent intent routing**
* 🖥 **Graphical user interface**
* ⚙️ **Modular and extensible architecture**

---

## 🚀 Features

* 💬 Natural conversation
* 🧠 System command execution
* 🔀 Intelligent intent routing
* 🔊 Voice responses
* 🪟 Siri / ChatGPT–style GUI
* 🧩 Modular architecture
* 🛠 Easy model switching

---

## ⚙️ Installation

```bash
git clone https://github.com/Baggrisha/AI-Assistance.git
cd AI-Assistance
pip install -r requirements.txt
brew install ollama
ollama pull gemma3:4b
```

---

## 🔑 Environment Setup

```bash
cp .env.example .env
```

```env
MINI_MODEL="gemma3:4b"
MAIN_MODEL="gemma3:4b"
HF_TOKEN=TOKEN
VOICE_ENABLED="0"
```

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
* [ ] Voice
* [ ] Memory of Dialogue
* [ ] Voice Activation

---

## ⭐ Support the Project

If you like this project — **give it a star ⭐**
It really helps 🚀

```


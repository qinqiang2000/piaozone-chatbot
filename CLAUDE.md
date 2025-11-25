# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This project is a knowledge base integration center (piaozone-chatbot) that connects Yuque (knowledge base) with various communication channels (Yunzhijia, ZhiChi, etc.) via LLMs. It handles data synchronization, Q&A/Search, and feedback loops.

## Commands
- **Run Server**: `python src/app.py` (runs on port 9999)
- **Install Dependencies**: `pip install -r requirements.txt`
- **Database Setup**: Run SQL commands from `sql.txt` in MySQL
- **Run Tests**:
  - `python test/test_flow.py` (Test sync flow)
  - `python test/test_yq.py` (Test Yuque integration)
  - `python test/test-assitant.py` (Test Assistant)

## Architecture
- **Framework**: FastAPI (`src/app.py` is the entry point).
- **Core Modules**:
  - `src/handlers/`: Adapters for different platforms (Yunzhijia, ZhiChi, Simple).
  - `src/qa_assistant/`: LLM integration logic (OpenAI/Azure OpenAI wrappers).
  - `src/sync/`: Logic for synchronizing content from Yuque to Vector DBs/Assistants.
  - `src/utils/`: Common utilities including `ConfigManager` and `SQLDatabase`.
- **Configuration**:
  - Managed by `ConfigManager`.
  - Keys in `.env`.
  - Settings in `config/settings.py`.
  - Dynamic config via Yuque webhook integration.
- **Data Flow**: Request -> `app.py` -> `Handler` -> `Assistant` -> `LLM` -> Response.
- **Async Tasks**: Uses `APScheduler` and `Celery` for periodic synchronization and auto-entry tasks.

## Code Style
- **Python**: Follows standard PEP 8 guidelines.
- **Type Hinting**: Use `typing` module (e.g., `List`, `Dict`, `Optional`) where possible.
- **Imports**: Absolute imports preferred (e.g., `from src.utils.logger import logger`).
- **Logging**: Use `src.utils.logger`.

# AGENTS.md

This file serves as a guide for AI agents working on the `ha-indygo-pool` project. Follow these instructions to ensure consistency, quality, and maintainability.

## 🧠 Philosophy & Principles

- **KISS (Keep It Simple, Stupid)**: Avoid over-engineering. Solutions should be simple and easy to understand.
- **DRY (Don't Repeat Yourself)**: Reuse code where possible. Extract common logic into helper functions or classes.
- **Modern Home Assistant Architecture**: Follow the latest [Home Assistant Developer Docs](https://developers.home-assistant.io/). Use `DataUpdateCoordinator` for polling, config flows for setup, and standard entity platforms.
- **Test-Driven Mental Model**: Always verify changes. If you break it, you buy it.

## 🛠️ Technology Stack

- **Language**: Python 3.12+ (Type Hinting is MANDATORY)
- **Dependency Management**: [uv](https://github.com/astral-sh/uv)
- **Containerization**: Docker & Docker Compose
- **Linting & Formatting**: `ruff`
- **Testing**: `pytest`

## 📂 Project Structure & Responsibilities

- **`api.py`**: Contains **ALL** core logic for interacting with the MyIndygo API. No Home Assistant code here.
- **`coordinator.py`**: Handles data fetching and caching using `DataUpdateCoordinator`. Maps API data to a format usable by entities.
- **`sensor.py` / `binary_sensor.py`**: Entity platform definitions. Should be thin wrappers around data from the coordinator.
- **`config_flow.py`**: Handles integration setup and option flows.
- **`strings.json`**: Contains ALL user-facing strings (labels, descriptions, errors). **NEVER** hardcode strings in Python files.
- **`tests/`**: Contains `pytest` tests. Mirror the source structure.

## 🔄 Development Workflow

1.  **Understand the Goal**: Read the user request and existing code.
2.  **Plan**: If complex, create an `implementation_plan.md`.
3.  **Implement**: Make changes following the structure above.
4.  **Verify**:
    -   **MUST** run tests: `uv run pytest tests`
    -   **MUST** lint/format: `uv run pre-commit run --all-files`
5.  **Commit**: Use Conventional Commits (e.g., `feat: add pool light control`, `fix: handle api timeout`).

## ✅ Quality Assurance Checklist

Before telling the user you are done, YOU MUST:

- [ ] **Run Tests**: `uv run pytest tests` -> ALL PASSING.
- [ ] **Lint**: `uv run ruff check .` -> NO ERRORS.
- [ ] **Format**: `uv run ruff format .` -> NO CHANGES NEEDED.
- [ ] **Type Check**: ensure no obvious type errors (Python is dynamically typed but use hints).

## 📚 References

- `CONTRIBUTING.md`: Setup and contribution details.
- `README.md`: project overview and usage.

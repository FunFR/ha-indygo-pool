# AGENTS.md

This file serves as a guide for AI agents working on the `ha-indygo-pool` project. Follow these instructions to ensure consistency, quality, and maintainability.

## 🧠 Philosophy & Principles

- **KISS (Keep It Simple, Stupid)**: Avoid over-engineering. Solutions should be simple and easy to understand.
- **DRY (Don't Repeat Yourself)**: Reuse code where possible. Extract common logic into helper functions or classes.
- **Modern Home Assistant Architecture**: Follow the latest [Home Assistant Developer Docs](https://developers.home-assistant.io/). Use `DataUpdateCoordinator` for polling, config flows for setup, and standard entity platforms.
  - **HTTP Requests**: ALWAYS use `homeassistant.helpers.aiohttp_client.async_create_clientsession` or `async_get_clientsession` instead of instantiating `aiohttp.ClientSession` directly.
  - **Entity Translations**: Use `translation_key` in entity descriptions. DO NOT hardcode English strings in the `name` attribute of EntityDescriptions if a translation key is present.
  - **Constants**: Use native HA constants (e.g., `UnitOfTime.HOURS`) instead of hardcoded strings whenever possible.
- **Test-Driven Mental Model**: Always verify changes. If you break it, you buy it.

## 📂 Project Structure & Responsibilities

- **`api.py`**: Contains **ALL** core logic for interacting with the MyIndygo API. No Home Assistant code here.
- **`coordinator.py`**: Handles data fetching and caching using `DataUpdateCoordinator`. Maps API data to a format usable by entities.
- **`entity.py`**: Base entity class to share `CoordinatorEntity` logic and `device_info` across all platforms.
- **`sensor.py` / `binary_sensor.py`**: Entity platform definitions. Should be thin wrappers around data from the coordinator.
- **`config_flow.py`**: Handles integration setup and option flows.
- **`diagnostics.py`**: Generates diagnostic data for easier troubleshooting.
- **`strings.json`**: Contains ALL user-facing strings (labels, descriptions, errors). **NEVER** hardcode strings in Python files.
- **`tests/`**: Contains `pytest` tests. Mirror the source structure.

## 🔄 Development Workflow

1.  **Understand the Goal**: Read the user request and existing code.
2.  **Plan**: If complex, create an `implementation_plan.md`.
3.  **Implement**: Make changes following the structure above.
4.  **Verify & Commit**: You **MUST** follow the QA Checklist (testing, linting, formatting) and Tech Stack constraints defined in [CONTRIBUTING.md](CONTRIBUTING.md).
    - **Conventional Commits**: Use `feat:`, `fix:`, `refactor:`, etc., for SemVer.
    - **Breaking Changes**: ONLY flag a commit as a breaking change (`!`) if it fundamentally breaks the user's HA configuration (e.g., removing an entity entirely, changing the integration domain, or altering required config steps).

## 📚 References

- [`CONTRIBUTING.md`](CONTRIBUTING.md): Technology stack, development environment setup, and mandatory quality assurance commands.
- [`README.md`](README.md): Project overview, features, and usage.

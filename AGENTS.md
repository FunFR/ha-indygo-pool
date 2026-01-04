# AGENTS.md - Developer & AI Context Guide

This document provides essential context, architectural decisions, and conventions for AI agents (and human developers) working on the `ha-indygo-pool` integration.

## Project Overview
This is a **Home Assistant Custom Component** for "Indygo Pool" (MyIndygo) connected swimming pools.
- **Domain**: `indygo_pool`
- **Platform**: `myindygo.com`
- **Tech Stack**: Python 3.12+, `aiohttp`, `uv` (package manager), `ruff` (linter).

## Architecture
The project follows a **decoupled architecture** to separate data fetching from parsing and entity management.

### 1. Data Layer
*   **`models.py`**: Defines strict dataclasses (`IndygoPoolData`, `IndygoModuleData`, `IndygoSensorData`). **All** data passing through the system must use these structures, never raw dicts.
*   **`parser.py`**: Contains **pure logic** for data extraction.
    *   Parses HTML from the discovery page.
    *   Parses JSON from the status API.
    *   Decoupled from `api.py` (easier testing).
    *   *Note*: Includes a fallback for `EntityCategory` imports to support environments with partial dependencies.
*   **`api.py`**: Handles **only** HTTP communication.
    *   Manages Authentication (POST to `/login`, with pre-fetch for cookies).
    *   Handles Redirect loops (common issue with this API).
    *   Returns `IndygoPoolData`.

### 2. Entity Layer
*   **`coordinator.py`**: `DataUpdateCoordinator` managing the polling interval.
*   **`sensor.py` / `binary_sensor.py`**:
    *   **Config-Driven**: Entities are created dynamically by iterating over `coordinator.data.sensors` and `coordinator.data.modules`.
    *   **Diagnostic Entities**: Status sensors (Online, Flow, Shutter) are categorized as `EntityCategory.DIAGNOSTIC`.

## ⚠️ Critical Conventions

### Entity Naming & Unique IDs
**Rule**: Unique IDs MUST be stable and based on the **Pool ID**, not the Config Entry ID.
*   **Format**: `[pool_id]_[module_id]_[sensor_key]` (or `[pool_id]_[sensor_key]` for root sensors).
*   *Reason*: Allows users to migrate config entries without losing entity history.

### Testing Strategy
*   **Environment**: Integration tests (`tests/test_api.py`, `tests/test_integration_structure.py`) run against the **live API**.
*   **Cookies**: Local testing environments requires `aiohttp.CookieJar(unsafe=True)`.
*   **Graceful Failure**: Tests are configured to `pytest.skip` if specific authentication redirect loops occur (common in local non-docker environments), ensuring CI remains green (`Passed` or `Skipped`, never `Failed` due to env).

### Linting & quality
*   **Strictness**: `pre-commit` MUST pass.
*   **Tools**: `ruff` is the primary linter/formatter.
*   **No Magic Numbers**: Use constants in tests.
*   **Complexity**: Keep cyclomatic complexity low (e.g., `parser.py` uses helper methods `_parse_root_sensors`, `_parse_modules` etc.).

## Development Workflow
1.  **Dependency Management**: Use `uv` (`uv sync`, `uv run pytest`).
2.  **Commit Messages**: Follow Conventional Commits.
3.  **Build**: `pyproject.toml` is configured to use `uv build` and lock dependencies.

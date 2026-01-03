# Contributing to Indygo Pool

This document outlines how to set up your development environment and contribute to the **Indygo Pool** integration.

## 🛠️ Development Environment

### Prerequisites

- [Python 3.9+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Git](https://git-scm.com/)

### Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/FunFR/ha-indygo-pool.git
   cd ha-indygo-pool
   ```

2. **Sync dependencies and environment**:
   ```bash
   uv sync --all-extras
   ```

3. **Install Playwright browsers**:
   ```bash
   uv run playwright install chromium
   ```

4. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

## 🧪 Testing

### Automated Tests

We use `pytest` for testing. Run tests with:

```bash
uv run pytest tests
```

### Integration Testing (Real Credentials)

To run tests against the real MyIndygo API, create a `.env` file in the root directory:

```env
email=your_email@example.com
password=your_password
pool_id=your_pool_id
```

Then run the integration tests using:

```bash
uv run pytest -s -m integration tests
```

### Manual Config Testing

To test the integration in a local Home Assistant environment:

1. Create a `config` directory in the root of the project.
2. Link the custom component:
   ```bash
   mkdir -p config/custom_components
   ln -s $(pwd)/custom_components/indygo_pool config/custom_components/indygo_pool
   ```
3. Run Home Assistant pointing to this config:
   ```bash
   uv run hass -c config
   ```

### Remote Deployment (Real HAOS)

To quickly deploy your local changes to a remote Home Assistant instance (e.g., HAOS on a VM/Pi) without committing to Git:

```bash
scp -r custom_components/indygo_pool root@<HA_IP>:/config/custom_components/
```

> **Note**: This requires the **SSH & Web Terminal** add-on in Home Assistant.

After copying, **restart Home Assistant** to apply changes.

## ✨ Code Quality

We use `ruff` for linting and formatting.

- **Check**: `uv run ruff check .`
- **Fix**: `uv run ruff check --fix .`
- **Format**: `uv run ruff format .`

### Pre-commit

We use `pre-commit` to ensure code quality before every commit.

1. **Install hooks**:
   ```bash
   uv run pre-commit install
   ```

2. **Run manually**:
   ```bash
   uv run pre-commit run --all-files
   ```

## 🤝 Contributing Process

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add some amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

## 🤖 Automated Maintenance

This repository uses **Renovate** to keep dependencies up to date automatically.

- **Runtime Dependencies**: Renovate updates use the `fix` scope (e.g., `fix(deps): ...`), which **triggers a new patch release** via Semantic Release. HACS users will see an update.
- **Dev/CI Dependencies**: Renovate updates use the `chore` or `ci` scope (e.g., `chore(deps): ...`), which **does NOT trigger a release**. The codebase is updated, but HACS users are not spammed with updates for internal changes.
- **Auto-merge**: Minor and patch updates are automatically merged if the CI passes.

### Development Workflow

1. Keep API logic in `api.py`.
2. Map data in `coordinator.py`.
3. Add entities in the respective platform files (`sensor.py`, `binary_sensor.py`, etc.).
4. Always update `strings.json` if you add new configuration options or entities.

# Contributing to Indygo Pool

This document outlines how to set up your development environment and contribute to the **Indygo Pool** integration.

For project architecture, design philosophy, and AI agent instructions, please refer to [AGENTS.md](AGENTS.md).
For features and installation instructions, see [README.md](README.md).

## Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's reporting a bug, discussing code, or submitting a pull request. Github is used for everything.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code passes tests and lints.
4. Issue that pull request!

## 🛠️ Technology Stack & Environment

- **Language**: Python 3.12+ (Type Hinting is MANDATORY)
- **Dependency Management**: [uv](https://docs.astral.sh/uv/)
- **Linting & Formatting**: `ruff`
- **Testing**: `pytest`
- **Containerization**: Docker & Docker Compose

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

3. **Install pre-commit hooks**:
   ```bash
   uv run pre-commit install
   ```

## ✅ Quality Assurance Checklist

Before telling the user you are done or submitting a PR, YOU MUST ensure:

- [ ] **Tests Pass**: `uv run pytest tests`
- [ ] **Linting is Clean**: `uv run ruff check .`
- [ ] **Code is Formatted**: `uv run ruff format .`
- [ ] **Types are Checked**: Ensure no obvious type errors (Python is dynamically typed but use hints).

## 🧪 Testing

### Automated Tests
Run tests with:
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

### Manual Config Testing (Docker)
1. Start the Home Assistant container: `docker compose up -d`
2. Access Home Assistant at [http://localhost:8123](http://localhost:8123).
3. View logs: `docker compose logs -f`
4. Stop container: `docker compose down`

The `docker-compose.yml` file maps the `custom_components/indygo_pool` directory into the container. Restart HA to reflect code changes.

### Remote Deployment (Real HAOS)
To quickly deploy local changes to a remote Home Assistant instance without Git:
```bash
scp -r custom_components/indygo_pool root@<HA_IP>:/config/custom_components/
```
> **Note**: Requires the **SSH & Web Terminal** add-on in Home Assistant. Restart HA to apply changes.

## ✨ Code Quality Fixes

- **Check**: `uv run ruff check .`
- **Fix**: `uv run ruff check --fix .`
- **Format**: `uv run ruff format .`
- **Pre-commit**: `uv run pre-commit run --all-files`

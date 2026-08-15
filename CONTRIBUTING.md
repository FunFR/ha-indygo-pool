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

- **Language**: Python 3.14.2+ (Type Hinting is MANDATORY)
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
uv run pytest -s -m integration tests --no-cov
```

### Sharing Diagnostics

When reporting a bug or requesting support for unknown hardware, include the integration diagnostics:

1. Go to **Settings → Devices & Services → Indygo Pool**
2. Click the **⋮** menu → **Download diagnostics**
3. Attach the JSON to your GitHub issue

The diagnostics include raw module data (`inputs`, `outputs`, `ipxData`) that reveals what sensors and controls each hardware device exposes, without requiring physical access to the hardware.

> **Before sharing:** review the JSON and remove anything you consider sensitive. The integration filters common PII fields (email, address, coordinates, MAC address, etc.), but cannot determine what is confidential for you.

### Manual Config Testing (Docker)
1. Start the Home Assistant container: `docker compose up -d`
2. Access Home Assistant at [http://localhost:8123](http://localhost:8123).
3. View logs: `docker compose logs -f`
4. Stop container: `docker compose down`

The `docker-compose.yml` file maps the `custom_components/indygo_pool` directory into the container. Restart HA to reflect code changes.

#### Verifying the integration is healthy

1. **Logs**: check the setup and every coordinator refresh succeeded, no traceback:
   ```bash
   docker compose logs --since 20m | grep -i "indygo\|error\|traceback\|exception"
   ```
   Look for `Setting up indygo_pool`, `Finished fetching indygo_pool data ... (success: True)`, and the absence of any `ERROR`/`Traceback` line.
2. **Entity states via the REST API**: create a Home Assistant long-lived access token (Profile → Security → "Create Long-Lived Access Token") and store it as `ha_token` in `.env` (see `.env.example`), then:
   ```bash
   export HA_TOKEN=$(grep '^ha_token=' .env | cut -d= -f2)
   curl -s -H "Authorization: Bearer $HA_TOKEN" http://localhost:8123/api/states \
     | jq -r '.[] | select(.attributes.attribution=="Data provided by MyIndygo") | "\(.entity_id)\t\(.state)"'
   unset HA_TOKEN
   ```
   All `indygo_pool` entities should have a populated state; none should be `unavailable` or `unknown`.

`ha_token` authenticates against this local dev HA instance only, unrelated to the `email`/`password`/`pool_id` credentials above, which authenticate against the real MyIndygo API.

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

## 🚀 Release Process

Merges batch into one running draft ([Release Drafter](.github/workflows/release-drafter.yml)), published manually when ready:

1. Publish the draft under [Releases](https://github.com/FunFR/ha-indygo-pool/releases). Defaults to **pre-release** (HACS beta channel) for a few days of testing.
2. Edit the same release, uncheck "Set as a pre-release" to promote it to latest.

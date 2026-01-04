# Contributing to Indygo Pool

This document outlines how to set up your development environment and contribute to the **Indygo Pool** integration.

## Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

### Github is used for everything

Github is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (using pre-commit).
4. Test your contribution.
5. Issue that pull request!

## 🛠️ Development Environment

### Prerequisites

- [Python 3.9+](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Git](https://git-scm.com/)
- [Docker](https://www.docker.com/)
- [Docker Compose](https://docs.docker.com/compose/)

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

### Manual Config Testing (Docker)

To test the integration in a local Home Assistant environment using Docker:

1. Start the Home Assistant container:
   ```bash
   docker compose up -d
   ```

2. Access Home Assistant at [http://localhost:8123](http://localhost:8123).

3. To view logs:
   ```bash
   docker compose logs -f
   ```

4. To stop the container:
   ```bash
   docker compose down
   ```

The `docker-compose.yml` file is already configured to map the `custom_components/indygo_pool` directory into the container, so any code changes you make will be reflected after a restart.

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

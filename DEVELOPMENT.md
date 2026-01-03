# Development

This document outlines how to set up your development environment for the **Indygo Pool** integration.

## 🛠️ Development Environment

The recommended way to develop for Home Assistant is using [Visual Studio Code](https://code.visualstudio.com/) with the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension.

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Getting Started

1. **Clone the repository**:
   ```bash
   git clone https://github.com/brice.messeca/ha-indygo-pool.git
   cd ha-indygo-pool
   ```

2. **Open in VS Code**:
   ```bash
   code .
   ```

3. **Dev Container**:
   - Ensure the **Dev Containers** extension is installed.
   - Open the Command Palette (`Cmd+Shift+P` on Mac, `Ctrl+Shift+P` on Windows/Linux).
   - Type and select: **"Dev Containers: Reopen in Container"**.

## 🧪 Testing

### Automated Tests

We use `pytest` for testing. Run unit tests with:

```bash
pytest tests
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
# In Dev Container or Local Env
pytest -s tests/test_api.py
```

*Note: The `pytest-homeassistant-custom-component` plugin might block external network access by default. If you encounter `socket.socket` errors, you can run tests with `-p no:homeassistant_custom_component`.*

### Troubleshooting

#### DNS Issues in Docker/Linux
If you encounter errors like `Channel.getaddrinfo() takes 3 positional arguments...`, it is likely due to a conflict between `aiohttp` and `aiodns` in certain environments. You can resolve this by uninstalling `aiodns`:

```bash
pip uninstall aiodns pycares -y
```

### Manual Testing

To test the integration in a real Home Assistant environment:

1. Create a `config` directory in the root of the project.
2. Link the custom component:
   ```bash
   mkdir -p config/custom_components
   ln -s $(pwd)/custom_components/indygo_pool config/custom_components/indygo_pool
   ```
3. Run Home Assistant pointing to this config:
   ```bash
   hass -c config
   ```

## ✨ Code Quality

We use `ruff` for linting and formatting.

- **Check**: `ruff check .`
- **Fix**: `ruff check --fix .`
- **Format**: `ruff format .`

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add some amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

### Development Workflow

1. Keep API logic in `api.py`.
2. Map data in `coordinator.py`.
3. Add entities in the respective platform files (`sensor.py`, `binary_sensor.py`, etc.).
4. Always update `strings.json` if you add new configuration options or entities.

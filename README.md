# Indygo Pool for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Last Commit][last-commit-shield]][repo]
[![GitHub Issues][issues-shield]][issues]
[![HACS][hacs-shield]][hacs]
[![CI][ci-shield]][ci]

Indygo Pool is a custom integration for Home Assistant that allows you to monitor your MyIndygo connected pool solution.

## Features

- **Temperature Monitoring**: Keep an eye on your pool's water temperature.
- **pH & Salt levels**: Monitor the chemical balance of your pool.
- **Electrolyser Status**: Monitor the production status.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance.
2. Click on the three dots in the top right corner and select "Custom repositories".
3. Add the URL of this repository and select "Integration" as the category.
4. Click "Add" and then install the "Indygo Pool" integration.
5. Restart Home Assistant.

### Manual

1. Download the latest release.
2. Copy the `indygo_pool` directory from `custom_components` to your Home Assistant `config/custom_components` directory.
3. Restart Home Assistant.

## Configuration

Add the integration: [![Add Integration][add-integration-badge]][add-integration]

1. Go to **Settings** > **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Indygo Pool**.
4. Enter your MyIndygo credentials (email, password) and your **Pool ID**.
    > The **Pool ID** can be found in the URL after logging into myindygo.com (e.g., `https://myindygo.com/pools/<Pool ID>/devices`).

## Disclaimer

This integration is not affiliated with or endorsed by MyIndygo. It uses a scraper to retrieve data from the MyIndygo website. Use it at your own risk.

## Support

If you found this integration helpful, feel free to buy me a coffee!

<a href="https://buymeacoffee.com/funfr" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

[hacs]: https://github.com/hacs/integration
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg
[last-commit-shield]: https://img.shields.io/github/last-commit/FunFR/ha-indygo-pool
[releases]: https://github.com/FunFR/ha-indygo-pool/releases
[releases-shield]: https://img.shields.io/github/release/FunFR/ha-indygo-pool.svg
[repo]: https://github.com/FunFR/ha-indygo-pool
[issues]: https://github.com/FunFR/ha-indygo-pool/issues
[issues-shield]: https://img.shields.io/github/issues/FunFR/ha-indygo-pool.svg
[ci]: https://github.com/FunFR/ha-indygo-pool/actions/workflows/ci.yml
[ci-shield]: https://github.com/FunFR/ha-indygo-pool/actions/workflows/ci.yml/badge.svg
[add-integration]: https://my.home-assistant.io/redirect/config_flow_start/?domain=indygo_pool
[add-integration-badge]: https://my.home-assistant.io/badges/config_flow_start.svg

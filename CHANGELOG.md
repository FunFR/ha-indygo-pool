# CHANGELOG

<!-- version list -->

## v2.3.1 (2026-03-28)

### Bug Fixes

- Switch to OAuth2 API to fix pump mode transitions (On↔Auto)
  ([#100](https://github.com/FunFR/ha-indygo-pool/pull/100),
  [`1565aa0`](https://github.com/FunFR/ha-indygo-pool/commit/1565aa0cb90109954dd1af664b2f3fb83fbf3dbb))

### Continuous Integration

- **deps**: Update actions/stale action to v10
  ([#99](https://github.com/FunFR/ha-indygo-pool/pull/99),
  [`b4e05ff`](https://github.com/FunFR/ha-indygo-pool/commit/b4e05ffdf254860cd5b231f893a961b93dcbc4e8))


## v2.3.0 (2026-03-28)

### Features

- Simplify codebase with shared helpers, cached state, and stale workflow
  ([#98](https://github.com/FunFR/ha-indygo-pool/pull/98),
  [`f428a9f`](https://github.com/FunFR/ha-indygo-pool/commit/f428a9fa3e2734d9f867583d9c1789eb43a22271))


## v2.2.0 (2026-03-28)

### Chores

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 4c1d99a
  ([#91](https://github.com/FunFR/ha-indygo-pool/pull/91),
  [`dbbf871`](https://github.com/FunFR/ha-indygo-pool/commit/dbbf871aaf39031551a25b17c6bc89705276c945))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 9166820
  ([#92](https://github.com/FunFR/ha-indygo-pool/pull/92),
  [`bd9ca16`](https://github.com/FunFR/ha-indygo-pool/commit/bd9ca1645a1579e4a67e7a6d84069f1fc8d65c64))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.8
  ([#96](https://github.com/FunFR/ha-indygo-pool/pull/96),
  [`1232279`](https://github.com/FunFR/ha-indygo-pool/commit/1232279a0986948059683423265c6610a53677e4))

### Continuous Integration

- **deps**: Pin dependencies ([#93](https://github.com/FunFR/ha-indygo-pool/pull/93),
  [`6147444`](https://github.com/FunFR/ha-indygo-pool/commit/614744428a5688d6fad08875ef19ea24bd7edaac))

- **deps**: Update codecov/codecov-action action to v6
  ([#94](https://github.com/FunFR/ha-indygo-pool/pull/94),
  [`fcc7884`](https://github.com/FunFR/ha-indygo-pool/commit/fcc78841521507e492dae9382c3b7d07e3cdf101))

- **deps**: Update codecov/codecov-action digest to 75cd116
  ([#95](https://github.com/FunFR/ha-indygo-pool/pull/95),
  [`a9dd2db`](https://github.com/FunFR/ha-indygo-pool/commit/a9dd2dbf0d7db282f2fc1ed18c81b803d7f8d2a9))

### Features

- Expose filtration schedule and remaining time from Auto mode
  ([#97](https://github.com/FunFR/ha-indygo-pool/pull/97),
  [`e45f329`](https://github.com/FunFR/ha-indygo-pool/commit/e45f329bb0a582c3c265197accb3ea7b194e0aa1))


## v2.1.2 (2026-03-21)

### Bug Fixes

- Add state_class to ph and ph_setpoint sensors
  ([#90](https://github.com/FunFR/ha-indygo-pool/pull/90),
  [`f361a03`](https://github.com/FunFR/ha-indygo-pool/commit/f361a03a5d1f22f1e86ee84602dde5f6c8b43d6a))

- Treat ph/ph_setpoint as floats and fix via_device warning
  ([#90](https://github.com/FunFR/ha-indygo-pool/pull/90),
  [`f361a03`](https://github.com/FunFR/ha-indygo-pool/commit/f361a03a5d1f22f1e86ee84602dde5f6c8b43d6a))


## v2.1.1 (2026-03-21)

### Continuous Integration

- Remove redundant coverage comment action ([#89](https://github.com/FunFR/ha-indygo-pool/pull/89),
  [`d3420e2`](https://github.com/FunFR/ha-indygo-pool/commit/d3420e25bc406d78977ba11f61e7f759fedab9cd))

- **deps**: Pin dependencies
  ([`925806f`](https://github.com/FunFR/ha-indygo-pool/commit/925806f3c33e8415d31334d833de366224de5d21))

### Refactoring

- Clean up dead code, unused deps, and translations
  ([#89](https://github.com/FunFR/ha-indygo-pool/pull/89),
  [`d3420e2`](https://github.com/FunFR/ha-indygo-pool/commit/d3420e25bc406d78977ba11f61e7f759fedab9cd))


## v2.1.0 (2026-03-21)

### Chores

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.7
  ([`5a18e80`](https://github.com/FunFR/ha-indygo-pool/commit/5a18e8036529cc1dd0234fd19559a14eac50e38c))

### Documentation

- Refactor documentation to avoid duplication
  ([`7bbb5a0`](https://github.com/FunFR/ha-indygo-pool/commit/7bbb5a02f19eea62eced2714b4f1b4e8260971bb))

### Features

- Add CI coverage reporting with codecov and PR comments
  ([`b9ac128`](https://github.com/FunFR/ha-indygo-pool/commit/b9ac128852d8b099c85b479d9434c306583ff60c))

- Reach 94% test coverage and stabilize test suite
  ([`7a9e7e1`](https://github.com/FunFR/ha-indygo-pool/commit/7a9e7e19db8f36e503a85cb079620e385ec62d27))

### Refactoring

- Use async_create_clientsession and rely on pure entity translations
  ([`0921492`](https://github.com/FunFR/ha-indygo-pool/commit/09214926ffb3ac714cd5e2dd7513ff64744e2586))


## v2.0.1 (2026-03-20)

### Bug Fixes

- Force English entity_id slugs regardless of user language
  ([`24b7e94`](https://github.com/FunFR/ha-indygo-pool/commit/24b7e94add62905028dbeafd1c3948716b028690))


## v2.0.0 (2026-03-20)

### Features

- Overhaul multi-device architecture and merge filtration sensors
  ([`6658fe6`](https://github.com/FunFR/ha-indygo-pool/commit/6658fe6c8b2e122c806ef6f932f54c87b6bab57b))

### Breaking Changes

- - Migrated entities to segmented devices by module ID (IPX, LR-PC, etc.).


## v1.3.5 (2026-03-20)

### Bug Fixes

- Enable strict mode in semantic-release to fail on errors
  ([`e92d901`](https://github.com/FunFR/ha-indygo-pool/commit/e92d901719668f955e68ee4d5d902b3f32709873))

### Chores

- **deps**: Lock file maintenance
  ([`b4aba88`](https://github.com/FunFR/ha-indygo-pool/commit/b4aba88b4a34b912c68b9e1cb2edee68dce3150b))

### Continuous Integration

- **deps**: Update actions/create-github-app-token action to v3
  ([`303a264`](https://github.com/FunFR/ha-indygo-pool/commit/303a264dd88a0c04c10f31539cfce951246d8c55))


## v1.3.4 (2026-03-20)

### Bug Fixes

- Include refactor in semantic release config to trigger release
  ([`f0db192`](https://github.com/FunFR/ha-indygo-pool/commit/f0db192b9dea3cec9e1b3f0b1484547f26133be0))

### Refactoring

- Apply HA best practices for entities, naming and translations
  ([`3c9c0da`](https://github.com/FunFR/ha-indygo-pool/commit/3c9c0da50e1edf38af6341f7e4757985e4ae7b3d))


## v1.3.3 (2026-03-19)

### Bug Fixes

- Extract correct water temperature from sensorState
  ([`f116d9a`](https://github.com/FunFR/ha-indygo-pool/commit/f116d9a596f0e8bc0fdef0ea7b3f2c15ea34e69f))

### Chores

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 572a5d0
  ([#77](https://github.com/FunFR/ha-indygo-pool/pull/77),
  [`265f108`](https://github.com/FunFR/ha-indygo-pool/commit/265f1087a08ad44ff8fc6f2aeed0b25d5d297619))

### Continuous Integration

- **deps**: Update astral-sh/setup-uv digest to 37802ad
  ([#78](https://github.com/FunFR/ha-indygo-pool/pull/78),
  [`9afdc1c`](https://github.com/FunFR/ha-indygo-pool/commit/9afdc1c7a84dca61c413bd8b9d9fb342783777c3))


## v1.3.2 (2026-03-17)

### Bug Fixes

- Restore IPX electrolyzer data and correct shutter sensor logic
  ([`914f48a`](https://github.com/FunFR/ha-indygo-pool/commit/914f48a4ae20f06e5ccd3fc3bbce372608afc673))

### Chores

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 0e091df
  ([#70](https://github.com/FunFR/ha-indygo-pool/pull/70),
  [`9e9c783`](https://github.com/FunFR/ha-indygo-pool/commit/9e9c7836d9095a4784f1d473573711c10aaa0b0a))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 17441c4
  ([#56](https://github.com/FunFR/ha-indygo-pool/pull/56),
  [`207f4ab`](https://github.com/FunFR/ha-indygo-pool/commit/207f4ab172bc6255d1943f477fb800d3f79ba5c2))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 3e2dff5
  ([#60](https://github.com/FunFR/ha-indygo-pool/pull/60),
  [`50d90f2`](https://github.com/FunFR/ha-indygo-pool/commit/50d90f241d478ae8fd2754d3a4212dee256990ae))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 4fb4ad8
  ([#68](https://github.com/FunFR/ha-indygo-pool/pull/68),
  [`04e9491`](https://github.com/FunFR/ha-indygo-pool/commit/04e94911a0a3496ea4800b6b53317d5a252c7124))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 96fa92d
  ([#64](https://github.com/FunFR/ha-indygo-pool/pull/64),
  [`b656324`](https://github.com/FunFR/ha-indygo-pool/commit/b65632483ae94cd0c130e8a10cf1690eb17a731b))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.1
  ([#59](https://github.com/FunFR/ha-indygo-pool/pull/59),
  [`64c023d`](https://github.com/FunFR/ha-indygo-pool/commit/64c023d2690e15771259cea0ed9f6e2ce64400f2))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.2
  ([#63](https://github.com/FunFR/ha-indygo-pool/pull/63),
  [`49444f5`](https://github.com/FunFR/ha-indygo-pool/commit/49444f5303272d1f08808dbc48ba7ef3a1dc6ae2))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.4
  ([#66](https://github.com/FunFR/ha-indygo-pool/pull/66),
  [`9982599`](https://github.com/FunFR/ha-indygo-pool/commit/99825990689c3da5dac5207029f763052b4080d5))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.5
  ([#69](https://github.com/FunFR/ha-indygo-pool/pull/69),
  [`c24b9ea`](https://github.com/FunFR/ha-indygo-pool/commit/c24b9eaabc344f2b3e01a556da955228f7682007))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.6
  ([#74](https://github.com/FunFR/ha-indygo-pool/pull/74),
  [`4f1d69c`](https://github.com/FunFR/ha-indygo-pool/commit/4f1d69ca61dd6f2027bcb7611c3f0e8960ffae53))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.6
  ([#57](https://github.com/FunFR/ha-indygo-pool/pull/57),
  [`7919678`](https://github.com/FunFR/ha-indygo-pool/commit/79196781d0e33156ea7743a7d096b18fe68934a1))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.7
  ([#58](https://github.com/FunFR/ha-indygo-pool/pull/58),
  [`e721f6e`](https://github.com/FunFR/ha-indygo-pool/commit/e721f6e27e1b83badc245a9c94db695089a9bfe4))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.8
  ([#62](https://github.com/FunFR/ha-indygo-pool/pull/62),
  [`71829ec`](https://github.com/FunFR/ha-indygo-pool/commit/71829ec0f8682db30becbdf494519c2798f31408))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.9
  ([#65](https://github.com/FunFR/ha-indygo-pool/pull/65),
  [`504b8c7`](https://github.com/FunFR/ha-indygo-pool/commit/504b8c725c39e7a10b5804ced592b57551568b22))

### Continuous Integration

- **deps**: Update actions/create-github-app-token digest to fee1f7d
  ([#75](https://github.com/FunFR/ha-indygo-pool/pull/75),
  [`339e990`](https://github.com/FunFR/ha-indygo-pool/commit/339e990096900a1f40d1c440e325416bee4da86d))

- **deps**: Update astral-sh/setup-uv digest to 5a095e7
  ([#67](https://github.com/FunFR/ha-indygo-pool/pull/67),
  [`bb9ac7b`](https://github.com/FunFR/ha-indygo-pool/commit/bb9ac7b3a4fbdb4049053981970f9b4a0d05b4c3))

- **deps**: Update astral-sh/setup-uv digest to 6ee6290
  ([#71](https://github.com/FunFR/ha-indygo-pool/pull/71),
  [`723bab7`](https://github.com/FunFR/ha-indygo-pool/commit/723bab7830c8fc729e9095967fd6f3fcd55a9e1b))

- **deps**: Update astral-sh/setup-uv digest to e06108d
  ([#73](https://github.com/FunFR/ha-indygo-pool/pull/73),
  [`dc3d7ed`](https://github.com/FunFR/ha-indygo-pool/commit/dc3d7edce4b81de65f44d0316436b1e0c7c217a4))


## v1.3.1 (2026-02-07)

### Bug Fixes

- Pump activation with session management
  ([`7d130f1`](https://github.com/FunFR/ha-indygo-pool/commit/7d130f13db96d6d2f4bc6f1ada69305747c04d2b))

### Continuous Integration

- **deps**: Update astral-sh/setup-uv digest to eac588a
  ([#54](https://github.com/FunFR/ha-indygo-pool/pull/54),
  [`57c3929`](https://github.com/FunFR/ha-indygo-pool/commit/57c392916850b4b423d74fc723925821f09c2c50))


## v1.3.0 (2026-02-06)

### Chores

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 043ab74
  ([#51](https://github.com/FunFR/ha-indygo-pool/pull/51),
  [`6c12ae0`](https://github.com/FunFR/ha-indygo-pool/commit/6c12ae0e024b14afaec8a24553a386c4796fcba0))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 3007eee
  ([#40](https://github.com/FunFR/ha-indygo-pool/pull/40),
  [`dd1e2e3`](https://github.com/FunFR/ha-indygo-pool/commit/dd1e2e357242302a3c642a0b67cb19c1b6ea0f14))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to bf1602f
  ([#36](https://github.com/FunFR/ha-indygo-pool/pull/36),
  [`6911ebb`](https://github.com/FunFR/ha-indygo-pool/commit/6911ebbae7144a48dd033165fde932b1705fcc55))

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to c367414
  ([#45](https://github.com/FunFR/ha-indygo-pool/pull/45),
  [`b85afcd`](https://github.com/FunFR/ha-indygo-pool/commit/b85afcd9f00588bd0eb5eb97b5e7b3fb8a8765ee))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.14.13
  ([#38](https://github.com/FunFR/ha-indygo-pool/pull/38),
  [`a0e8930`](https://github.com/FunFR/ha-indygo-pool/commit/a0e8930f843093c39143dac78beeb9b66547a347))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.14.14
  ([#44](https://github.com/FunFR/ha-indygo-pool/pull/44),
  [`ee56ee6`](https://github.com/FunFR/ha-indygo-pool/commit/ee56ee60efa22576df2fe655e5f77c952574bd13))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.15.0
  ([#49](https://github.com/FunFR/ha-indygo-pool/pull/49),
  [`6be4077`](https://github.com/FunFR/ha-indygo-pool/commit/6be40774036666650a9caef6c7accf4a1bf172af))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.11.3
  ([#37](https://github.com/FunFR/ha-indygo-pool/pull/37),
  [`0bbe02f`](https://github.com/FunFR/ha-indygo-pool/commit/0bbe02f71041a337cb5ec798a47ddd7f02129acc))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.11.6
  ([#39](https://github.com/FunFR/ha-indygo-pool/pull/39),
  [`280f091`](https://github.com/FunFR/ha-indygo-pool/commit/280f091debe6fc68beb31658a02ad096452992fa))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.12.0
  ([#41](https://github.com/FunFR/ha-indygo-pool/pull/41),
  [`358cae7`](https://github.com/FunFR/ha-indygo-pool/commit/358cae7b2b6d08ef73053a4be08583d1ca195808))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.12.1
  ([#43](https://github.com/FunFR/ha-indygo-pool/pull/43),
  [`cb3239f`](https://github.com/FunFR/ha-indygo-pool/commit/cb3239fa98d9077e99a86c36bd91917648e7893d))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.2
  ([#47](https://github.com/FunFR/ha-indygo-pool/pull/47),
  [`0085ddd`](https://github.com/FunFR/ha-indygo-pool/commit/0085ddd41c69105a7da323b15e00e49b97841f97))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.4
  ([#50](https://github.com/FunFR/ha-indygo-pool/pull/50),
  [`497b09f`](https://github.com/FunFR/ha-indygo-pool/commit/497b09fb312faa65a9ab37f8627d3e0423a67538))

- **deps**: Update pre-commit hook commitizen-tools/commitizen to v4.13.5
  ([#52](https://github.com/FunFR/ha-indygo-pool/pull/52),
  [`c614b21`](https://github.com/FunFR/ha-indygo-pool/commit/c614b21181473c22286c622a846ca95e019b335a))

### Continuous Integration

- **deps**: Update actions/checkout digest to de0fac2
  ([#48](https://github.com/FunFR/ha-indygo-pool/pull/48),
  [`f6d36d3`](https://github.com/FunFR/ha-indygo-pool/commit/f6d36d3d4478938a670bd1a9d63834a1888ae22d))

- **deps**: Update actions/setup-python digest to a309ff8
  ([#42](https://github.com/FunFR/ha-indygo-pool/pull/42),
  [`87a85df`](https://github.com/FunFR/ha-indygo-pool/commit/87a85df6c174d3339c5020ce638f0b885b81f2c9))

- **deps**: Update astral-sh/setup-uv digest to 803947b
  ([#46](https://github.com/FunFR/ha-indygo-pool/pull/46),
  [`7732826`](https://github.com/FunFR/ha-indygo-pool/commit/773282691f3deb0f6873f28d105b2f2d2a6cdc55))

### Features

- Implement full cloud synchronization sequence for filtration modes
  ([`04e54e6`](https://github.com/FunFR/ha-indygo-pool/commit/04e54e6260ccf536353b9fbb5522e41108674bf4))


## v1.2.0 (2026-01-10)

### Features

- Add last_measurement_time to temperature and refactor parser
  ([`9276685`](https://github.com/FunFR/ha-indygo-pool/commit/927668577fff6db4d7b160bf7e7d92706abc1dbe))

### Refactoring

- Simplify api client implementation
  ([`eacc5cc`](https://github.com/FunFR/ha-indygo-pool/commit/eacc5cc8957eb9f874580c7bdb97347ab806b41c))


## v1.1.0 (2026-01-10)

### Chores

- **deps**: Update ghcr.io/home-assistant/home-assistant:stable docker digest to 97d63b3
  ([#32](https://github.com/FunFR/ha-indygo-pool/pull/32),
  [`221013b`](https://github.com/FunFR/ha-indygo-pool/commit/221013bf589c54ece3e37bfe1d14b9460528eb18))

- **deps**: Update pre-commit hook astral-sh/ruff-pre-commit to v0.14.11
  ([#33](https://github.com/FunFR/ha-indygo-pool/pull/33),
  [`d26bac9`](https://github.com/FunFR/ha-indygo-pool/commit/d26bac9e0abb66efef21639ac77d64688b8e9f66))

### Continuous Integration

- **deps**: Update astral-sh/setup-uv digest to 61cb8a9
  ([#30](https://github.com/FunFR/ha-indygo-pool/pull/30),
  [`be4e85f`](https://github.com/FunFR/ha-indygo-pool/commit/be4e85fd4836fc0f3676327b64a52992dc35325d))

### Features

- Add pH latest sensor parsing and timestamp attribute
  ([`ba86e13`](https://github.com/FunFR/ha-indygo-pool/commit/ba86e131ab2508dcca4d5b2cb1a72b9eedf36ff6))

### Refactoring

- Rename entity_id by simplifying device name
  ([`d063ee9`](https://github.com/FunFR/ha-indygo-pool/commit/d063ee96050da3f4cb5e88c6e1b79561d1148626))


## v1.0.12 (2026-01-07)

### Bug Fixes

- Refresh scraped data and pool_id in unique_id
  ([`282c207`](https://github.com/FunFR/ha-indygo-pool/commit/282c207209415fc8d1d14562ecf9625869659e6f))

- **config_flow**: Prevent duplicate entries with unique_id
  ([`282c207`](https://github.com/FunFR/ha-indygo-pool/commit/282c207209415fc8d1d14562ecf9625869659e6f))

- **entity**: Enforce Indygo Pool prefix in device name
  ([`282c207`](https://github.com/FunFR/ha-indygo-pool/commit/282c207209415fc8d1d14562ecf9625869659e6f))

- **entity**: Remove unavailable pool name and use pool_id fallback
  ([`282c207`](https://github.com/FunFR/ha-indygo-pool/commit/282c207209415fc8d1d14562ecf9625869659e6f))

- **entity**: Use dynamic pool name for device and unique_id
  ([`282c207`](https://github.com/FunFR/ha-indygo-pool/commit/282c207209415fc8d1d14562ecf9625869659e6f))

- **sensors**: Refresh scraped data and add filtration status
  ([`282c207`](https://github.com/FunFR/ha-indygo-pool/commit/282c207209415fc8d1d14562ecf9625869659e6f))


## v1.0.11 (2026-01-05)

### Bug Fixes

- **release**: Use publish-action for asset upload
  ([#27](https://github.com/FunFR/ha-indygo-pool/pull/27),
  [`6fba9c9`](https://github.com/FunFR/ha-indygo-pool/commit/6fba9c96ab691079390e9d43ea470deac16f8cb4))


## v1.0.10 (2026-01-05)

### Bug Fixes

- **release**: Move dist_glob_patterns to publish section
  ([#26](https://github.com/FunFR/ha-indygo-pool/pull/26),
  [`75af88b`](https://github.com/FunFR/ha-indygo-pool/commit/75af88bd89cc70177332aca0ca809c44dafc9a7c))


## v1.0.9 (2026-01-05)

### Bug Fixes

- **release**: Use semantic-release for zip upload, remove race condition
  ([#25](https://github.com/FunFR/ha-indygo-pool/pull/25),
  [`9b35be1`](https://github.com/FunFR/ha-indygo-pool/commit/9b35be1e39a3101aaa2e30fc60a15988d1d8f1da))


## v1.0.8 (2026-01-05)

### Bug Fixes

- Use app token for release asset upload ([#24](https://github.com/FunFR/ha-indygo-pool/pull/24),
  [`96f03a5`](https://github.com/FunFR/ha-indygo-pool/commit/96f03a5865e993da5d90838334282d749fd31099))


## v1.0.7 (2026-01-05)

### Bug Fixes

- Resolve stale data issue
  ([`8823141`](https://github.com/FunFR/ha-indygo-pool/commit/882314107fb2bc51acf746e2a68d06b914e51780))


## v1.0.6 (2026-01-05)

### Bug Fixes

- **release**: Upload asset to release
  ([`e29208a`](https://github.com/FunFR/ha-indygo-pool/commit/e29208a13fd9a86bc31f43fb86da16bb84e2d1bb))


## v1.0.5 (2026-01-05)

### Bug Fixes

- **ci**: Add id to semantic release step
  ([`870c1c9`](https://github.com/FunFR/ha-indygo-pool/commit/870c1c9413219286c5c5e702b818f4bae74ef0aa))


## v1.0.4 (2026-01-05)

### Bug Fixes

- **release**: Use dist directory for zip and separate publish action
  ([`b65009f`](https://github.com/FunFR/ha-indygo-pool/commit/b65009f6de69d7f54a50601199a91ad6c8acb3de))


## v1.0.3 (2026-01-05)

### Bug Fixes

- Improve HACS compliance and CI
  ([`9847688`](https://github.com/FunFR/ha-indygo-pool/commit/984768832e195dc721736ef8760d9ce8b6f586a5))

- **release**: Use python script for zip generation
  ([`cc9c212`](https://github.com/FunFR/ha-indygo-pool/commit/cc9c212057a2a6e698f527cecac6296a5ac0b755))


## v1.0.2 (2026-01-05)

### Bug Fixes

- Align const.py version with project version and configure semantic-release
  ([`990c45d`](https://github.com/FunFR/ha-indygo-pool/commit/990c45d89eda761ac901ecafa23d75103d993c8e))


## v1.0.1 (2026-01-05)

### Bug Fixes

- Temporarily disable the control feature until it is working properly
  ([`be6c67b`](https://github.com/FunFR/ha-indygo-pool/commit/be6c67b8dfdc48e05f39d4aeca991f4f9f38e9dc))

### Continuous Integration

- **deps**: Pin dependencies
  ([`88a1419`](https://github.com/FunFR/ha-indygo-pool/commit/88a1419e80fc4b37a028a148500df7be45be6935))

- **deps**: Update actions/setup-python action to v6
  ([`50b2b9d`](https://github.com/FunFR/ha-indygo-pool/commit/50b2b9dc9a492c59399091e23570fc319b184d19))

- **deps**: Update astral-sh/setup-uv action to v7
  ([`6c49f86`](https://github.com/FunFR/ha-indygo-pool/commit/6c49f863930ff209a9efb448da74d07c212dcf4e))


## v1.0.0 (2026-01-04)

### Continuous Integration

- **deps**: Update actions/create-github-app-token action to v2
  ([`790a35d`](https://github.com/FunFR/ha-indygo-pool/commit/790a35da9eb5156549089a0fb832e22ac60c6233))

- **deps**: Update python-semantic-release/python-semantic-release action to v10
  ([`f05568d`](https://github.com/FunFR/ha-indygo-pool/commit/f05568d06f31d5f57bb70bc2950e0131c030bd6b))

### Refactoring

- Decouple api/sensors and update docs
  ([`060c619`](https://github.com/FunFR/ha-indygo-pool/commit/060c61948e4591486df951dca9e74959f17bf8fb))


## v0.2.0 (2026-01-04)

### Continuous Integration

- **deps**: Pin dependencies
  ([`9ba9024`](https://github.com/FunFR/ha-indygo-pool/commit/9ba9024ed7e821aa809b1fa26452faa553811cb7))

- **deps**: Update actions/checkout action to v6
  ([`f3baa3a`](https://github.com/FunFR/ha-indygo-pool/commit/f3baa3a172df1667b92949a55bf594b6a1aa110d))

### Features

- Migrate to direct API client and standardize developer workflow
  ([`b8f4b97`](https://github.com/FunFR/ha-indygo-pool/commit/b8f4b970e051a9a618eb4ff0f659b9bf8018ccb2))


## v0.1.0 (2026-01-03)

- Initial Release

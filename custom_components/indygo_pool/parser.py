"""Parser for Indygo Pool data."""

from __future__ import annotations

import json
import logging
import re
from enum import Enum

try:
    from homeassistant.const import EntityCategory
except ImportError:
    # Fallback for environments where EntityCategory is not available (e.g. old tests)
    class EntityCategory(str, Enum):
        """Entity category."""

        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"


from .models import IndygoModuleData, IndygoPoolData, IndygoSensorData

_LOGGER = logging.getLogger(__name__)


class IndygoParser:
    """Parser for Indygo Pool data."""

    @staticmethod
    def extract_json_object(text: str, start_index: int) -> str | None:
        """Extract a JSON object from text starting at start_index.

        This handles nested braces correctly to extract a full JSON object string
        embedded within JavaScript.
        """
        brace_count = 0
        in_string = False
        escape = False

        for i in range(start_index, len(text)):
            char = text[i]

            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    return text[start_index : i + 1]

        return None

    def parse_pool_ids(
        self, html: str, pool_id: str
    ) -> tuple[str | None, str | None, dict]:
        """Parse HTML to find pool address and relay ID.

        Returns:
            Tuple of (pool_address, relay_id, pool_metadata_dict)
        """
        pool_metadata = {}
        pool_address = None
        relay_id = None

        # Extract currentPool
        start_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*currentPool\s*=\s*(\{)", re.IGNORECASE
        )
        match = start_regex.search(html)
        if match:
            start_index = match.start(1)
            json_str = self.extract_json_object(html, start_index)
            if json_str:
                try:
                    pool_metadata = json.loads(json_str)
                except json.JSONDecodeError as exc:
                    _LOGGER.error("Failed to decode currentPool JSON: %s", exc)

        if not pool_metadata:
            # Basic validation
            return None, None, {}

        # Logic: Prioritize lr-pc (gateway + relay ID)
        if "modules" in pool_metadata:
            modules = pool_metadata["modules"]

            # 1. Try to find gateway (lr-mb-10)
            gateway = next((m for m in modules if m.get("type") == "lr-mb-10"), None)

            # 2. Try to find main device (lr-pc)
            lr_pc = next((m for m in modules if m.get("type") == "lr-pc"), None)

            if lr_pc:
                if not gateway:
                    # Fallback: assume lr-pc is gateway if no dedicated gateway found
                    gateway = lr_pc

                pool_address = gateway.get("serialNumber")

                # Relay ID from lr-pc
                name_parts = lr_pc.get("name", "").split("-")
                if len(name_parts) > 1:
                    relay_id = name_parts[-1]
                else:
                    relay_id = lr_pc.get("serialNumber")[-6:]

            else:
                # Fallback for IPX only
                ipx = next((m for m in modules if m.get("type") == "ipx"), None)
                if ipx:
                    pool_address = ipx.get("serialNumber")
                    relay_id = ipx.get("ipxRelay")
                else:
                    _LOGGER.error(
                        "No compatible module (lr-pc or ipx) found in modules list."
                    )

        return pool_address, relay_id, pool_metadata

    def parse_ipx_module(self, html: str) -> dict:
        """Parse HTML to find ipxModule data (embedded JS)."""
        ipx_metadata = {}
        ipx_start_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*ipxModule\s*=\s*(\{)", re.IGNORECASE
        )
        ipx_match = ipx_start_regex.search(html)
        if ipx_match:
            ipx_start_index = ipx_match.start(1)
            ipx_json_str = self.extract_json_object(html, ipx_start_index)
            if ipx_json_str:
                try:
                    ipx_metadata = json.loads(ipx_json_str)
                except json.JSONDecodeError as exc:
                    _LOGGER.error("Failed to decode ipxModule JSON: %s", exc)
        return ipx_metadata

    def parse_data(
        self, json_data: dict, pool_id: str, pool_address: str, relay_id: str
    ) -> IndygoPoolData:
        """Parse the API response into a structured IndygoPoolData object."""
        pool_data = IndygoPoolData(
            pool_id=pool_id, address=pool_address, relay_id=relay_id, raw_data=json_data
        )

        self._parse_root_sensors(json_data, pool_data)
        self._parse_sensor_state(json_data, pool_data)
        self._parse_modules(json_data, pool_data)
        self._parse_scraped_ipx(json_data, pool_data)

        return pool_data

    def _parse_root_sensors(self, json_data: dict, pool_data: IndygoPoolData) -> None:
        """Parse root level sensors."""
        # Map simple keys directly
        root_sensors_map = {
            "temperature": ("Water Temperature", "temperature", "°C"),
            "ph": ("pH", "ph", None),
            "redox": ("Redox", None, "mV"),
            "orp": ("ORP", None, "mV"),
            "salt": ("Salt", None, "g/L"),
            "chlorineRate": ("Chlorine", None, "ppm"),
        }

        for key, (name, device_class, unit) in root_sensors_map.items():
            if key in json_data and json_data[key] is not None:
                pool_data.sensors[key] = IndygoSensorData(
                    key=key,
                    name=name,
                    value=json_data[key],
                    unit=unit,
                    device_class=device_class,
                )

    def _parse_sensor_state(self, json_data: dict, pool_data: IndygoPoolData) -> None:
        """Parse sensorState (legacy/generic list)."""
        if "sensorState" in json_data and isinstance(json_data["sensorState"], list):
            for sensor_item in json_data["sensorState"]:
                idx = sensor_item.get("index")
                val = sensor_item.get("value")
                if idx == 0 and val is not None:
                    # Water Temp override or backup - DUPLICATE
                    # User requested removal of duplicate. Logic commented out.
                    # pool_data.sensors["water_temp_sensor_state"] = IndygoSensorData(
                    #     key="water_temp_sensor_state",
                    #     name="Water Temperature (Sensor State)",
                    #     value=val / 100.0,
                    #     unit="°C",
                    #     device_class="temperature",
                    #     entity_category="diagnostic",
                    # )
                    pass

    def _parse_modules(self, json_data: dict, pool_data: IndygoPoolData) -> None:
        """Parse modules list."""
        if "modules" in json_data:
            for module in json_data["modules"]:
                m_id = module.get("id")
                m_type = module.get("type", "unknown")
                m_name = module.get("name", f"Module {m_id}")

                indygo_module = IndygoModuleData(
                    id=str(m_id), type=m_type, name=m_name, raw_data=module
                )

                # IPX Data
                if m_type == "ipx" and "ipxData" in module:
                    ipx_data = module["ipxData"]
                    if "totalElectrolyseDuration" in ipx_data:
                        indygo_module.sensors["totalElectrolyseDuration"] = (
                            IndygoSensorData(
                                key="totalElectrolyseDuration",
                                name="Electrolyse Duration",
                                value=ipx_data["totalElectrolyseDuration"],
                                unit="h",
                                entity_category=EntityCategory.DIAGNOSTIC,
                            )
                        )

                pool_data.modules[str(m_id)] = indygo_module

    def _parse_scraped_ipx(self, json_data: dict, pool_data: IndygoPoolData) -> None:
        """Parse scraped ipx_module data."""
        if "ipx_module" in json_data:
            ipx_mod = json_data["ipx_module"]
            outputs = ipx_mod.get("outputs", [])

            # Helper to safely get nested
            def get_nested(obj, *keys):
                for k in keys:
                    if not isinstance(obj, (dict, list)):
                        return None
                    if isinstance(obj, list):
                        try:
                            obj = obj[int(k)]
                        except (IndexError, ValueError):
                            return None
                    else:
                        obj = obj.get(k)
                return obj

            # Salt
            salt = get_nested(outputs, 1, "ipxData", "saltValue")
            if salt is not None:
                pool_data.sensors["ipx_salt"] = IndygoSensorData(
                    key="ipx_salt", name="Salt Level (IPX)", value=salt, unit="g/L"
                )

            # pH Setpoint
            ph_set = get_nested(outputs, 0, "ipxData", "pHSetpoint")
            if ph_set is not None:
                pool_data.sensors["ph_setpoint"] = IndygoSensorData(
                    key="ph_setpoint", name="pH Setpoint", value=ph_set, unit=None
                )

            # Production Setpoint
            prod_set = get_nested(outputs, 1, "ipxData", "percentageSetpoint")
            if prod_set is not None:
                pool_data.sensors["production_setpoint"] = IndygoSensorData(
                    key="production_setpoint",
                    name="Production Setpoint",
                    value=prod_set,
                    unit="%",
                )

            # Electrolyzer Mode
            elec_mode = get_nested(outputs, 1, "ipxData", "electrolyzerMode")
            if elec_mode is not None:
                pool_data.sensors["electrolyzer_mode"] = IndygoSensorData(
                    key="electrolyzer_mode",
                    name="Electrolyzer Mode",
                    value=elec_mode,
                    unit=None,
                    entity_category=EntityCategory.DIAGNOSTIC,
                )

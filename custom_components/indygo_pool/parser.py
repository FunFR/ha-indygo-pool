"""Parser for Indygo Pool data."""

from __future__ import annotations

import json
import logging
import re
from enum import Enum

try:
    from enum import StrEnum
except ImportError:
    # Python < 3.11 fallback
    class StrEnum(str, Enum):  # noqa: UP042
        pass


from .const import PROGRAM_TYPE_FILTRATION
from .models import IndygoModuleData, IndygoPoolData, IndygoSensorData

_LOGGER = logging.getLogger(__name__)


IPX_PH_SENSOR_TYPE = 6


class IndygoParser:
    """Parser for Indygo Pool data."""

    @staticmethod
    def extract_json_object(text: str, start_index: int) -> str | None:
        """Extract a JSON object or array from text starting at start_index.

        This handles nested braces/brackets correctly to extract a full JSON
        object or array string embedded within JavaScript.
        """
        brace_count = 0
        in_string = False
        escape = False
        open_char = None
        close_char = None

        # Find the first opening brace/bracket
        for i in range(start_index, len(text)):
            if text[i] in "{[":
                open_char = text[i]
                close_char = "}" if open_char == "{" else "]"
                start_index = i
                break

        if not open_char:
            return None

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
            elif char == open_char:
                brace_count += 1
            elif char == close_char:
                brace_count -= 1
                if brace_count == 0:
                    return text[start_index : i + 1]

        return None

    def _extract_device_ids(self, lr_pc: dict) -> tuple[str | None, str | None]:
        """Extract device short ID and relay ID from lr-pc module.

        Returns:
            Tuple of (device_short_id, relay_id)
        """
        # Device Short ID: from name suffix or last 6 chars of serial
        name_parts = lr_pc.get("name", "").split("-")
        if len(name_parts) > 1:
            device_short_id = name_parts[-1]
        else:
            device_short_id = lr_pc.get("serialNumber", "")[-6:]

        # Relay ID: from relay field, fallback to device_short_id
        relay_id = lr_pc.get("relay") or device_short_id

        return device_short_id, relay_id

    def _parse_lr_pc_module(
        self, modules: list[dict]
    ) -> tuple[str | None, str | None, str | None]:
        """Parse lr-pc module to extract pool address and IDs.

        Returns:
            Tuple of (pool_address, device_short_id, relay_id)
        """
        gateway = next((m for m in modules if m.get("type") == "lr-mb-10"), None)
        lr_pc = next((m for m in modules if m.get("type") == "lr-pc"), None)

        if not lr_pc:
            return None, None, None

        # Use lr-pc as gateway if no dedicated gateway found
        if not gateway:
            gateway = lr_pc

        pool_address = gateway.get("serialNumber")
        device_short_id, relay_id = self._extract_device_ids(lr_pc)

        return pool_address, device_short_id, relay_id

    def _parse_ipx_module(
        self, modules: list[dict]
    ) -> tuple[str | None, str | None, str | None]:
        """Parse IPX module as fallback.

        Returns:
            Tuple of (pool_address, device_short_id, relay_id)
        """
        ipx = next((m for m in modules if m.get("type") == "ipx"), None)
        if not ipx:
            return None, None, None

        pool_address = ipx.get("serialNumber")
        device_short_id = ipx.get("ipxRelay")
        relay_id = device_short_id  # For IPX, they're the same

        return pool_address, device_short_id, relay_id

    def parse_pool_ids(
        self, html: str, pool_id: str
    ) -> tuple[str | None, str | None, str | None, dict]:
        """Parse HTML to find pool address, device short ID, and relay ID.

        Returns:
            Tuple of (pool_address, device_short_id, relay_id, pool_metadata_dict)
        """
        # Extract currentPool JSON
        start_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*currentPool\s*=\s*([{\[])", re.IGNORECASE
        )
        match = start_regex.search(html)

        json_str = None
        pool_metadata = {}

        if match:
            start_index = match.start(1)
            json_str = self.extract_json_object(html, start_index)

        if json_str:
            try:
                pool_metadata = json.loads(json_str)
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode currentPool JSON: %s", exc)
                return None, None, None, {}
        else:
            # Fallback to modulesInPool
            modules_regex = re.compile(
                r"(?:var|let|const|window\.)?\s*modulesInPool\s*=\s*(\[)", re.IGNORECASE
            )
            match = modules_regex.search(html)
            if match:
                start_index = match.start(1)
                json_str = self.extract_json_object(html, start_index)
                if json_str:
                    try:
                        modules_list = json.loads(json_str)
                        pool_metadata = {"modules": modules_list}
                    except json.JSONDecodeError as exc:
                        _LOGGER.error("Failed to decode modulesInPool JSON: %s", exc)
                        return None, None, None, {}

        if not pool_metadata:
            return None, None, None, {}

        # Extract module information
        modules = pool_metadata.get("modules", [])
        if not modules:
            return None, None, None, {}

        # Try lr-pc first, fallback to IPX
        pool_address, device_short_id, relay_id = self._parse_lr_pc_module(modules)
        if not pool_address:
            pool_address, device_short_id, relay_id = self._parse_ipx_module(modules)

        if not pool_address:
            _LOGGER.error("No compatible module (lr-pc or ipx) found in modules list.")

        return pool_address, device_short_id, relay_id, pool_metadata

    def parse_ipx_module(self, html: str) -> dict:
        """Parse HTML to find ipxModule data (embedded JS)."""
        ipx_metadata = {}

        # 1. Search for poolTechModulesIpx (contains outputs for electrolyzer settings)
        pooltech_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*poolTechModulesIpx\s*=\s*(\[)",
            re.IGNORECASE,
        )
        match = pooltech_regex.search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                modules_list = json.loads(json_str)
                for m in modules_list:
                    if m.get("type", "").startswith("ipx"):
                        ipx_metadata = m
                        return ipx_metadata
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode poolTechModulesIpx JSON: %s", exc)

        # 2. Search for ipxModule (legacy single object)
        ipx_start_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*ipxModule\s*=\s*(\{)", re.IGNORECASE
        )
        match = ipx_start_regex.search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                ipx_metadata = json.loads(json_str)
                return ipx_metadata
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode ipxModule JSON: %s", exc)

        # 3. Fallback to modulesInPool (new general module list but misses outputs)
        modules_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*modulesInPool\s*=\s*(\[)", re.IGNORECASE
        )
        match = modules_regex.search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                modules_list = json.loads(json_str)
                for m in modules_list:
                    if m.get("type", "").startswith("ipx"):
                        ipx_metadata = m
                        break
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode modulesInPool JSON: %s", exc)

        return ipx_metadata

    def parse_programs_from_html(self, html: str) -> dict[str, list[dict]]:
        """Parse programs from embedded HTML JSON."""
        programs_map: dict[str, list[dict]] = {}

        # Regex for 'const poolCommand'
        regex = re.compile(
            r"(?:var|let|const|window\.)?\s*poolCommand\s*=\s*(\{)", re.IGNORECASE
        )
        match = regex.search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                data = json.loads(json_str)
                programs = data.get("programs", [])
                if isinstance(programs, list):
                    for prog in programs:
                        if m_id := prog.get("module"):
                            programs_map.setdefault(m_id, []).append(prog)
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode poolCommand JSON: %s", exc)
            return programs_map

        # Fallback to modulesInPool
        modules_regex = re.compile(
            r"(?:var|let|const|window\.)?\s*modulesInPool\s*=\s*(\[)", re.IGNORECASE
        )
        match = modules_regex.search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                for m in json.loads(json_str):
                    programs = m.get("programs", [])
                    m_id = str(m.get("id", ""))
                    if programs and m_id:
                        programs_map[m_id] = programs
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode modulesInPool JSON: %s", exc)
        return programs_map

    def parse_data(
        self,
        json_data: dict,
        pool_id: str,
        pool_address: str,
        relay_id: str,
        scraped_programs: dict[str, list[dict]] | None = None,
    ) -> IndygoPoolData:
        """Parse the API response into a structured IndygoPoolData object."""
        pool_data = IndygoPoolData(
            pool_id=pool_id, address=pool_address, relay_id=relay_id, raw_data=json_data
        )

        self._parse_root_sensors(json_data, pool_data)
        self._parse_sensor_state(json_data, pool_data)
        self._parse_modules(json_data, pool_data, scraped_programs)
        # self._parse_modules called twice in original code? Removing duplicate call.
        self._parse_scraped_ipx(json_data, pool_data)
        self._parse_pool_status_list(json_data, pool_data)

        return pool_data

    def _parse_pool_status_list(
        self, json_data: dict, pool_data: IndygoPoolData
    ) -> None:
        """Parse 'pool' list which contains status for Filtration, etc."""
        if "pool" in json_data and isinstance(json_data["pool"], list):
            for item in json_data["pool"]:
                idx = item.get("index")
                val = item.get("value")

                # Index 0 is Filtration
                if idx == 0:
                    pool_data.pool_status["0"] = IndygoSensorData(
                        key="filtration_status",
                        value=val,
                        extra_attributes={
                            "info": item.get("info"),
                            "time": item.get("time"),
                            "tempRef": item.get("tempRef"),
                        },
                    )

    def _parse_root_sensors(self, json_data: dict, pool_data: IndygoPoolData) -> None:
        """Parse root level sensors."""
        root_sensors_map = {
            "temperature": {
                "attributes": {"temperatureTime": "last_measurement_time"},
            },
        }

        for key, config in root_sensors_map.items():
            if key in json_data and json_data[key] is not None:
                extra_attributes = {}
                # Handle attributes mapping
                attr_map = config.get("attributes", {})
                for source_key, target_key in attr_map.items():
                    if source_key in json_data:
                        extra_attributes[target_key] = json_data[source_key]

                pool_data.sensors[key] = IndygoSensorData(
                    key=key,
                    value=json_data[key],
                    extra_attributes=extra_attributes,
                )

    def _parse_sensor_state(self, json_data: dict, pool_data: IndygoPoolData) -> None:
        """Parse sensorState (legacy/generic list)."""
        if "sensorState" in json_data and isinstance(json_data["sensorState"], list):
            for sensor_item in json_data["sensorState"]:
                idx = sensor_item.get("index")
                val = sensor_item.get("value")
                if idx == 0 and val is not None:
                    # Index 0 is water temperature in 1/100th of degree
                    temp_c = val / 100.0
                    if "temperature" in pool_data.sensors:
                        pool_data.sensors["temperature"].value = temp_c
                    else:
                        pool_data.sensors["temperature"] = IndygoSensorData(
                            key="temperature",
                            value=temp_c,
                        )

    def _parse_modules(
        self,
        json_data: dict,
        pool_data: IndygoPoolData,
        scraped_programs: dict[str, list[dict]] | None = None,
    ) -> None:
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
                                value=ipx_data["totalElectrolyseDuration"],
                            )
                        )

                # Programs parsing
                programs = []
                if "programs" in module:
                    programs = module["programs"]
                elif scraped_programs and str(m_id) in scraped_programs:
                    # fallback to scraped programs
                    programs = scraped_programs[str(m_id)]

                if programs:
                    indygo_module.programs = programs
                    # Find filtration program (type 4)
                    for prog in programs:
                        if (
                            "programCharacteristics" in prog
                            and prog["programCharacteristics"].get("programType")
                            == PROGRAM_TYPE_FILTRATION
                        ):
                            indygo_module.filtration_program = prog
                            break

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
                    key="ipx_salt", value=salt
                )

            # pH Setpoint
            ph_set = get_nested(outputs, 0, "ipxData", "pHSetpoint")
            if ph_set is not None:
                pool_data.sensors["ph_setpoint"] = IndygoSensorData(
                    key="ph_setpoint", value=ph_set
                )

            # Production Setpoint
            prod_set = get_nested(outputs, 1, "ipxData", "percentageSetpoint")
            if prod_set is not None:
                pool_data.sensors["production_setpoint"] = IndygoSensorData(
                    key="production_setpoint",
                    value=prod_set,
                )

            # Electrolyzer Mode
            elec_mode = get_nested(outputs, 1, "ipxData", "electrolyzerMode")
            if elec_mode is not None:
                pool_data.sensors["electrolyzer_mode"] = IndygoSensorData(
                    key="electrolyzer_mode",
                    value=elec_mode,
                )

            # pH Latest (from inputs)
            inputs = ipx_mod.get("inputs", [])
            if isinstance(inputs, list):
                for inp in inputs:
                    last_val = inp.get("lastValue")
                    if (
                        last_val
                        and "value" in last_val
                        and last_val["value"] is not None
                    ):
                        if inp.get("type") == IPX_PH_SENSOR_TYPE:
                            val = last_val["value"]
                        date_str = last_val.get("date")

                        extra_attrs = {}
                        if date_str:
                            extra_attrs["last_measurement_time"] = date_str

                        pool_data.sensors["ph"] = IndygoSensorData(
                            key="ph",
                            value=val,
                            extra_attributes=extra_attrs,
                        )
                        break

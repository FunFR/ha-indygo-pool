"""Parser for Indygo Pool data."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from .const import PROGRAM_TYPE_FILTRATION
from .models import IndygoModuleData, IndygoPoolData, IndygoSensorData

_LOGGER = logging.getLogger(__name__)


IPX_PH_SENSOR_TYPE = 6


def _get_nested(obj: dict | list | None, *keys: str) -> Any:
    """Safely traverse nested dicts/lists by key or index."""
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


def _js_var_regex(var_name: str, delimiter: str = r"[{\[]") -> re.Pattern:
    """Build a compiled regex to match a JS variable assignment."""
    return re.compile(
        rf"(?:var|let|const|window\.)\s*{var_name}\s*=\s*({delimiter})",
        re.IGNORECASE,
    )


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
        match = _js_var_regex("currentPool").search(html)

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
            match = _js_var_regex("modulesInPool", r"\[").search(html)
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

        match = _js_var_regex("poolTechModulesIpx", r"\[").search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                modules_list = json.loads(json_str)
                for m in modules_list:
                    if m.get("type", "").startswith("ipx"):
                        ipx_metadata = m
                        return ipx_metadata
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode poolTechModulesIpx JSON: %s", exc)

        match = _js_var_regex("ipxModule", r"\{").search(html)
        if match and (json_str := self.extract_json_object(html, match.start(1))):
            try:
                ipx_metadata = json.loads(json_str)
                return ipx_metadata
            except json.JSONDecodeError as exc:
                _LOGGER.error("Failed to decode ipxModule JSON: %s", exc)

        match = _js_var_regex("modulesInPool", r"\[").search(html)
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

        match = _js_var_regex("poolCommand", r"\{").search(html)
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

        match = _js_var_regex("modulesInPool", r"\[").search(html)
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

    @staticmethod
    def _find_filtration_module(
        pool_data: IndygoPoolData,
    ) -> IndygoModuleData | None:
        """Find the module responsible for filtration."""
        return next(
            (m for m in pool_data.modules.values() if m.filtration_program),
            next((m for m in pool_data.modules.values() if m.type == "lr-pc"), None),
        )

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

        # 1. Modules Data (Parsed first to allow sensors to be attached to them)
        self._parse_modules(json_data, pool_data, scraped_programs)

        # 2. Scraped IPX Data
        self._parse_scraped_ipx(json_data, pool_data)

        # 3. Main Pool Data — resolve filtration module once
        filt_module = self._find_filtration_module(pool_data)
        self._parse_root_sensors(json_data, pool_data, filt_module)
        self._parse_sensor_state(json_data, pool_data, filt_module)
        self._parse_pool_status_list(json_data, pool_data, filt_module)

        return pool_data

    @staticmethod
    def _minutes_to_time(minutes: int) -> str:
        """Convert minutes since midnight to HH:MM string."""
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"

    @staticmethod
    def _parse_remaining_time(time_str: str) -> int | None:
        """Parse remaining time string 'HH:MM' into total minutes."""
        try:
            parts = time_str.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_dialog_timestamp(raw: str | None) -> datetime | None:
        """Parse dialogTimeStamp (ISO 8601) into a timezone-aware datetime."""
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return None

    def _build_schedule_attributes(
        self,
        filt_module: IndygoModuleData,
        temp_ref: int | None,
        dialog_ts: datetime | None,
    ) -> dict:
        """Build filtration schedule attributes from temperatureSchedules and tempRef.

        Returns a dict of extra attributes to merge into the filtration pool_status.
        """
        if temp_ref is None or not filt_module.filtration_program:
            return {}

        schedules = filt_module.filtration_program.get("temperatureSchedules", [])
        if not schedules:
            return {}

        thresholds = schedules[0].get("thresholds", [])
        if not isinstance(thresholds, list) or temp_ref >= len(thresholds):
            return {}

        windows = thresholds[temp_ref]
        if not windows:
            return {}

        first = windows[0]
        start_min = first.get("start")
        end_min = first.get("end")
        if start_min is None or end_min is None:
            return {}

        # Build datetime values using dialogTimeStamp date
        schedule_start = self._minutes_to_time(start_min)
        schedule_end = self._minutes_to_time(end_min)
        if dialog_ts:
            base_date = dialog_ts.replace(hour=0, minute=0, second=0, microsecond=0)
            schedule_start = base_date.replace(
                hour=start_min // 60, minute=start_min % 60
            ).isoformat()
            schedule_end = base_date.replace(
                hour=min(end_min // 60, 23), minute=end_min % 60
            ).isoformat()

        return {
            "schedule_start": schedule_start,
            "schedule_end": schedule_end,
            "schedule_duration_minutes": sum(
                w.get("end", 0) - w.get("start", 0) for w in windows
            ),
            "schedule_windows": [
                {
                    "start": self._minutes_to_time(w["start"]),
                    "end": self._minutes_to_time(w["end"]),
                }
                for w in windows
                if "start" in w and "end" in w
            ],
        }

    def _parse_pool_status_list(
        self,
        json_data: dict,
        pool_data: IndygoPoolData,
        filt_module: IndygoModuleData | None = None,
    ) -> None:
        """Parse 'pool' list which contains status for Filtration, etc."""
        if "pool" not in json_data or not isinstance(json_data["pool"], list):
            return
        target_status = (
            filt_module.pool_status if filt_module else pool_data.pool_status
        )

        for item in json_data["pool"]:
            idx = item.get("index")
            val = item.get("value")

            # Index 0 is Filtration
            if idx == 0:
                temp_ref = item.get("tempRef")
                remaining_time = item.get("time")

                extra_attributes = {
                    "info": item.get("info"),
                    "time": remaining_time,
                    "tempRef": temp_ref,
                }

                # Merge schedule attributes into filtration status
                if filt_module:
                    dialog_ts = self._parse_dialog_timestamp(
                        json_data.get("dialogTimeStamp")
                    )
                    extra_attributes.update(
                        self._build_schedule_attributes(
                            filt_module, temp_ref, dialog_ts
                        )
                    )

                target_status["0"] = IndygoSensorData(
                    key="filtration_status",
                    value=val,
                    extra_attributes=extra_attributes,
                )

                # Remaining filtration time in minutes
                if remaining_time and filt_module:
                    remaining_minutes = self._parse_remaining_time(remaining_time)
                    if remaining_minutes is not None:
                        filt_module.sensors["filtration_remaining_time"] = (
                            IndygoSensorData(
                                key="filtration_remaining_time",
                                value=remaining_minutes,
                            )
                        )

    def _parse_root_sensors(
        self,
        json_data: dict,
        pool_data: IndygoPoolData,
        filt_module: IndygoModuleData | None = None,
    ) -> None:
        """Parse root level sensors."""
        root_sensors_map = {
            "temperature": {
                "attributes": {"temperatureTime": "last_measurement_time"},
            },
        }

        target_sensors = filt_module.sensors if filt_module else pool_data.sensors

        for key, config in root_sensors_map.items():
            if key in json_data and json_data[key] is not None:
                extra_attributes = {}
                # Handle attributes mapping
                attr_map = config.get("attributes", {})
                for source_key, target_key in attr_map.items():
                    if source_key in json_data:
                        extra_attributes[target_key] = json_data[source_key]

                target_sensors[key] = IndygoSensorData(
                    key=key,
                    value=json_data[key],
                    extra_attributes=extra_attributes,
                )

    def _parse_sensor_state(
        self,
        json_data: dict,
        pool_data: IndygoPoolData,
        filt_module: IndygoModuleData | None = None,
    ) -> None:
        """Parse sensorState (legacy/generic list)."""
        if "sensorState" not in json_data or not isinstance(
            json_data["sensorState"], list
        ):
            return

        target_sensors = filt_module.sensors if filt_module else pool_data.sensors

        for sensor_item in json_data["sensorState"]:
            idx = sensor_item.get("index")
            val = sensor_item.get("value")
            if idx == 0 and val is not None:
                # Index 0 is water temperature in 1/100th of degree
                temp_c = val / 100.0
                if "temperature" in target_sensors:
                    target_sensors["temperature"].value = temp_c
                else:
                    target_sensors["temperature"] = IndygoSensorData(
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
        if "ipx_module" not in json_data:
            return

        ipx_mod = json_data["ipx_module"]
        outputs = ipx_mod.get("outputs", [])

        # Find IPX module to attach sensors
        ipx_module = next(
            (m for m in pool_data.modules.values() if m.type == "ipx"), None
        )
        # Fallback to root sensors if no module found
        target_sensors = ipx_module.sensors if ipx_module else pool_data.sensors

        salt = _get_nested(outputs, 1, "ipxData", "saltValue")
        if salt is not None:
            target_sensors["ipx_salt"] = IndygoSensorData(key="ipx_salt", value=salt)

        ph_set = _get_nested(outputs, 0, "ipxData", "pHSetpoint")
        if ph_set is not None:
            target_sensors["ph_setpoint"] = IndygoSensorData(
                key="ph_setpoint", value=ph_set
            )

        prod_set = _get_nested(outputs, 1, "ipxData", "percentageSetpoint")
        if prod_set is not None:
            target_sensors["production_setpoint"] = IndygoSensorData(
                key="production_setpoint",
                value=prod_set,
            )

        elec_mode = _get_nested(outputs, 1, "ipxData", "electrolyzerMode")
        if elec_mode is not None:
            target_sensors["electrolyzer_mode"] = IndygoSensorData(
                key="electrolyzer_mode",
                value=elec_mode,
            )

        # pH Latest (from inputs)
        inputs = ipx_mod.get("inputs", [])
        if isinstance(inputs, list):
            for inp in inputs:
                last_val = inp.get("lastValue")
                if last_val and "value" in last_val and last_val["value"] is not None:
                    if inp.get("type") == IPX_PH_SENSOR_TYPE:
                        val = last_val["value"]
                        date_str = last_val.get("date")

                        extra_attrs = {}
                        if date_str:
                            extra_attrs["last_measurement_time"] = date_str

                        target_sensors["ph"] = IndygoSensorData(
                            key="ph",
                            value=val,
                            extra_attributes=extra_attrs,
                        )
                        break

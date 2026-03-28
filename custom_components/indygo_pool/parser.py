"""Parser for Indygo Pool data."""

from __future__ import annotations

import logging
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


class IndygoParser:
    """Parser for Indygo Pool data."""

    # ------------------------------------------------------------------
    # Hardware ID resolution (from module list, no HTML needed)
    # ------------------------------------------------------------------

    def _extract_device_ids(self, lr_pc: dict) -> tuple[str | None, str | None]:
        """Extract device short ID and relay ID from lr-pc module."""
        name_parts = lr_pc.get("name", "").split("-")
        if len(name_parts) > 1:
            device_short_id = name_parts[-1]
        else:
            device_short_id = lr_pc.get("serialNumber", "")[-6:]

        relay_id = lr_pc.get("relay") or device_short_id
        return device_short_id, relay_id

    def _resolve_lr_pc(
        self, modules: list[dict]
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve IDs from lr-pc + gateway modules."""
        gateway = next((m for m in modules if m.get("type") == "lr-mb-10"), None)
        lr_pc = next((m for m in modules if m.get("type") == "lr-pc"), None)

        if not lr_pc:
            return None, None, None

        if not gateway:
            gateway = lr_pc

        pool_address = gateway.get("serialNumber")
        device_short_id, relay_id = self._extract_device_ids(lr_pc)
        return pool_address, device_short_id, relay_id

    def _resolve_ipx(
        self, modules: list[dict]
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve IDs from IPX module as fallback."""
        ipx = next((m for m in modules if m.get("type") == "ipx"), None)
        if not ipx:
            return None, None, None

        pool_address = ipx.get("serialNumber")
        device_short_id = ipx.get("ipxRelay")
        relay_id = device_short_id
        return pool_address, device_short_id, relay_id

    def resolve_hardware_ids(
        self, modules: list[dict]
    ) -> tuple[str | None, str | None, str | None]:
        """Resolve pool_address, device_short_id and relay_id from modules.

        Tries lr-pc first, falls back to IPX.

        Returns:
            Tuple of (pool_address, device_short_id, relay_id)
        """
        pool_address, device_short_id, relay_id = self._resolve_lr_pc(modules)
        if not pool_address:
            pool_address, device_short_id, relay_id = self._resolve_ipx(modules)

        if not pool_address:
            _LOGGER.error(
                "No compatible module (lr-pc or ipx) found in %d modules.",
                len(modules),
            )
        return pool_address, device_short_id, relay_id

    # ------------------------------------------------------------------
    # Main data parser
    # ------------------------------------------------------------------

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
    ) -> IndygoPoolData:
        """Parse the API response into a structured IndygoPoolData object."""
        pool_data = IndygoPoolData(
            pool_id=pool_id, address=pool_address, relay_id=relay_id, raw_data=json_data
        )

        # 1. Modules Data
        self._parse_modules(json_data, pool_data)

        # 2. IPX Data
        self._parse_scraped_ipx(json_data, pool_data)

        # 3. Main Pool Data — resolve filtration module once
        filt_module = self._find_filtration_module(pool_data)
        self._parse_root_sensors(json_data, pool_data, filt_module)
        self._parse_sensor_state(json_data, pool_data, filt_module)
        self._parse_pool_status_list(json_data, pool_data, filt_module)

        return pool_data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        """Build filtration schedule attributes from temperatureSchedules."""
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

    # ------------------------------------------------------------------
    # Parsing sub-sections
    # ------------------------------------------------------------------

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

            if idx == 0:
                temp_ref = item.get("tempRef")
                remaining_time = item.get("time")

                extra_attributes = {
                    "info": item.get("info"),
                    "time": remaining_time,
                    "tempRef": temp_ref,
                }

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
    ) -> None:
        """Parse modules list."""
        if "modules" not in json_data:
            return
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

            # Programs
            programs = module.get("programs", [])
            if programs:
                indygo_module.programs = programs
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
        """Parse ipx_module data."""
        if "ipx_module" not in json_data:
            return

        ipx_mod = json_data["ipx_module"]
        outputs = ipx_mod.get("outputs", [])

        ipx_module = next(
            (m for m in pool_data.modules.values() if m.type == "ipx"), None
        )
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

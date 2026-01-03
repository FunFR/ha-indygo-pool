"""Tests for the Indygo Pool integration."""

import os

import pytest

from custom_components.indygo_pool.api import IndygoPoolApiClient


def _verify_pool_data(pool_data):
    """Verify pool data key indicators."""
    print(f"Pool data keys: {list(pool_data.keys())}")
    if "temperature" in pool_data:
        print(f"Pool Temperature: {pool_data['temperature']}")
    if "ph" in pool_data:
        print(f"Pool pH: {pool_data['ph']}")


def _verify_sensor(name, value, is_tor):
    """Verify a single sensor's data."""
    sensor_type = "Binary Sensor" if is_tor else "Sensor"
    print(f"Found {sensor_type}: {name} = {value}")

    # Specific checks for expected sensors
    if "Température" in name or "Thermomètre" in name:
        assert value is not None, f"Temperature sensor {name} has no value"
    if "pH" in name:
        assert value is not None, f"pH sensor {name} has no value"
    if "Redox" in name or "ORP" in name:
        print(f"Redox/ORP found: {value}")
    if "Sel" in name or "Salt" in name:
        print(f"Salt sensor found: {value}")
    if "Volet" in name:
        print(f"Shutter (Volet) found: {value}")


def _verify_modules_data(modules_data):
    """Verify modules and their sensors."""
    print(f"Found {len(modules_data)} modules")
    for module in modules_data:
        if "inputs" in module:
            for sensor in module["inputs"]:
                name = sensor.get("name", "Unknown")
                value = sensor.get("value")
                if value is None and "lastValue" in sensor:
                    value = sensor["lastValue"].get("value")

                is_tor = sensor.get("typeIsTOR", False) == 1
                _verify_sensor(name, value, is_tor)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_api_client_authentication():  # noqa: PLR0912, PLR0915
    """Test API client authentication with real credentials from env."""
    email = os.getenv("email")
    password = os.getenv("password")
    pool_id = os.getenv("pool_id")

    if not email or not password or not pool_id:
        pytest.skip("Credentials or pool_id not provided in environment")

    client = IndygoPoolApiClient(email, password, pool_id=pool_id)
    try:
        data = await client.async_get_data()
        assert data is not None
        print("Successfully reached the API endpoint and retrieved data!")
        print(f"Data snippet (keys): {list(data.keys())}")

        # Verify pool data
        if "pool" in data:
            pool = data["pool"]
            print("\n=== POOL DATA ===")
            print(f"Temperature: {pool.get('temperature')}°C")
            print(f"pH: {pool.get('ph')}")
            print(f"pH Quality: {pool.get('phQuality')}")
            print(f"pH Time: {pool.get('phTime')}")
            print(f"Filtering Type: {pool.get('filteringType')}")
            print(f"Water Treatment: {pool.get('waterTreatmentType')}")
            print(f"pH Regulation Mode: {pool.get('phRegulationMode')}")
            print(f"pH Regulation Type: {pool.get('pHRegulationType')}")
            print(f"Chlorine Regulation Mode: {pool.get('chlorineRegulationMode')}")
            print(f"Electrolyser Model: {pool.get('electrolyserModel')}")
            print(f"Chlorine Rate: {pool.get('chlorineRate')}")

            # Assertions
            assert pool.get("temperature") is not None, "Temperature should be present"
            assert pool.get("ph") is not None, "pH should be present"
            assert pool.get("phRegulationMode") is not None, (
                "pH regulation mode should be present"
            )

        # Verify poolCommand data (setpoints and configuration)
        if "poolCommand" in data:
            pool_cmd = data["poolCommand"]
            print("\n=== POOL COMMAND DATA ===")

            if "inputs" in pool_cmd:
                print(f"Inputs ({len(pool_cmd['inputs'])} sensors):")
                for idx, sensor in enumerate(pool_cmd["inputs"]):
                    sensor_type = sensor.get("type", -1)
                    print(f"  Input {idx} (Type {sensor_type}):")
                    print(f"    Low Threshold: {sensor.get('lowThreshold')}")
                    print(f"    High Threshold: {sensor.get('highThreshold')}")
                    print(f"    Unit: {sensor.get('unit')}")

            if "programs" in pool_cmd:
                print(f"\nPrograms ({len(pool_cmd['programs'])} total):")
                for idx, program in enumerate(pool_cmd["programs"]):
                    prog_chars = program.get("programCharacteristics", {})
                    prog_type = prog_chars.get("programType")
                    if prog_type:  # Only show active programs
                        print(f"  Program {idx}:")
                        print(f"    Type: {prog_type}")
                        print(f"    Mode: {prog_chars.get('mode')}")

        # Verify modules/sensors data
        if "modules" in data:
            print("\n=== MODULES DATA ===")
            print(f"Found {len(data['modules'])} modules")

            for module in data["modules"]:
                module_name = module.get("name", "Unknown")
                module_type = module.get("type", "Unknown")
                is_online = module.get("isOnline", False)

                print(f"\nModule: {module_name}")
                print(f"  Type: {module_type}, Online: {is_online}")

                # Check for IPX module with device state
                if module_type == "ipx" and "ipxData" in module:
                    ipx_data = module["ipxData"]
                    if "deviceState" in ipx_data:
                        device_state = ipx_data["deviceState"]
                        print("  Device State:")
                        shutter = device_state.get("shutterEntry")
                        boost = device_state.get("boostEnabled")
                        ph_inj = device_state.get("pHInjection")
                        prod = device_state.get("prodStatus")
                        print(f"    - Shutter Entry: {shutter}")
                        print(f"    - Boost Enabled: {boost}")
                        print(f"    - pH Injection: {ph_inj}")
                        print(f"    - Production Status: {prod}")
                        print(f"    - Flow Entry: {device_state.get('flowEntry')}")
                        print(f"    - Command Entry: {device_state.get('cmdEntry')}")

                    # Electrolyser data
                    print("  Electrolyser Data:")
                    total_dur = ipx_data.get("totalElectrolyseDuration")
                    remaining = ipx_data.get(
                        "remainingTimeElectrolyseDurationInPercent"
                    )
                    print(f"    - Total Duration: {total_dur}h")
                    print(f"    - Remaining %: {remaining}%")
                    print(f"    - Cell Voltage: {ipx_data.get('cellVoltage')}V")

                # Check inputs/sensors
                if "inputs" in module and module["inputs"]:
                    print(f"  Inputs ({len(module['inputs'])} sensors):")
                    for idx, sensor in enumerate(module["inputs"]):
                        sensor_type = sensor.get("type", -1)
                        sensor_name = sensor.get("name", f"Sensor {idx}")

                        value = None
                        if "lastValue" in sensor:
                            value = sensor["lastValue"].get("value")
                        elif "value" in sensor:
                            value = sensor["value"]

                        print(f"    - {sensor_name} (Type {sensor_type}): {value}")

    except Exception as e:
        pytest.fail(f"API call failed: {e}")

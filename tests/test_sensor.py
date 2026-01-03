import json
from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass

from custom_components.indygo_pool.binary_sensor import IndygoPoolBinarySensor
from custom_components.indygo_pool.sensor import IndygoPoolSensor

# Constants for magic values to satisfy PLR2004
EXPECTED_TEMPERATURE = 5.27
EXPECTED_PH = 7.2


def test_sensor_values():
    """Test sensor values directly without full HASS setup."""
    # Load fixture
    with open("tests/fixtures/data.json", encoding="utf-8") as f:
        data = json.load(f)

    # Setup Mock Coordinator
    coordinator = MagicMock()
    coordinator.data = data

    # Find thermometer sensor data in fixture (Module 3, id FAKE_MONGO_ID_5)
    thermo_data = None
    for module in data["modules"]:
        if module["name"] == "Module 3":
            for sensor in module["inputs"]:
                if sensor["id"] == "FAKE_MONGO_ID_5":
                    thermo_data = sensor
                    break

    assert thermo_data is not None

    # Test Temperature Sensor
    sensor = IndygoPoolSensor(coordinator, thermo_data, "Module 3")
    assert sensor.name == "Module 3 Thermomètre"
    assert sensor.native_value == EXPECTED_TEMPERATURE
    assert sensor.device_class == SensorDeviceClass.TEMPERATURE

    # Find pH sensor data (Module 1, id FAKE_MONGO_ID_3)
    ph_data = None
    for module in data["modules"]:
        if module["name"] == "Module 1":
            for sensor in module["inputs"]:
                if sensor["id"] == "FAKE_MONGO_ID_3":
                    ph_data = sensor
                    break

    assert ph_data is not None

    # Test pH Sensor
    sensor_ph = IndygoPoolSensor(coordinator, ph_data, "Module 1")
    assert sensor_ph.name == "Module 1 pHmètre"
    assert sensor_ph.native_value == EXPECTED_PH
    # device_class might be None on older HA versions but should be 'ph' if supported
    assert sensor_ph.device_class in (None, "ph")

    # Test Binary Sensor (Volet fermé in Module 3, id FAKE_MONGO_ID_6)
    volet_data = None
    for module in data["modules"]:
        if module["name"] == "Module 3":
            for sensor in module["inputs"]:
                if sensor["id"] == "FAKE_MONGO_ID_6":
                    volet_data = sensor
                    break

    assert volet_data is not None

    binary_sensor = IndygoPoolBinarySensor(coordinator, volet_data, "Module 3")
    assert binary_sensor.name == "Module 3 Volet fermé"
    assert binary_sensor.is_on is None  # as it's null in fixture

"""Tests for Indygo Parser."""

from custom_components.indygo_pool.models import IndygoPoolData
from custom_components.indygo_pool.parser import IndygoParser

# Constants for testing
TEST_POOL_ID = "123"
TEST_GATEWAY_SERIAL = "GATEWAY123"
TEST_RELAY_ID = "ABC"
TEST_TEMP_VALUE = 25.5
TEST_PH_VALUE = 7.2
TEST_ELECTROLYSE_DURATION = 100
TEST_PH_SETPOINT = 7.4
TEST_SALT_VALUE = 3.0
TEST_PROD_SETPOINT = 80
TEST_DATE = "2023-01-01T12:00:00Z"


class TestIndygoParser:
    """Test class for Indygo Parser."""

    def test_extract_json_object(self):
        """Test extraction of JSON object from text."""
        parser = IndygoParser()
        text = 'var someData = {"a": 1, "b": {"c": 2}};'
        start_index = text.find("{")
        result = parser.extract_json_object(text, start_index)
        assert result == '{"a": 1, "b": {"c": 2}}'

        # Test with escaped quotes
        text_escaped = '{"a": "val\\"ue"}'
        result_escaped = parser.extract_json_object(text_escaped, 0)
        assert result_escaped == '{"a": "val\\"ue"}'

    def test_parse_pool_ids(self):
        """Test parsing pool IDs from HTML."""
        parser = IndygoParser()
        html = (
            "<script>\n"
            "    var currentPool = {\n"
            '        "id": 123,\n'
            '        "temperature": 25.5,\n'
            '        "temperatureTime": "2023-01-01T12:00:00Z",\n'
            '        "modules": [\n'
            '            {"type": "lr-mb-10", "serialNumber": "GATEWAY123", '
            '"name": "Gateway-01"},\n'
            '            {"type": "lr-pc", "serialNumber": "LRPC123", '
            '"name": "Pool-ABC"}\n'
            "        ]\n"
            "    };\n"
            "</script>"
        )
        pool_address, relay_id, metadata = parser.parse_pool_ids(html, TEST_POOL_ID)
        assert pool_address == TEST_GATEWAY_SERIAL
        assert relay_id == TEST_RELAY_ID
        assert metadata["id"] == int(TEST_POOL_ID)
        assert metadata["temperature"] == TEST_TEMP_VALUE
        assert metadata["temperatureTime"] == TEST_DATE

    def test_parse_data(self):
        """Test parsing API JSON into IndygoPoolData."""
        parser = IndygoParser()
        json_data = {
            "temperature": TEST_TEMP_VALUE,
            "temperatureTime": TEST_DATE,
            "ph": TEST_PH_VALUE,
            "modules": [
                {
                    "id": "MOD1",
                    "type": "ipx",
                    "name": "Electrolyzer",
                    "ipxData": {"totalElectrolyseDuration": TEST_ELECTROLYSE_DURATION},
                }
            ],
            "ipx_module": {
                "outputs": [
                    {"ipxData": {"pHSetpoint": TEST_PH_SETPOINT}},
                    {
                        "ipxData": {
                            "saltValue": TEST_SALT_VALUE,
                            "percentageSetpoint": TEST_PROD_SETPOINT,
                        }
                    },
                ],
                "inputs": [
                    {"name": "", "type": 0},
                    {
                        "name": "",
                        "type": 6,
                        "lastValue": {
                            "value": TEST_PH_VALUE,
                            "date": TEST_DATE,
                        },
                    },
                ],
            },
        }

        pool_data = parser.parse_data(json_data, "POOL1", "ADDR1", "RELAY1")

        assert isinstance(pool_data, IndygoPoolData)
        assert pool_data.pool_id == "POOL1"
        assert pool_data.sensors["temperature"].value == TEST_TEMP_VALUE
        assert (
            pool_data.sensors["temperature"].extra_attributes["last_measurement_time"]
            == TEST_DATE
        )

        # Test Module Data
        assert "MOD1" in pool_data.modules
        assert (
            pool_data.modules["MOD1"].sensors["totalElectrolyseDuration"].value
            == TEST_ELECTROLYSE_DURATION
        )

        # Test IPX Scraped Data
        assert pool_data.sensors["ph_setpoint"].value == TEST_PH_SETPOINT
        assert pool_data.sensors["ipx_salt"].value == TEST_SALT_VALUE

        # Test pH Latest Logic (merged)
        assert "ph" in pool_data.sensors
        assert pool_data.sensors["ph"].value == TEST_PH_VALUE
        assert (
            pool_data.sensors["ph"].extra_attributes["last_measurement_time"]
            == TEST_DATE
        )

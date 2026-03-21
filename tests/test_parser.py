"""Tests for Indygo Parser."""

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
TEST_SENSOR_STATE_TEMP = 1355
TEST_DATE = "2023-01-01T12:00:00Z"
FILTRATION_PROGRAM_TYPE = 4
MODE_AUTO = 2
MODE_ON = 1


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
        pool_address, device_short_id, relay_id, metadata = parser.parse_pool_ids(
            html, TEST_POOL_ID
        )
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
            "sensorState": [{"index": 0, "value": TEST_SENSOR_STATE_TEMP}],
            "ph": TEST_PH_VALUE,
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pool Pump",
                },
                {
                    "id": "MOD2",
                    "type": "ipx",
                    "name": "Electrolyzer",
                    "ipxData": {"totalElectrolyseDuration": TEST_ELECTROLYSE_DURATION},
                },
            ],
            "ipx_module": {
                "outputs": [
                    {"ipxData": {"pHSetpoint": TEST_PH_SETPOINT}},
                    {
                        "ipxData": {
                            "saltValue": TEST_SALT_VALUE,
                            "percentageSetpoint": TEST_PROD_SETPOINT,
                            "electrolyzerMode": 0,
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
            "pool": [
                {"index": 0, "value": TEST_PH_VALUE, "info": "INFO", "time": TEST_DATE}
            ],
        }

        pool_data = parser.parse_data(json_data, "POOL1", "ADDR1", "RELAY1")

        # Test LR-PC (Filtration Module) Data
        assert "MOD1" in pool_data.modules
        filt_mod = pool_data.modules["MOD1"]

        # Temperature and Filtration should now be on the module
        assert filt_mod.sensors["temperature"].value == TEST_SENSOR_STATE_TEMP / 100.0
        # Check filtration status (index 0)
        assert filt_mod.pool_status["0"].value == TEST_PH_VALUE

        # Test IPX Data (on module MOD2)
        assert "MOD2" in pool_data.modules
        ipx_mod = pool_data.modules["MOD2"]
        assert (
            ipx_mod.sensors["totalElectrolyseDuration"].value
            == TEST_ELECTROLYSE_DURATION
        )

        # Test IPX Scraped Data (now on module MOD2)
        assert ipx_mod.sensors["ph_setpoint"].value == TEST_PH_SETPOINT
        assert ipx_mod.sensors["ipx_salt"].value == TEST_SALT_VALUE
        assert ipx_mod.sensors["production_setpoint"].value == TEST_PROD_SETPOINT
        # Electrolyzer mode is defaulted in this test case
        assert ipx_mod.sensors["electrolyzer_mode"].value == 0

        # Test pH Latest Logic (merged on module MOD2)
        assert "ph" in ipx_mod.sensors
        assert ipx_mod.sensors["ph"].value == TEST_PH_VALUE
        assert (
            ipx_mod.sensors["ph"].extra_attributes["last_measurement_time"] == TEST_DATE
        )

    def test_parse_programs_from_html(self):
        """Test parsing programs from embedded HTML JSON."""
        parser = IndygoParser()
        html = (
            "<script>\n"
            "    var poolCommand = {\n"
            '        "module": "MOD_123",\n'
            '        "programs": [\n'
            "            {\n"
            '                "module": "MOD_123",\n'
            '                "programCharacteristics": {\n'
            f'                    "programType": {FILTRATION_PROGRAM_TYPE}, '
            f'"mode": {MODE_AUTO}\n'
            "                }\n"
            "            },\n"
            "            {\n"
            '                "module": "MOD_123",\n'
            '                "programCharacteristics": {"programType": 1, "mode": 1}\n'
            "            }\n"
            "        ]\n"
            "    };\n"
            "</script>"
        )

        programs_map = parser.parse_programs_from_html(html)
        assert "MOD_123" in programs_map
        programs = programs_map["MOD_123"]
        expected_count = 2
        assert len(programs) == expected_count

        # Verify filtration program (type 4) matches
        filt_prog = next(
            p
            for p in programs
            if p["programCharacteristics"]["programType"] == FILTRATION_PROGRAM_TYPE
        )
        assert filt_prog["programCharacteristics"]["mode"] == MODE_AUTO

    def test_parse_programs_missing_html(self):
        """Test parsing programs when HTML/JSON is missing."""
        parser = IndygoParser()
        html = "<html><body>No programs here</body></html>"
        programs_map = parser.parse_programs_from_html(html)
        assert programs_map == {}

    def test_extract_json_object_edge_cases(self):
        """Test JSON object extraction edge cases."""
        parser = IndygoParser()
        assert parser.extract_json_object("no braces here", 0) is None
        assert parser.extract_json_object("{unclosed object", 0) is None

    def test_parse_lr_pc_module_edge_cases(self):
        """Test LR-PC parsing edge cases."""
        parser = IndygoParser()
        # No lr-pc
        a, b, c = parser._parse_lr_pc_module([{"type": "other"}])
        assert a is None

        # lr-pc acts as gateway
        a, b, c = parser._parse_lr_pc_module(
            [{"type": "lr-pc", "serialNumber": "123456"}]
        )
        assert a == "123456"

    def test_parse_ipx_module_direct(self):
        """Test IPX module direct parsing."""
        parser = IndygoParser()
        assert parser._parse_ipx_module([{"type": "other"}]) == (None, None, None)
        a, b, c = parser._parse_ipx_module(
            [{"type": "ipx", "serialNumber": "ser123", "ipxRelay": "rel456"}]
        )
        assert a == "ser123"
        assert b == "rel456"
        assert c == "rel456"

    def test_parse_pool_ids_fallbacks(self):
        """Test pool IDs HTML parsing fallbacks."""
        parser = IndygoParser()
        # JSON Decode error on currentPool returns empty
        html = "<script>var currentPool = {bad json;</script>"
        assert parser.parse_pool_ids(html, "123") == (None, None, None, {})

        # modulesInPool fallback
        html = (
            '<script>var modulesInPool = [{"type": "ipx", '
            '"serialNumber": "X", "ipxRelay": "Y"}];</script>'
        )
        a, b, c, m = parser.parse_pool_ids(html, "123")
        assert a == "X"
        assert b == "Y"
        assert m == {"modules": [{"type": "ipx", "serialNumber": "X", "ipxRelay": "Y"}]}

        # No compatible module
        html = '<script>var currentPool = {"modules": []};</script>'
        assert parser.parse_pool_ids(html, "123") == (None, None, None, {})

    def test_parse_ipx_module_html(self):
        """Test IPX module HTML embedded JSON parsing."""
        parser = IndygoParser()
        # Validate poolTechModulesIpx
        html = '<script>var poolTechModulesIpx = [{"type": "ipx_1"}];</script>'
        assert parser.parse_ipx_module(html) == {"type": "ipx_1"}

        # Validate legacy ipxModule
        html = '<script>var ipxModule = {"id": 1};</script>'
        assert parser.parse_ipx_module(html) == {"id": 1}

        # Validate modulesInPool fallback for ipx
        html = '<script>var modulesInPool = [{"type": "ipx_foo"}];</script>'
        assert parser.parse_ipx_module(html) == {"type": "ipx_foo"}

    def test_parse_programs_from_html_fallbacks(self):
        """Test programs parsing fallbacks."""
        parser = IndygoParser()
        # poolCommand json error
        html = "<script>var poolCommand = {bad;</script>"
        assert parser.parse_programs_from_html(html) == {}

        # modulesInPool valid programs
        html = (
            '<script>var modulesInPool = [{"id": "MOD1", '
            '"programs": [{"id": 1}]}];</script>'
        )
        progs = parser.parse_programs_from_html(html)
        assert progs["MOD1"] == [{"id": 1}]

    def test_parse_data_edge_cases(self):
        """Test full data parsing edge cases."""
        parser = IndygoParser()
        # Test when no modules, no pool status, no sensorState, etc.
        data = parser.parse_data({}, "POOL1", "ADDR1", "RELAY1")
        assert len(data.modules) == 0

        # Test new temperature creation without existing modules
        data = parser.parse_data(
            {"sensorState": [{"index": 0, "value": 1500}]}, "POOL1", "ADDR1", "RELAY1"
        )
        expected_temperature = 15.0
        assert data.sensors["temperature"].value == expected_temperature

        # Test get_nested error handling without crashing
        data = parser.parse_data(
            {"ipx_module": {"outputs": [{"ipxData": {}}]}}, "POOL1", "ADDR1", "RELAY1"
        )
        assert "ipx_salt" not in data.sensors

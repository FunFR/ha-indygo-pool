"""Tests for Indygo Parser."""

from custom_components.indygo_pool.parser import (
    IndygoParser,
    _get_nested,
    _js_var_regex,
)

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

    def test_parse_filtration_schedule_as_attributes(self):
        """Test schedule is exposed as attributes on the filtration binary sensor."""
        parser = IndygoParser()
        json_data = {
            "dialogTimeStamp": "2026-03-28T16:28:54Z",
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [
                                {
                                    "thresholds": [
                                        [{"start": 300, "end": 360}],
                                        [{"start": 720, "end": 900}],
                                        [{"start": 660, "end": 960}],
                                    ]
                                }
                            ],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "time": "01:30", "tempRef": 2}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        mod = pool_data.modules["MOD1"]

        # Schedule should be in pool_status["0"] extra_attributes
        attrs = mod.pool_status["0"].extra_attributes
        assert attrs["schedule_start"] == "2026-03-28T11:00:00+00:00"
        assert attrs["schedule_end"] == "2026-03-28T16:00:00+00:00"
        expected_duration = 300
        assert attrs["schedule_duration_minutes"] == expected_duration
        assert len(attrs["schedule_windows"]) == 1
        assert attrs["schedule_windows"][0] == {"start": "11:00", "end": "16:00"}

        # Should NOT be separate sensors
        assert "filtration_schedule_start" not in mod.sensors
        assert "filtration_schedule_end" not in mod.sensors

    def test_parse_filtration_schedule_multiple_windows(self):
        """Test schedule with multiple filtration windows."""
        parser = IndygoParser()
        json_data = {
            "dialogTimeStamp": "2026-03-28T10:00:00Z",
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [
                                {
                                    "thresholds": [
                                        [
                                            {"start": 300, "end": 360},
                                            {"start": 1320, "end": 1380},
                                        ],
                                    ]
                                }
                            ],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "time": "00:45", "tempRef": 0}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes

        assert attrs["schedule_start"] == "2026-03-28T05:00:00+00:00"
        assert attrs["schedule_end"] == "2026-03-28T06:00:00+00:00"
        expected_window_count = 2
        assert len(attrs["schedule_windows"]) == expected_window_count
        assert attrs["schedule_windows"][1] == {"start": "22:00", "end": "23:00"}
        expected_duration = 120
        assert attrs["schedule_duration_minutes"] == expected_duration

    def test_parse_filtration_schedule_no_dialog_timestamp(self):
        """Test schedule falls back to HH:MM when dialogTimeStamp is missing."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [
                                {"thresholds": [[{"start": 660, "end": 960}]]}
                            ],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "tempRef": 0}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes
        assert attrs["schedule_start"] == "11:00"
        assert attrs["schedule_end"] == "16:00"

    def test_parse_filtration_schedule_missing_data(self):
        """Test schedule parsing with missing data doesn't crash."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "tempRef": 2}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes
        assert "schedule_start" not in attrs

    def test_parse_filtration_schedule_temp_ref_out_of_bounds(self):
        """Test schedule when tempRef exceeds thresholds length."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [
                                {"thresholds": [[{"start": 660, "end": 960}]]}
                            ],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "tempRef": 99}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes
        assert "schedule_start" not in attrs

    def test_parse_filtration_schedule_empty_windows(self):
        """Test schedule when threshold entry is an empty list."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [{"thresholds": [[]]}],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "tempRef": 0}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes
        assert "schedule_start" not in attrs

    def test_parse_filtration_schedule_window_missing_fields(self):
        """Test schedule when first window is missing start or end."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [
                                {"thresholds": [[{"start": 660}]]}
                            ],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "tempRef": 0}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes
        assert "schedule_start" not in attrs

    def test_parse_filtration_schedule_no_temp_ref(self):
        """Test schedule parsing when tempRef is missing."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                            "temperatureSchedules": [
                                {"thresholds": [[{"start": 660, "end": 960}]]}
                            ],
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        attrs = pool_data.modules["MOD1"].pool_status["0"].extra_attributes
        assert "schedule_start" not in attrs

    def test_parse_remaining_time(self):
        """Test remaining filtration time parsing."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 1, "time": "01:30", "tempRef": 2}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        mod = pool_data.modules["MOD1"]
        assert "filtration_remaining_time" in mod.sensors
        expected_minutes = 90
        assert mod.sensors["filtration_remaining_time"].value == expected_minutes

    def test_parse_remaining_time_zero(self):
        """Test remaining time when filtration is done."""
        parser = IndygoParser()
        json_data = {
            "modules": [
                {
                    "id": "MOD1",
                    "type": "lr-pc",
                    "name": "Pump",
                    "programs": [
                        {
                            "programCharacteristics": {
                                "programType": FILTRATION_PROGRAM_TYPE,
                                "mode": MODE_AUTO,
                            },
                        }
                    ],
                }
            ],
            "pool": [{"index": 0, "value": 0, "time": "00:00", "tempRef": 2}],
        }
        pool_data = parser.parse_data(json_data, "P1", "A1", "R1")
        mod = pool_data.modules["MOD1"]
        assert mod.sensors["filtration_remaining_time"].value == 0

    def test_minutes_to_time(self):
        """Test minutes to time conversion."""
        assert IndygoParser._minutes_to_time(0) == "00:00"
        assert IndygoParser._minutes_to_time(60) == "01:00"
        assert IndygoParser._minutes_to_time(660) == "11:00"
        assert IndygoParser._minutes_to_time(1440) == "24:00"
        assert IndygoParser._minutes_to_time(90) == "01:30"

    def test_parse_remaining_time_helper(self):
        """Test _parse_remaining_time helper."""
        expected_90 = 90
        expected_165 = 165
        assert IndygoParser._parse_remaining_time("01:30") == expected_90
        assert IndygoParser._parse_remaining_time("00:00") == 0
        assert IndygoParser._parse_remaining_time("02:45") == expected_165
        assert IndygoParser._parse_remaining_time("invalid") is None
        assert IndygoParser._parse_remaining_time("") is None

    def test_parse_dialog_timestamp(self):
        """Test _parse_dialog_timestamp helper."""
        dt = IndygoParser._parse_dialog_timestamp("2026-03-28T16:28:54Z")
        assert dt is not None
        expected_year = 2026
        expected_month = 3
        expected_day = 28
        assert dt.year == expected_year
        assert dt.month == expected_month
        assert dt.day == expected_day
        assert dt.tzinfo is not None

        assert IndygoParser._parse_dialog_timestamp(None) is None
        assert IndygoParser._parse_dialog_timestamp("not-a-date") is None

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


class TestGetNested:
    """Tests for the _get_nested helper."""

    def test_traverses_dict(self):
        """Test basic dict traversal."""
        assert _get_nested({"a": {"b": 1}}, "a", "b") == 1

    def test_traverses_list_by_index(self):
        """Test list traversal by numeric key."""
        expected = 20
        assert _get_nested([10, 20, 30], "1") == expected

    def test_returns_none_on_non_traversable(self):
        """Test early return when encountering a non-dict/list value."""
        assert _get_nested({"a": 42}, "a", "b") is None

    def test_returns_none_on_none_input(self):
        """Test with None input."""
        assert _get_nested(None, "a") is None

    def test_returns_none_on_index_error(self):
        """Test with out-of-range list index."""
        assert _get_nested([1], "5") is None

    def test_returns_none_on_invalid_index(self):
        """Test with non-numeric key on a list."""
        assert _get_nested([1, 2], "abc") is None


class TestJsVarRegex:
    """Tests for the _js_var_regex helper."""

    def test_matches_var(self):
        """Test matching var declaration."""
        regex = _js_var_regex("myVar", r"\{")
        assert regex.search("var myVar = {};") is not None

    def test_matches_const(self):
        """Test matching const declaration."""
        regex = _js_var_regex("myVar", r"\[")
        assert regex.search("const myVar = [];") is not None

    def test_matches_window_dot(self):
        """Test matching window.property assignment."""
        regex = _js_var_regex("myVar")
        assert regex.search("window.myVar = {};") is not None

    def test_no_match(self):
        """Test no match for unrelated content."""
        regex = _js_var_regex("myVar")
        assert regex.search("var otherVar = {};") is None

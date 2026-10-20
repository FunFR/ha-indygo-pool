"""Tests for the vendor-app program frame builder."""

import pytest

from custom_components.indygo_pool.device_program import build_device_program

THURSDAY = 3
PUMP_THRESHOLDS = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 127]


def _pump(**characteristics) -> dict:
    """Cloud document of a filtration program, as MyIndygo stores it."""
    return {
        "index": 0,
        "name": "",
        "windows": [],
        "variableSpeedWindows": [],
        "temperatureSchedules": [],
        "programCharacteristics": {
            "programType": 4,
            "mode": 2,
            "rule": 0,
            "adaptOffset": 0,
            "defaultProgramSpeed": 2,
            "onSpeed": 3,
            "frostFreeSpeed": 1,
            "speedSequence": 38192,
            "microFilteringSpeed": 1,
            "microFilteringDuration": 5,
            "microFilteringPeriod": 60,
            "microFilteringTemperature": 4,
            **characteristics,
        },
    }


def _build(program: dict, **kwargs) -> dict:
    return build_device_program(
        program,
        frost_free_enabled=kwargs.get("frost_free_enabled", False),
        default_speed_sequence=kwargs.get("default_speed_sequence", 29456),
    )


def test_pump_characteristics_use_the_app_short_keys():
    """Speeds, mode and rule travel under the short keys the module reads."""
    frame = _build(_pump())

    assert frame["index"] == 0
    assert frame["name"] == ""
    assert frame["programCharacteristics"] == {
        "mode": 2,
        "rule": 0,
        "programType": 4,
        "ths": PUMP_THRESHOLDS,
        "cyclic": [
            {"th": 127, "dur": 0, "per": 60},
            {"th": 127, "dur": 0, "per": 60},
        ],
        "spSeq": 38192,
        "spPg": 2,
        "spFF": 1,
        "spIn": 1,
        "spON": 3,
        "inPg": {"dur": 5, "per": 60, "th": 4},
    }


def test_missing_speeds_fall_back_to_the_app_defaults():
    """Absent or null fields take the app defaults, the sequence the pump's."""
    frame = _build(
        _pump(
            speedSequence=None,
            defaultProgramSpeed=-1,
            onSpeed=None,
            frostFreeSpeed=None,
            microFilteringDuration=None,
            microFilteringPeriod=-1,
            microFilteringTemperature=None,
        ),
        default_speed_sequence=63280,
    )["programCharacteristics"]

    assert (frame["spSeq"], frame["spPg"], frame["spON"], frame["spFF"]) == (
        63280,
        1,
        1,
        1,
    )
    assert frame["inPg"] == {"dur": 0, "per": 0, "th": 127}


def test_frost_free_enables_the_cyclic_filtering_steps():
    """With frost protection on, the module gets the app's two cyclic steps."""
    frame = _build(_pump(), frost_free_enabled=True)["programCharacteristics"]

    assert frame["cyclic"] == [
        {"th": 2, "dur": 20, "per": 120},
        {"th": 0, "dur": 60, "per": 60},
    ]


def _window(start, end, days, **extra) -> dict:
    return {"start": start, "end": end, "runningDays": days, **extra}


def _sched(program: dict) -> list[list[int]]:
    return _build(program)["sched"]


def test_time_windows_fill_the_hour_bits_of_their_days():
    """Hours 15 to 17 on day bit 3: bits 15, 16 and 17 in all 12 slots."""
    program = _pump()
    program["windows"] = [_window(900, 1080, 1 << THURSDAY, on=10800, off=0)]

    sched = _sched(program)

    assert sched[THURSDAY] == [229376] * 12
    assert all(row == [0] * 12 for i, row in enumerate(sched) if i != THURSDAY)


def test_overnight_window_stays_on_its_own_day_row():
    """22:00 to 06:00: hours 22, 23 and 0 to 5 on the same day row, no spill."""
    program = _pump()
    program["windows"] = [_window(1320, 360, 1)]

    sched = _sched(program)

    assert sched[0] == [12582975] * 12
    assert sched[1] == [0] * 12


def test_cycling_window_alternates_on_and_off_periods():
    """One hour on then one hour off from 10:00: hours 10 and 12 only."""
    program = _pump()
    program["windows"] = [_window(600, 840, 127, on=3600, off=3600)]

    sched = _sched(program)

    assert sched[0] == [1024 | 4096] * 12


def test_variable_speed_windows_encode_the_speed_in_two_slot_halves():
    """Speed 1 sets slots 0-5, speed 2 moves to slots 6-11, speed 3 sets both."""
    program = _pump(rule=2)
    program["windows"] = [_window(0, 1440, 127)]  # ignored by this rule
    program["variableSpeedWindows"] = [
        _window(540, 660, 1, speed=2),
        _window(480, 600, 1, speed=1),
        _window(1200, 1260, 1, speed=3),
    ]

    row = _sched(program)[0]

    assert row[:6] == [256 | 1048576] * 6
    assert row[6:] == [512 | 1024 | 1048576] * 6
    assert _sched(program)[1] == [0] * 12


def _thermo(adapt_offset=0, schedules=None) -> dict:
    program = _pump(rule=1, adaptOffset=adapt_offset)
    program["windows"] = [_window(0, 1440, 127)]  # ignored by this rule
    program["temperatureSchedules"] = schedules or [
        {
            "days": 127,
            "indexes": [0, 1],
            "thresholds": [
                [{"start": 300, "end": 360}, {"start": 1320, "end": 1380}],
                [{"start": 720, "end": 900}],
            ],
        }
    ]
    return program


def test_temperature_schedule_maps_each_index_to_a_column():
    """One column per index: hours 5 and 22 for the first, 12 to 14 for the next."""
    sched = _sched(_thermo())

    assert all(row == [4194336, 28672] + [0] * 10 for row in sched)


def test_adapt_offset_shifts_indexes_and_clamps_to_the_last_threshold():
    """+60 minutes of offset moves each index up one step, capped at the last."""
    sched = _sched(_thermo(adapt_offset=60))

    assert sched[0][:2] == [28672, 28672]


def test_only_the_first_schedule_matching_a_day_applies():
    """A day takes the first schedule listing it, later ones are ignored."""
    only_monday = {
        "days": 1,
        "indexes": [0],
        "thresholds": [[{"start": 0, "end": 60}]],
    }
    everyday = _thermo()["temperatureSchedules"][0]

    sched = _sched(_thermo(schedules=[only_monday, everyday]))

    assert sched[0][:2] == [1, 0]
    assert sched[1][:2] == [4194336, 28672]


def test_programs_other_than_the_pump_are_rejected():
    """Auxiliary and treatment programs have their own frames, not ported yet."""
    with pytest.raises(ValueError, match="filtration pump"):
        _build(_pump(programType=8))

"""Build the program frame the MyIndygo app sends to a Pool Command module.

The cloud stores programs with long keys, the MyIndygo app writes them to the
module with short ones.
"""

from __future__ import annotations

from typing import Any

from .const import (
    PROGRAM_RULE_THERMO_ADAPTIVE,
    PROGRAM_RULE_VARIABLE_SPEED,
    PROGRAM_TYPE_FILTRATION,
)

_DAYS = 7
_SLOTS = 12
SPEED_1, SPEED_2, SPEED_3 = 1, 2, 3

# Fixed in the app for the MyIndygo brand (11 values, padded to 12 with 127).
_TEMPERATURE_THRESHOLDS = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 127]

_CYCLIC_IDLE = [
    {"th": 127, "dur": 0, "per": 60},
    {"th": 127, "dur": 0, "per": 60},
]
_CYCLIC_FROST_FREE = [
    {"th": 2, "dur": 20, "per": 120},
    {"th": 0, "dur": 60, "per": 60},
]


def _value(characteristics: dict[str, Any], key: str, default: int) -> int:
    """Return a numeric characteristic, ``default`` when absent, null or -1."""
    value = characteristics.get(key)
    return default if value is None or value == -1 else int(value)


def module_speed_keys(characteristics: dict[str, Any]) -> dict[str, int]:
    """Return the speeds stored in the module's own keys, skipping unset ones."""
    keys = {
        "spPg": "defaultProgramSpeed",
        "spON": "onSpeed",
        "spFF": "frostFreeSpeed",
        "spSeq": "speedSequence",
    }
    return {
        short: int(characteristics[long])
        for short, long in keys.items()
        if characteristics.get(long) not in (None, -1)
    }


def _is_window_active(window: dict[str, Any], minute: int) -> bool:
    """Return True when the window runs at ``minute`` of the day.

    Mirrors ``isWindowActiveAtTime``: an ``on``/``off`` pair makes the window
    cycle, and an overnight window (end before start) wraps past midnight.
    """
    start, end = window["start"], window["end"]
    if start < 0:
        return False
    end = end or 1440
    if start >= end:
        return minute >= start or minute < end
    if not start <= minute < end:
        return False

    on, off = window.get("on"), window.get("off")
    if off is None:
        off = 0
    if on is None:
        on = (end - start) * 60
    if off == -1:
        return True
    period = int(on / 60) + int(off / 60)
    return period == 0 or (minute - start) % period < int(on / 60)


def _window_schedule(windows: list[dict[str, Any]]) -> list[list[int]]:
    """Day x 5-minute-slot matrix, one bit per hour (``rule`` time)."""
    matrix = [[0] * _SLOTS for _ in range(_DAYS)]
    for window in windows:
        for day in range(_DAYS):
            if not window["runningDays"] & (1 << day):
                continue
            for hour in range(24):
                for slot in range(_SLOTS):
                    if _is_window_active(window, hour * 60 + slot * 5):
                        matrix[day][slot] |= 1 << hour
    return matrix


def _is_time_inside(minute: int, start: int, end: int) -> bool:
    """Return True when ``minute`` falls in [start, end), wrapping past midnight."""
    if start < 0:
        return False
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def _temperature_schedule(
    schedules: list[dict[str, Any]], adapt_offset: int
) -> list[list[int]]:
    """Day x index-column matrix, one bit per hour (``rule`` thermo-adaptive).

    Each column is one temperature step of the first schedule that runs that
    day, moved by ``adapt_offset`` (minutes, whole hours) and capped to the
    schedule's thresholds.
    """
    matrix = [[0] * _SLOTS for _ in range(_DAYS)]
    shift = int(adapt_offset / 60)
    for day in range(_DAYS):
        schedule = next((s for s in schedules if s["days"] & (1 << day)), None)
        if schedule is None or not schedule["thresholds"]:
            continue
        thresholds = schedule["thresholds"]
        for column, index in enumerate(schedule["indexes"][:_SLOTS]):
            step = min(max(index + shift, 0), len(thresholds) - 1)
            for time_range in thresholds[step]:
                for hour in range(24):
                    if _is_time_inside(
                        hour * 60, time_range["start"], time_range["end"]
                    ):
                        matrix[day][column] |= 1 << hour
    return matrix


def _variable_speed_schedule(windows: list[dict[str, Any]]) -> list[list[int]]:
    """Day x 10-minute-slot matrix, slots 0-5 and 6-11 holding the speed bits.

    Speed 1 sets the first half, speed 2 the second half only, speed 3 both.
    Windows apply from the lowest speed up, so a higher speed wins an overlap.
    """
    matrix = [[0] * _SLOTS for _ in range(_DAYS)]
    for window in sorted(windows, key=lambda w: w.get("speed") or 0):
        speed = window.get("speed")
        for day in range(_DAYS):
            if not window["runningDays"] & (1 << day):
                continue
            for hour in range(24):
                bit = 1 << hour
                for slot in range(6):
                    if not _is_window_active(window, hour * 60 + slot * 10):
                        continue
                    if speed == SPEED_1:
                        matrix[day][slot] |= bit
                    elif speed == SPEED_2:
                        matrix[day][slot] &= ~bit
                        matrix[day][slot + 6] |= bit
                    elif speed == SPEED_3:
                        matrix[day][slot] |= bit
                        matrix[day][slot + 6] |= bit
    return matrix


def _schedule(program: dict[str, Any]) -> list[list[int]]:
    """Return the ``sched`` matrix matching the program's management rule."""
    chars = program["programCharacteristics"]
    if chars["rule"] == PROGRAM_RULE_THERMO_ADAPTIVE:
        return _temperature_schedule(
            program.get("temperatureSchedules") or [],
            _value(chars, "adaptOffset", 0),
        )
    if chars["rule"] == PROGRAM_RULE_VARIABLE_SPEED:
        return _variable_speed_schedule(program.get("variableSpeedWindows") or [])
    return _window_schedule(program.get("windows") or [])


def build_device_program(
    program: dict[str, Any],
    *,
    frost_free_enabled: bool,
    default_speed_sequence: int,
) -> dict[str, Any]:
    """Return the short-key frame of a filtration pump program."""
    chars = program["programCharacteristics"]
    if chars.get("programType") != PROGRAM_TYPE_FILTRATION:
        raise ValueError("Only filtration pump programs are supported")

    return {
        "index": program["index"],
        "name": program.get("name") or "",
        "programCharacteristics": {
            "mode": chars["mode"],
            "rule": chars["rule"],
            "programType": PROGRAM_TYPE_FILTRATION,
            "ths": list(_TEMPERATURE_THRESHOLDS),
            "cyclic": [
                dict(step)
                for step in (_CYCLIC_FROST_FREE if frost_free_enabled else _CYCLIC_IDLE)
            ],
            "spSeq": _value(chars, "speedSequence", default_speed_sequence),
            "spPg": _value(chars, "defaultProgramSpeed", 1),
            "spFF": _value(chars, "frostFreeSpeed", 1),
            "spIn": 1,
            "spON": _value(chars, "onSpeed", 1),
            "inPg": {
                "dur": _value(chars, "microFilteringDuration", 0),
                "per": _value(chars, "microFilteringPeriod", 0),
                "th": _value(chars, "microFilteringTemperature", 127),
            },
        },
        "sched": _schedule(program),
    }

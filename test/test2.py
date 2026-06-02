import hashlib
import json
from typing import Any, Dict, List, Optional

import requests


# -----------------------------
# Basic configuration
# -----------------------------

HOST = "http://192.168.100.30"
PASSWORD = "opendoor"


# -----------------------------
# Helper functions
# -----------------------------

def make_password_hash(password: str) -> str:
    """
    Convert the OpenSprinkler plain password into the MD5 hash required by the API.

    OpenSprinkler API does not expect:
        pw=opendoor

    It expects:
        pw=<md5 hash of opendoor>
    """
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def api_get(
    endpoint: str,
    password_hash: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 5,
) -> Any:
    """
    Send a GET request to the OpenSprinkler API.

    Parameters:
        endpoint:
            API endpoint, for example "/jn", "/ja", "/cs".

        password_hash:
            MD5 password hash.

        params:
            Extra API parameters.

        timeout:
            Number of seconds to wait before failing.

    Returns:
        JSON response if response is JSON.
        Text response if response is not JSON.
    """
    if params is None:
        params = {}

    # Every OpenSprinkler API call needs the password hash.
    request_params = {
        "pw": password_hash,
        **params,
    }

    response = requests.get(
        f"{HOST}{endpoint}",
        params=request_params,
        timeout=timeout,
    )

    response.raise_for_status()

    try:
        return response.json()
    except ValueError:
        return response.text


def print_json(data: Any) -> None:
    """
    Pretty-print API data.
    """
    print(json.dumps(data, indent=2))


# -----------------------------
# Read/get functions
# -----------------------------

def get_all_settings(password_hash: str) -> Dict[str, Any]:
    """
    Get all major OpenSprinkler data.

    Usually includes:
        - settings
        - programs
        - options
        - status
        - stations
    """
    return api_get("/ja", password_hash)


def get_station_settings(password_hash: str) -> Dict[str, Any]:
    """
    Get station configuration.

    Usually includes:
        - station names
        - disabled stations
        - station groups
        - master station settings
    """
    return api_get("/jn", password_hash)


def get_station_names(password_hash: str) -> List[str]:
    """
    Return only the station names as a Python list.
    """
    data = get_station_settings(password_hash)
    return data.get("snames", [])


def get_station_status(password_hash: str) -> Dict[str, Any]:
    """
    Get current station ON/OFF status.

    The 'sn' list usually contains:
        0 = station is OFF
        1 = station is ON
    """
    data = api_get("/jc", password_hash)
    return data


# -----------------------------
# Station index helpers
# -----------------------------

def ui_station_number_to_index(station_number: int) -> int:
    """
    Convert UI station number to API station index.

    In the UI:
        S01 = station number 1

    In the API:
        S01 = index 0

    Example:
        station_number 6 -> index 5
    """
    if station_number < 1:
        raise ValueError("Station number must be 1 or higher.")

    return station_number - 1


def station_index_to_name_param(station_index: int) -> str:
    """
    Convert station index to the API name parameter.

    Example:
        index 0 -> s0
        index 5 -> s5
    """
    if station_index < 0:
        raise ValueError("Station index cannot be negative.")

    return f"s{station_index}"


def make_disable_bitfield(disabled_station_numbers: List[int]) -> int:
    """
    Create the d0 disable bitfield for stations 1 to 8.

    Bit values:
        S01 = 1
        S02 = 2
        S03 = 4
        S04 = 8
        S05 = 16
        S06 = 32
        S07 = 64
        S08 = 128

    Example:
        disable S07 and S08:
            64 + 128 = 192
    """
    bitfield = 0

    for station_number in disabled_station_numbers:
        if station_number < 1 or station_number > 8:
            raise ValueError("This simple d0 function only supports stations 1 to 8.")

        station_index = ui_station_number_to_index(station_number)
        bitfield += 2 ** station_index

    return bitfield


# -----------------------------
# Station name functions
# -----------------------------

def set_station_name(
    password_hash: str,
    station_number: int,
    station_name: str,
) -> Any:
    """
    Change the name of one station.

    Example:
        set_station_name(PW, 6, "Test01")

    This changes S06 to Test01.
    """
    station_index = ui_station_number_to_index(station_number)
    name_param = station_index_to_name_param(station_index)

    return api_get(
        "/cs",
        password_hash,
        params={
            name_param: station_name,
        },
    )


def set_multiple_station_names(
    password_hash: str,
    station_names: Dict[int, str],
) -> Any:
    """
    Change multiple station names at once.

    Example:
        set_multiple_station_names(PW, {
            6: "Test01",
            7: "",
            8: "",
        })

    This:
        - renames S06 to Test01
        - clears S07 name
        - clears S08 name
    """
    params = {}

    for station_number, station_name in station_names.items():
        station_index = ui_station_number_to_index(station_number)
        name_param = station_index_to_name_param(station_index)
        params[name_param] = station_name

    return api_get("/cs", password_hash, params=params)


# -----------------------------
# Disable/activate functions
# -----------------------------

def disable_stations(
    password_hash: str,
    station_numbers: List[int],
) -> Any:
    """
    Disable station slots.

    Example:
        disable_stations(PW, [7, 8])

    This disables S07 and S08.

    Important:
        This does not delete stations.
        It marks them as disabled.
    """
    disable_value = make_disable_bitfield(station_numbers)

    return api_get(
        "/cs",
        password_hash,
        params={
            "d0": disable_value,
        },
    )


def activate_all_stations(password_hash: str) -> Any:
    """
    Activate all stations from S01 to S08.

    d0 = 0 means no stations are disabled.
    """
    return api_get(
        "/cs",
        password_hash,
        params={
            "d0": 0,
        },
    )


def activate_some_stations(
    password_hash: str,
    active_station_numbers: List[int],
    total_stations: int = 8,
) -> Any:
    """
    Activate selected stations and disable all others.

    Example:
        activate_some_stations(PW, [1, 2, 3, 4, 5, 6])

    This keeps S01 to S06 active and disables S07 and S08.
    """
    all_station_numbers = list(range(1, total_stations + 1))

    disabled_station_numbers = [
        station_number
        for station_number in all_station_numbers
        if station_number not in active_station_numbers
    ]

    disable_value = make_disable_bitfield(disabled_station_numbers)

    return api_get(
        "/cs",
        password_hash,
        params={
            "d0": disable_value,
        },
    )


# -----------------------------
# Add/remove style functions
# -----------------------------

def add_station_by_naming_slot(
    password_hash: str,
    station_number: int,
    station_name: str,
    activate_station: bool = True,
) -> Any:
    """
    Add a station by giving an existing station slot a name.

    Important:
        OpenSprinkler usually has fixed station slots.
        This function does not create a new physical station.
        It renames an existing slot.

    Example:
        add_station_by_naming_slot(PW, 6, "Test01")

    This makes S06 appear as Test01.
    """
    result = set_station_name(password_hash, station_number, station_name)

    if activate_station:
        # This simple version activates all stations.
        # Use activate_some_stations() if you want exact control.
        activate_all_stations(password_hash)

    return result


def remove_station_by_clearing_and_disabling(
    password_hash: str,
    station_number: int,
) -> Any:
    """
    Remove a station visually by:
        - clearing its name
        - disabling it

    Important:
        This does not delete the station slot.
        It hides/deactivates it logically.

    Example:
        remove_station_by_clearing_and_disabling(PW, 8)

    This clears S08 name and disables S08.
    """
    set_station_name(password_hash, station_number, "")
    return disable_stations(password_hash, [station_number])


def replace_last_three_with_test01(password_hash: str) -> Any:
    """
    Your specific requested action:

        Remove/clear:
            S06, S07, S08

        Add:
            Test01

    Safe interpretation:
        - Rename S06 to Test01
        - Clear S07
        - Clear S08
        - Keep S01 to S06 active
        - Disable S07 and S08
    """
    set_multiple_station_names(
        password_hash,
        {
            6: "Test01",
            7: "",
            8: "",
        },
    )

    return activate_some_stations(
        password_hash,
        active_station_numbers=[1, 2, 3, 4, 5, 6],
        total_stations=8,
    )


# -----------------------------
# Verification functions
# -----------------------------

def show_station_summary(password_hash: str) -> None:
    """
    Print a clean station summary:
        S01: name
        S02: name
        ...
    """
    data = get_station_settings(password_hash)

    station_names = data.get("snames", [])
    disabled_bitfields = data.get("stn_dis", [])

    disabled_value = disabled_bitfields[0] if disabled_bitfields else 0

    print("\nStation summary:")
    print("----------------")

    for index, station_name in enumerate(station_names):
        station_number = index + 1
        is_disabled = bool(disabled_value & (2 ** index))

        status_text = "DISABLED" if is_disabled else "ACTIVE"
        display_name = station_name if station_name else "(empty name)"

        print(f"S{station_number:02d}: {display_name} - {status_text}")


# -----------------------------
# Main example
# -----------------------------

if __name__ == "__main__":
    PW = make_password_hash(PASSWORD)

    print("Before:")
    show_station_summary(PW)

    print("\nApplying your requested change...")
    activate_all_stations(PW)
    set_station_name(PW, 6, "S06")
    remove_station_by_clearing_and_disabling(PW, 1)

    print("\nAfter:")
    show_station_summary(PW)
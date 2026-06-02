import hashlib
import json
import requests

# The base URL of your OpenSprinkler device.
# Your OpenSprinkler is running on your N100 PC at this IP address.
HOST = "http://192.168.100.30"

# Your OpenSprinkler password.
# Default password is usually "opendoor".
# Important: the API does not send this plain text password directly.
# It sends an MD5 hash of it.
PASSWORD = "opendoor"


def md5_password(password: str) -> str:
    """
    Convert the plain OpenSprinkler password into an MD5 hash.

    OpenSprinkler API expects the password in the 'pw' parameter
    as a lowercase MD5 hash.

    Example:
        "opendoor" -> "a6d82bced638de3def1e9bbb4983225c"
    """
    return hashlib.md5(password.encode("utf-8")).hexdigest()


# Create the hashed password once, then reuse it in every API call.
PW = md5_password(PASSWORD)


def get_station_config():
    """
    Read the current station configuration from OpenSprinkler.

    Endpoint:
        /jn

    This returns station-related JSON data, including:
        - station names
        - disabled stations
        - station groups
        - master station settings
        - other station configuration fields
    """
    response = requests.get(
        f"{HOST}/jn",
        params={
            "pw": PW,  # Required API password hash
        },
        timeout=5,  # Stop waiting after 5 seconds if no response
    )

    # Raise an error if the HTTP request failed,
    # for example 404, 500, or connection-related HTTP failure.
    response.raise_for_status()

    # Convert the JSON response into a Python dictionary.
    return response.json()


def change_station_config():
    """
    Change station configuration using the OpenSprinkler /cs endpoint.

    Goal:
        - Rename S06 to Test01
        - Clear the names of S07 and S08
        - Disable S07 and S08

    Important station index rule:
        OpenSprinkler uses zero-based station indexes in the API.

        UI name  API index  API parameter
        S01      0          s0
        S02      1          s1
        S03      2          s2
        S04      3          s3
        S05      4          s4
        S06      5          s5
        S07      6          s6
        S08      7          s7

    Important disable rule:
        d0 is a bitfield for stations 1 through 8.

        Bit 0 = S01 = value 1
        Bit 1 = S02 = value 2
        Bit 2 = S03 = value 4
        Bit 3 = S04 = value 8
        Bit 4 = S05 = value 16
        Bit 5 = S06 = value 32
        Bit 6 = S07 = value 64
        Bit 7 = S08 = value 128

        To disable S07 and S08:
            64 + 128 = 192

        So:
            d0 = 192
    """
    params = {
        # Required password hash
        "pw": PW,

        # Rename station index 5.
        # This is S06 in the UI.
        "s5": "Test01",

        # Clear station index 6 name.
        # This is S07 in the UI.
        "s6": "",

        # Clear station index 7 name.
        # This is S08 in the UI.
        "s7": "",

        # Disable S07 and S08.
        # This does not delete the station slots.
        # It marks those stations as disabled.
        "d0": 192,
    }

    response = requests.get(
        f"{HOST}/cs",
        params=params,
        timeout=5,
    )

    # Raise an error if OpenSprinkler rejected the request
    # or if the HTTP request failed.
    response.raise_for_status()

    # Return the raw response text.
    # OpenSprinkler may return something short like "1" or JSON,
    # depending on the command/result.
    return response.text


# -----------------------------
# Main program starts here
# -----------------------------

print("Before:")

# Read and print the station configuration before making changes.
before = get_station_config()

# Pretty-print the Python dictionary as formatted JSON.
print(json.dumps(before, indent=2))

print("\nApplying change...")

# Send the API request that changes station names/disabled state.
result = change_station_config()

# Print the raw result from OpenSprinkler.
print(result)

print("\nAfter:")

# Read the station configuration again to verify the change worked.
after = get_station_config()

# Pretty-print the updated station configuration.
print(json.dumps(after, indent=2))
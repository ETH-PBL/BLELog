"""
blelog/Configuration.py
Defines the `Configuration` class that holds all settings

BLELog
Copyright (C) 2024 Philipp Schilk

This work is licensed under the terms of the MIT license.  For a copy, see the 
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------
"""
from dataclasses import dataclass
from typing import Callable, List, Dict, Union
from enum import Enum
import enum

from blelog.Util import normalise_adr, normalise_char_uuid


@enum.unique
class TUI_Mode(Enum):
    CURSES = 0
    CONSOLE = 1


@dataclass
class Characteristic:
    name: str
    uuid: str
    timeout: Union[None, float]
    column_headers: List[str]
    data_decoder: Callable


@dataclass
class Configuration:
    # Device settings:
    connect_device_adrs: List[str]
    connect_device_name_regexes: List[str]
    device_aliases: Dict[str, str]
    characteristics: List[Characteristic]

    # Connection parameters:
    max_active_connections: int
    max_simultaneous_connection_attempts: int
    connection_timeout_hard: float
    connection_timeout_scan: float

    # Scanner parameters:
    scan_duration: float
    scan_cooldown: float
    seen_timeout: float
    initial_characteristic_timeout: float
    mgr_interval: float

    # Consumers settings:
    log2csv_enabled: bool
    log2csv_folder_name: str
    plotter_open_by_default: bool
    plotter_exit_on_plot_close: bool
    throughput_period_s: float

    log2sqlite_enabled: bool
    log2sqlite_db_path: str
    log2sqlite_batch_size: int

    # General settings:
    log_file: str
    plain_ascii_tui: bool
    tui_mode: TUI_Mode
    curse_tui_interval: float

    def validate_and_normalise(self):
        """
        Validates the configuration provided by the user.
        Converts bluetooth addresses and characteristic UUIDs into a standard
        format.
        """

        # normalise connect device addresses:
        self.connect_device_adrs = [normalise_adr(adr) for adr in self.connect_device_adrs]

        # normalise connect device addresses in list of aliases:
        self.device_aliases = {normalise_adr(adr): alias for adr, alias in self.device_aliases.items()}

        # normalise characteristic UUIDs:
        for char in self.characteristics:
            char.uuid = normalise_char_uuid(char.uuid)

        # Check for duplicate aliases:
        # (Can cause problems, as they are used as a file name)
        seen_aliases = []
        for alias in self.device_aliases.values():
            if alias in seen_aliases:
                print('Duplicate device alias "%s"' % alias)
                exit(-1)
            seen_aliases.append(alias)

        # Check for duplicate characteristic names:
        # (Can cause problems, as they are used as a file name)
        seen_names = []
        for char in self.characteristics:
            if char.name in seen_names:
                print('Duplicate characteristic name "%s"' % char.name)
                exit(-1)
            seen_names.append(char.name)

        # Check for duplicate characteristic UUIDs:
        seen_uuids = []
        for char in self.characteristics:
            if char.uuid in seen_uuids:
                print('Duplicate characteristic UUID "%s"' % str(char.uuid))
                exit(-1)
            seen_uuids.append(char.uuid)

    def get_characteristic(self, uuid: str) -> Characteristic:
        for c in self.characteristics:
            if c.uuid == normalise_char_uuid(uuid):
                return c
        raise KeyError()

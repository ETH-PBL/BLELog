"""
config.py
Configuration Options.

BLELog
Copyright (C) 2024 Philipp Schilk

This work is licensed under the terms of the MIT license.  For a copy, see the
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------
"""
from blelog.Configuration import Characteristic, Configuration, TUI_Mode
from char_decoders import *

config = Configuration(
    # ======================= Devices ============================

    # Connect via address:
    # A list of addresses that BLELog will attempt to connect to:
    connect_device_adrs=[
        'E3:11:20:62:5D:3F',
    ],

    # Connect via device name:
    # A list of regexes. If a device's name matches any of the
    # regexes below, BLELog will attempt to connect to it:
    connect_device_name_regexes=[
        r'ETH_BLE'
    ],

    # Device nicknames:
    # An (optional) alias to identify a given address by.
    # Used for status logging, TUI information, and file names.
    # If provided, it has to be unique.
    device_aliases={
        'E3:11:20:62:5D:3F': 'Gadget007',
    },

    # Characteristics:
    # The list of characteristics that BLELog should subscribe to.
    characteristics=[
        Characteristic(
            # A name to identify the characteristics by:
            # Has to be unique.
            name='demo_char_data',

            # UUID:
            # Has to be unique.
            uuid='00002222-8e22-4541-9d4c-21edae82ed19',

            # Timeout (in seconds) for this characteristics:
            # If no notifications are received after this amount
            # of time, the connection is closed. Set to 'None'
            # to disable.
            timeout=3,

            # The data decoder function.
            # Produces a list data-rows from the received bytearray Defined in
            # char_decoders.py
            # See `char_decoders.py` for more infos.
            data_decoder=decode_demo_char_data,

            # Column names for the information returned by the decoder function:
            # See `char_decoders.py` for more infos.
            column_headers=['idx', 'data']

        ),
        
        Characteristic(
            name='demo_char_btn',
            uuid='00002223-8e22-4541-9d4c-21edae82ed19',
            timeout=None,
            data_decoder=decode_demo_char_btn,
            column_headers=['data']
        ),

        # ... Additional characteristics
    ],

    # ================ Connection Parameters =====================
    # Maximum number of simultaneously active connections:
    max_active_connections=3,

    # Maximum time an establishing a connection can take before being aborted:
    connection_timeout_hard=30,

    # Maximum time the scan performed during a connection can take before
    # being aborted:
    # (This is a bleak parameter, and is not documented very well. Sorry.)
    connection_timeout_scan=20,

    # Maximum number of simultaneous connection attempts:
    # Anything higher than one tends to cause instability.
    max_simultaneous_connection_attempts=1,

    # Initial Characteristic Timeout:
    # An additional amount of time (in seconds) allowed in addition to the
    # characteristic timeout for the first notification.
    initial_characteristic_timeout=10,

    # Manager Interval:
    # Time in seconds between connection manager attempting to
    # create new connections
    mgr_interval=1,

    # ================== Scanner Parameters ======================
    # Time, in seconds, a scan should last:
    # Increasing this may help if devices are not being discovered:
    scan_duration=3,

    # Time, in seconds, to pause between scans:
    scan_cooldown=0.1,

    # Last-seen timeout:
    # BLElog will only attempt to connect to a device if it has been
    # recently seen by the scanner. This is the time (in seconds) that a
    # device will be marked as 'recently seen' after being seen.
    seen_timeout=20,

    # ================== Consumer Settings ======================
    # Enable/disable logging of data to CSV files:
    log2csv_enabled=True,

    # CSV output folder name:
    # IMPORTANT: Make sure this folder exists, otherwise logging will
    # fail. BLElog will *not* attempt to create it!
    log2csv_folder_name="output_csv",

    # Automatically open the data plot GUI on startup:
    # Useful in 'CONSOLE' tui mode, as the plotter cannot
    # be manually opened.
    plotter_open_by_default=True,

    # Shut down BLElog when the plot GUI is closed:
    # Not recommended. This will stop BLElog if plotting fails
    # for any reason. Useful during testing/in CONSOLE mode.
    plotter_exit_on_plot_close=False,

    # ================== General Settings ======================

    # Text file name for status log output:
    # Set to 'None' to disable.
    log_file='log.txt',

    # Turn the TUI into plain ASCII:
    # Much less fun, much more compatible.
    plain_ascii_tui=False,

    # TUI Mode:
    # CURSES: Fancy dashboard. Tons of fun, sometimes not that compatible.
    # CONSOLE: log-only console output. Much less fun, much more compatible.
    tui_mode=TUI_Mode.CURSES,

    # CURSE TUI update interval (in seconds):
    curse_tui_interval=0.33,

    # Time period (in seconds) over which to calculate RX throughput.
    # set to `None` to disable.
    throughput_period_s=2
)

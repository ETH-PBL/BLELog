"""
BLELog.py
A simple python BLE data logger which receives, decodes, stores, and plots
characteristic data in real time, that has proven quite convenient and flexible.

BLELog
Copyright (C) 2024 Philipp Schilk

This work is licensed under the terms of the MIT license.  For a copy, see the
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------
"""
import asyncio
import logging
import signal
import sys
from asyncio import Event

import blelog.Logging as Logging
import config
from blelog.ConnectionMgr import ConnectionMgr
from blelog.ConsumerMgr import ConsumerMgr
from blelog.consumers.log2csv import Consumer_log2csv
from blelog.consumers.log2sqlite import Consumer_log2sqlite
from blelog.consumers.plotter import Consumer_plotter
from blelog.consumers.throughput import Consumer_throughput
from blelog.curses_tui_components.Connections_TUI import Connections_TUI
from blelog.curses_tui_components.Log_TUI import Log_TUI
from blelog.curses_tui_components.q_debug_TUI import q_TUI
from blelog.curses_tui_components.Scanner_TUI import Scanner_TUI
from blelog.Scanner import Scanner
from blelog.TUI import TUI


# noinspection SpellCheckingInspection
async def main():
    # Grab configuration from config.py and clean it up:
    configuration = config.config
    configuration.validate_and_normalise()

    # Setup log:
    Logging.setup_logging(configuration)

    # Create Data Consumers and Consumer Manager:
    consume_mgr = ConsumerMgr(configuration)

    if configuration.log2csv_enabled:
        consume_log2csv = Consumer_log2csv(configuration)
        consume_mgr.add_consumer(consume_log2csv)

    if configuration.log2sqlite_enabled:
        consume_log2sqlite = Consumer_log2sqlite(configuration)
        consume_mgr.add_consumer(consume_log2sqlite)

    consume_plot = Consumer_plotter(configuration)
    consume_mgr.add_consumer(consume_plot)
    
    if configuration.throughput_period_s is not None:
        consume_throughput = Consumer_throughput(configuration)
        consume_mgr.add_consumer(consume_throughput)

    # Create the scanner:
    scnr = Scanner(config=configuration)

    # Create the connection manager:
    con_mgr = ConnectionMgr(configuration, scnr, consume_mgr.input_q)

    # Create the TUI:
    tui = TUI(configuration)

    tui_scanner = Scanner_TUI(scnr, configuration)
    tui.add_component(tui_scanner)
    tui_conns = Connections_TUI(con_mgr, configuration)
    tui.add_component(tui_conns)
    tui_q = q_TUI(con_mgr, consume_mgr)
    tui.add_component(tui_q)
    tui_log = Log_TUI(configuration)
    tui.add_component(tui_log)

    tui.set_plot_toggle(consume_plot.toggle_on_off)

    # Re-route SIGINT (Interruption, i.e. due to CTRL-C) to a handler to
    # allow cleanup:
    halt_event = Event()
    panic_count = [0]

    def halt_hndlr(*_):
        # Set halt event
        print('\r\n[%i] Interrupted! Shutting down... This may take a few seconds. '
              'Interrupt 3 times to panic abort.\r\n' % panic_count[0])
        halt_event.set()

        # immediately turn of TUI:
        tui.off()

        # If this happens 3 times, kill the program:
        panic_count[0] += 1
        if panic_count[0] >= 3:
            print('[Panic Abort]')
            sys.exit(-1)

    signal.signal(signal.SIGINT, halt_hndlr)
    tui.set_halt_handler(halt_hndlr)

    # Startup:

    # Run the logger, scanner, tui, and consumer manager:
    scnr_task = asyncio.create_task(scnr.run(halt_event))
    con_mgr_task = asyncio.create_task(con_mgr.run(halt_event))
    tui_task = asyncio.create_task(tui.run(halt_event))
    consume_mgr_task = asyncio.create_task(consume_mgr.run(halt_event))

    logging.getLogger('log').info('Starting!')

    await asyncio.gather(scnr_task, con_mgr_task, tui_task, consume_mgr_task)

if __name__ == '__main__':
    asyncio.run(main(), debug=True)

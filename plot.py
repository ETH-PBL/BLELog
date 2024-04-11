"""
plot.py
The matplotlib plotting script to render the live data display.

BLELog
Copyright (C) 2024 Philipp Schilk

This work is licensed under the terms of the MIT license.  For a copy, see the
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------

# Introduction

The function plot(...) defined below is called by BLELog to display a live
graph of the data received.

You *will* have to update this file and adjust the plots to fit the data
you are receiving and wanting to display.

# Overview

The plot function does the following:

    - Set up a matplotlib plot
    - Set up some deques to hold the most recent data
    - Set up a matplotlib plot
    - define the function 'animate', which gets called by
      matplotlib repeatedly to update the plot

animate(_) in turn does the following:

    - Get data from the input data_queue, and send it to the correct deque
    - Clear the plot
    - Re-draw the plot with the most recent data.

Data arrives via the process-safe and thread-safe queue 'data_queue' in the
form of NotifData objects:

    @dataclass
    class NotifData:
        device_adr: str                  # Bluetooth address
        device_name_repr: str            # Alias, Device Name, or address
        characteristic: Characteristic   # The characteristic that received this
                                         # data (as defined in config.py)
        data: List[List[Any]]            # The output of the decoder function
                                         # (as defined in char_decoders.py and
                                         # set in config.py)
        data_raw: bytearray              # Raw received data

# Important Notes

Multi-threading in python is a whole can of worms.
(See 'https://en.wikipedia.org/wiki/Global_interpreter_lock')

Matplotlib cannot run in any thread but the main one - and even
if it could, the GIL-related limitations of python would likely cause
it to interfere with reliable data reception.

To get around this, BLELog runs this function (and hence matplotlib) in
a *completely separate* python interpreter. This means that this function
*cannot* directly access any of the internal state of BLELog.

It's only means of communication are:

    - data_queue: A process- and thread-safe queue where data arrives.

    - getLogger('log'): A logger that can be used for debug output - It too
      gets re-routed back to the main BLELog process using a queue.

This keeps things separate, allows matplotlib to run in its own process,
and avoids it from interfering with data logging.
"""

import logging
import multiprocessing as mp
import queue
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from blelog.ConsumerMgr import NotifData


def plot(data_queue: mp.Queue):
    # If you want to print anything, don't use print(..) -
    # Use the logger:
    log = logging.getLogger('log')
    # log.info('Helllooooooo wooooorld!')

    # Place to store the address of the device we are plotting data from, to
    # avoid plotting data from two simulatanously connected devices in the same plot:
    # Note: This plot function will only plot data for the first device it receives
    # notifications from.

    plot_device_adr = []

    # Setup plot with 2 subplots:
    fig1, (ax1, ax2) = plt.subplots(2)
    axs = [ax1, ax2]

    # Setup deques to hold data that will be plotted:
    # 'maxlen' controls the maximum number of data points shown.
    data_dqs = {
        'demo_data_idx': deque(maxlen=3000),
        'demo_data': deque(maxlen=3000),
        'demo_btn': deque(maxlen=300),
    }

    # Animation function called repeatedly by matplotlib.
    # Grabs data from the input queues and pushes it to the correct
    # deque before updating the plot.
    def animate(_):
        # Grab as much data from the input queue as possible:
        while True:
            try:
                # Get a NotifData object:
                notif_data = data_queue.get_nowait()  # type: NotifData

                if len(plot_device_adr) == 0:
                    # We have not received any data yet. Remember the
                    # address of this device and ignore any data
                    # originating from other addresses from here
                    # on out:
                    plot_device_adr.append(notif_data.device_adr)
                    log.info(f"Plotter showing data for device `{notif_data.device_name_repr}`")
                else:
                    # Ignore data if coming from any address other than
                    # the one we received data from first:
                    if notif_data.device_adr not in notif_data.device_adr:
                        continue

                # Process each notification and put the data into the
                # correct deques:
                # 'notif_data.data' contains the return value of the char decoder function.
                if notif_data.characteristic.name == "demo_char_data":
                    for row in notif_data.data:
                        data_dqs['demo_data_idx'].append(row[0])
                        data_dqs['demo_data'].append(row[1])
                elif notif_data.characteristic.name == "demo_char_btn":
                    for row in notif_data.data:
                        data_dqs['demo_btn'].append(row[0])
                # elif notif_data.characteristic.name == "some other char"
                # ...
                else:
                    log.warn(f"Plotter received data from unknown char '{notif_data.characteristic.name}'")

            except queue.Empty:
                break

        # Clear
        for ax in axs:
            ax.clear()

        # titles
        ax1.set_title("Demo Characteristic: 'Data'")
        ax2.set_title("Demo Characteristic: 'Btn'")

        # plot data
        ax1.plot(data_dqs['demo_data_idx'], data_dqs['demo_data'], linewidth=0.5, label="red")
        ax2.plot(data_dqs['demo_btn'], linewidth=0.5, label="red")

        # adjust layout
        fig1.tight_layout()

    # Start plot
    _ = FuncAnimation(fig1, animate)  # type: ignore
    plt.show()

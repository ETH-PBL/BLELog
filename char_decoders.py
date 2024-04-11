"""
char_decoders.py
Characteristic data decoding.

BLELog
Copyright (C) 2024 Philipp Schilk

This work is licensed under the terms of the MIT license.  For a copy, see the
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------

# Overview

Decoder functions used to convert the raw bytearray received
from characteristic notifications into actual data.

Should return a list of data rows/samples, where each
data row in turn is a list one or more values/columns, usually numbers.

Each data row should be of the same length as the column_headers
set for the characteristic in config.py where this decoder is used.

Confusing, I know, I'm sorry.

# Example 1

Assume we have a 'demo_char' characteristic, where each notification
consists of multiple values/readings ('data rows'), with each one
of those values made up of an 'index' and 'data' (two 'data columns'
per row).

The column headers for this characteristic are defined as follows in config.py:

    ```py
    column_headers=['idx', 'data']
    ```

Now assume a notification is received that contains the following data (encoded
into a binary blob/bytearray):

    - Reading/Row 1: idx = 1, data = 101
    - Reading/Row 1: idx = 2, data = 202

The characteristic decoder function should return the decoded the data in the
following format:

    ```py
    [[1, 101],
     [2, 202]]
    ```

# Example 2

Assume a characteristic where each notification contains
multiple numeric readings. The characteristic should be configured for
a single header in config.py:

    ```py
    column_headers=['data']
    ```

And the char_decoder function, for a notification that encodes the
values [1, 2, 3, 4, 5], should return:

    ```py
    [[1],
     [2],
     [3],
     [4],
     [5]]
    ```

Note that each reading is enclosed in an individual list!

# Example 3

Assume a characteristic where each notification contains a single number. The
characteristic should be configured for a single header in config.py:

    ```py
    column_headers=['data']
    ```

And the char_decoder function, for a notification that encodes the
value 42, should return:

    ```py
    [[42]]
    ```

Note the double list!

# Logging/Printing: IMPORTANT!

If you wish to print any debug information, **do not** use
print(...) - The output will likely be lost if the console TUI is not used.
Instead, get a logger as follows:

    ```py
    log = logging.getLogger('log')
    ```

And use it to print:

    ```py
    log.info('...')
    log.warning('...')
    log.error('...')
    ```
"""
import logging
import struct
from typing import Any, List


def decode_demo_char_data(data: bytearray) -> List[List[Any]]:
    # Each notification consists of 40 readings, with each
    # reading made up of a 16-bit little-endian unsigned index
    # and a 16-bit little-endian signed value.
    # The columns are configured as follows in config.py:
    # ```py
    #   column_headers=['idx', 'data']
    # ```

    # Logger:
    log = logging.getLogger('log')

    # Validate data length:
    if len(data) != 180:
        log.warning('Malformed demo data, rejecting...')
        return []

    # Decode:
    result = []

    for i in range(40):
        # Grab 4 bytes for sample at position i
        row_bytes = data[4*i:4*i+4]
        # Decode:
        # (See https://docs.python.org/3/library/struct.html)
        idx_val, data_val = struct.unpack('<Hh', row_bytes)
        result.append([idx_val, data_val])

    return result


def decode_demo_char_btn(data: bytearray) -> List[List[Any]]:
    # Logger:
    log = logging.getLogger('log')

    # Validate data length:
    if len(data) != 1:
        log.warning('Malformed demo btn, rejecting...')
        return []

    # Decode:
    return [[int.from_bytes(data, byteorder='big')]]

"""
blelog/consumers/log2csv.py
Data consumer that writes data to CSV files.

BLELog
Copyright (C) 2024 Philipp Schilk

This work is licensed under the terms of the MIT license.  For a copy, see the 
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------
"""
import asyncio
import csv
import io
import logging
import os
from asyncio.locks import Event
from asyncio.queues import Queue
from typing import List

import aiofiles

from blelog.Configuration import Configuration
from blelog.ConsumerMgr import Consumer, NotifData


class CSVLogger:
    def __init__(self, file_path: str, column_headers: List[str]):
        self.file_path = file_path
        self.input_q = Queue()
        self.column_headers = column_headers
        self.active = True

    async def run(self, halt: Event):
        log = logging.getLogger('log')
        f = None

        try:
            if os.path.exists(self.file_path):
                f = await aiofiles.open(self.file_path, 'a', newline='')
                # log.info('Opened %s' % self.file_path)
            else:
                f = await aiofiles.open(self.file_path, 'w', newline='')
                await self.write_row(f, self.column_headers)
                # log.info('Created %s' % self.file_path)

            while not (halt.is_set() and self.input_q.empty()):
                try:
                    next_data = await asyncio.wait_for(self.input_q.get(), timeout=0.5)  # type: NotifData
                    await self.write_rows(f, next_data.data)
                    await f.flush()
                    self.input_q.task_done()
                except asyncio.TimeoutError:
                    pass
        except FileNotFoundError as e:
            log.error('CSVLogger %s encountered an exception: %s' % (self.file_path, str(e)))
            log.exception(e)
        except Exception as e:
            log.error('CSVLogger %s encountered an exception: %s' % (self.file_path, str(e)))
            log.exception(e)
            halt.set()
        finally:
            self.active = False
            if f is not None:
                await f.close()
            # print('CSVLogger %s shut down...' % self.file_path)

    async def write_row(self, f, row):
        row_str_io = io.StringIO()
        csv_writer = csv.writer(row_str_io)
        csv_writer.writerow(row)

        await f.write(row_str_io.getvalue())

    async def write_rows(self, f, rows):
        row_str_io = io.StringIO()
        csv_writer = csv.writer(row_str_io)

        for row in rows:
            csv_writer.writerow(row)

        await f.write(row_str_io.getvalue())


class Consumer_log2csv(Consumer):
    def __init__(self, config: Configuration):
        super().__init__()
        self.config = config
        self.file_outputs = {}
        self.tasks = []

    async def run(self, halt: Event):
        log = logging.getLogger('log')

        try:
            while not (halt.is_set() and self.input_q.empty()):
                try:
                    next_data = await asyncio.wait_for(self.input_q.get(), timeout=0.5)  # type: NotifData
                    await self._log_to_file(next_data, halt)
                except asyncio.TimeoutError:
                    pass

        except Exception as e:
            log.error('Consumer log2csv encountered an exception: %s' % str(e))
            log.exception(e)
            halt.set()
        finally:
            total_output_q = sum([c.input_q.qsize() for c in self.file_outputs.values()])
            if total_output_q > 0:
                print('Consumer log2csv ready to shut down. Waiting for %i items in output queues...' % total_output_q)
            await asyncio.gather(*self.tasks)
            print('Consumer log2csv shut down...')

    async def _log_to_file(self, next_data: NotifData, halt: Event):
        # determine file path:
        file_path = self.file_path(next_data.device_adr, next_data.characteristic)

        if file_path not in self.file_outputs:
            # File not yet opened, open:
            file_output = CSVLogger(file_path, next_data.characteristic.column_headers)
            self.file_outputs[file_path] = file_output
            file_task = asyncio.create_task(self.file_outputs[file_path].run(halt))
            self.tasks.append(file_task)

        if self.file_outputs[file_path].active:
            # Open, write:
            await self.file_outputs[file_path].input_q.put(next_data)

    def file_path(self, device_adr, char):
        if device_adr in self.config.device_aliases:
            name = self.config.device_aliases[device_adr]
        else:
            name = device_adr
            name = device_adr.replace(':', '_')

        n = "%s_%s.csv" % (name, char.name)
        n = n.replace(' ', '_')
        return os.path.join(self.config.log2csv_folder_name, n)

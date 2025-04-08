"""
blelog/consumers/log2sqlite.py
Data consumer that writes data to a single SQLite database.

BLELog
Copyright (C) 2025 Silvano Cortesi
Based on log2csv by Philipp Schilk, 2024

This work is licensed under the terms of the MIT license.  For a copy, see the
included LICENSE file or <https://opensource.org/licenses/MIT>.
---------------------------------
"""
import asyncio
import logging
import os
import re  # For sanitizing names
from datetime import datetime
from asyncio.locks import Event
from asyncio.queues import Queue
from typing import List, Set, Tuple, Any, Dict

import aiosqlite

from blelog.Configuration import Configuration
from blelog.ConsumerMgr import Consumer, NotifData

log = logging.getLogger('log')

def sanitize_sql_identifier(name: str) -> str:
    """Sanitizes a string to be a valid SQL identifier (table/column name)."""
    # Remove invalid characters (keep alphanumeric and underscore)
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # Ensure it doesn't start with a digit (prepend underscore if it does)
    if name[0].isdigit():
        name = '_' + name

    return name.lower()

class Consumer_log2sqlite(Consumer):
    def __init__(self, config: Configuration):
        super().__init__()
        self.config = config
        self._db_conn = None # Holds the aiosqlite connection
        self._known_tables: Set[str] = set() # Cache for created tables
        self._halt_event: Event = None # To signal shutdown internally if needed

    async def _ensure_db_connection(self):
        """Establishes DB connection if not already connected."""
        if self._db_conn is None:
            try:
                # Ensure directory exists
                db_dir = os.path.dirname(self.config.log2sqlite_db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
                    log.info(f"Created directory for database: {db_dir}")

                self._db_conn = await aiosqlite.connect(self.config.log2sqlite_db_path)

                log.info(f"Connected to SQLite database: {self.config.log2sqlite_db_path}")
            except Exception as e:
                log.error(f"Failed to connect to database {self.config.log2sqlite_db_path}: {e}")
                log.exception(e)
                if self._halt_event:
                    self._halt_event.set() # Signal main loop to stop
                raise # Re-raise to stop the consumer run

    async def _close_db_connection(self):
        """Closes the DB connection if open."""
        if self._db_conn:
            try:
                await self._db_conn.commit() # Ensure any pending changes are saved
                await self._db_conn.close()
                log.info(f"Closed connection to SQLite database: {self.config.log2sqlite_db_path}")
                self._db_conn = None
            except Exception as e:
                log.error(f"Error closing database connection {self.config.log2sqlite_db_path}: {e}")
                log.exception(e)

    async def _create_table_if_not_exists(self, table_name: str, column_headers: List[str]):
        """Creates a table for a characteristic if it doesn't exist."""
        if table_name in self._known_tables:
            return

        if not self._db_conn:
            log.error("Database connection is not available for table creation.")
            return

        sanitized_headers = [sanitize_sql_identifier(h) for h in column_headers]

        # Define columns - characteristic data.
        column_definitions = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT",  # Auto-incrementing primary key
            "device_name TEXT NOT NULL",          # Device alias or address
        ]
        column_definitions.extend([f"{header} TEXT" for header in sanitized_headers])

        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_definitions)})"

        try:
            log.debug(f"Executing: {create_sql}")
            await self._db_conn.execute(create_sql)
            await self._db_conn.commit()
            self._known_tables.add(table_name)
            log.info(f"Ensured table '{table_name}' exists with columns: id, device_name, {', '.join(sanitized_headers)}")
        except Exception as e:
            log.error(f"Failed to create table {table_name}: {e}")
            log.exception(e)

            if self._halt_event:
                 self._halt_event.set()

    async def _insert_batch(self, table_name: str, column_headers: List[str], data_batch: List[Tuple[str, Tuple[Any, ...]]]):
        """Inserts a batch of data rows into the specified table."""
        if not self._db_conn:
             log.error(f"Database connection is not available for batch insertion into {table_name}.")
             return

        if not data_batch:
            log.debug(f"No data provided for batch insert into {table_name}.")
            return

        sanitized_headers = [sanitize_sql_identifier(h) for h in column_headers]
        all_columns = ["device_name"] + sanitized_headers

        # Prepare column names and placeholders for the INSERT statement
        placeholders = ", ".join(["?"] * len(all_columns))
        column_names_sql = ", ".join(all_columns)

        insert_sql = f"INSERT INTO {table_name} ({column_names_sql}) VALUES ({placeholders})"

        # Prepare the list of value tuples for executemany
        # Expected input format for data_batch: List[Tuple[device_name, tuple_of_data_values]]
        values_list = []
        expected_data_len = len(sanitized_headers)
        for device_name, data_tuple in data_batch:
            if len(data_tuple) != expected_data_len:
                log.warning(f"Data length mismatch in batch for table {table_name}. Expected {expected_data_len} columns (headers: {sanitized_headers}), got {len(data_tuple)} (data: {data_tuple}) for device {device_name}. Skipping row.")
                continue
            values_list.append((device_name,) + data_tuple)

        if not values_list:
            log.warning(f"Batch for table {table_name} resulted in no valid rows after validation.")
            return

        try:
            log.debug(f"Executing batch insert into {table_name} with {len(values_list)} rows.")
            await self._db_conn.executemany(insert_sql, values_list)
            await self._db_conn.commit() # Commit after the batch operation
            log.debug(f"Successfully inserted batch of {len(values_list)} rows into {table_name}.")
        except Exception as e:
            log.error(f"Failed to insert batch data into {table_name}: {e}")
            log.exception(e)

    async def run(self, halt: Event):
        """Main execution loop for the SQLite consumer."""
        self._halt_event = halt # Store halt event for internal use if needed
        log.info(f"Consumer log2sqlite started. Logging to {self.config.log2sqlite_db_path}. Batch size: {self.config.log2sqlite_batch_size}")

        try:
            await self._ensure_db_connection()

            while not halt.is_set(): # Loop until halt is set
                batch_to_process: List[NotifData] = []
                try:
                    # 1. Get the first item (wait if necessary)
                    first_data: NotifData = await asyncio.wait_for(self.input_q.get(), timeout=0.5)
                    batch_to_process.append(first_data)
                    self.input_q.task_done() # Mark first item as processed

                    # 2. Greedily collect more items up to batch size without waiting
                    while len(batch_to_process) < self.config.log2sqlite_batch_size:
                        try:
                            next_data: NotifData = self.input_q.get_nowait()
                            batch_to_process.append(next_data)
                            self.input_q.task_done() # Mark subsequent items as processed
                        except asyncio.QueueEmpty:
                            # No more items readily available, process what we have
                            break

                    # 3. Group data by table name (characteristic)
                    grouped_batch: Dict[str, Dict[str, Any]] = {}
                    # Structure: { table_name: {'headers': List[str], 'rows': List[Tuple[device_name, Tuple[Any,...]]]} }

                    for item in batch_to_process:
                        # Determine device name
                        device_name = self.config.device_aliases.get(item.device_adr, item.device_adr)
                        # Sanitize characteristic name for use as table name
                        table_name = sanitize_sql_identifier(item.characteristic.name)

                        if table_name not in grouped_batch:
                            grouped_batch[table_name] = {
                                'headers': item.characteristic.column_headers, # Store headers once per table per batch
                                'rows': []
                            }
                        # Basic check: Ensure headers are consistent within the batch for the same table
                        elif grouped_batch[table_name]['headers'] != item.characteristic.column_headers:
                             log.warning(f"Inconsistent headers for characteristic '{item.characteristic.name}' (table '{table_name}') within the same batch. Sticking with first encountered headers. Device: {device_name}")
                             # We'll use the headers already stored and might skip this row in _insert_batch if length mismatches

                        # Append (device_name, data_tuple) for each data item
                        for data_item in item.data:
                            grouped_batch[table_name]['rows'].append((device_name, tuple(data_item)))

                    # 4. Process each group (table)
                    for table_name, data_info in grouped_batch.items():
                        headers = data_info['headers']
                        rows = data_info['rows'] # List[Tuple[device_name, Tuple[Any,...]]]

                        if not rows: continue # Skip if no rows ended up in this group (e.g., due to header inconsistency warnings)

                        # Ensure the table exists
                        await self._create_table_if_not_exists(table_name, headers)

                        # Insert the batch of data for this table
                        await self._insert_batch(table_name, headers, rows)


                except asyncio.TimeoutError:
                    # No data received in the initial wait, check halt condition and loop again
                    if halt.is_set() and self.input_q.empty():
                         break # Exit if halted and queue is definitively empty
                    continue # Otherwise, just continue checking
                except Exception as e:
                    log.error(f"Consumer log2sqlite encountered an error processing a batch: {e}")
                    log.exception(e)
                    # Ensure task_done was called for items already removed from queue.
                    # If error happened *during* processing, items might be lost.
                    # Depending on where the exception occurred, some items might
                    # have been processed, others not. task_done was called upon retrieval.


            # --- End of main loop ---

            # Process any remaining items if halt was set but queue wasn't empty initially
            log.info("Halt signal received, processing remaining items in queue...")
            while not self.input_q.empty():
                 # Simplified processing for remaining items (could also batch here if desired)
                 # For simplicity, reuse the batching logic but don't wait.
                 batch_to_process: List[NotifData] = []
                 while len(batch_to_process) < self.config.log2sqlite_batch_size:
                      try:
                          item = self.input_q.get_nowait()
                          batch_to_process.append(item)
                          self.input_q.task_done()
                      except asyncio.QueueEmpty:
                          break

                 if not batch_to_process: break # Should not happen if !input_q.empty(), but safe check

                 # Group and process this final batch
                 grouped_batch: Dict[str, Dict[str, Any]] = {}
                 for item in batch_to_process:
                     device_name = self.config.device_aliases.get(item.device_adr, item.device_adr)
                     table_name = sanitize_sql_identifier(item.characteristic.name)
                     if table_name not in grouped_batch:
                         grouped_batch[table_name] = {'headers': item.characteristic.column_headers, 'rows': []}
                     elif grouped_batch[table_name]['headers'] != item.characteristic.column_headers:
                         log.warning(f"[Shutdown] Inconsistent headers for {table_name}. Skipping item.")
                         continue
                     for data_item in item.data:
                         grouped_batch[table_name]['rows'].append((device_name, tuple(data_item)))

                 for table_name, data_info in grouped_batch.items():
                     if data_info['rows']:
                        await self._create_table_if_not_exists(table_name, data_info['headers'])
                        await self._insert_batch(table_name, data_info['headers'], data_info['rows'])

            log.info("Finished processing remaining queue items.")


        except Exception as e:
            # Catch errors during setup (like DB connection) or unexpected loop exit
            log.error(f'Consumer log2sqlite encountered a critical exception: {e}')
            log.exception(e)
            halt.set() # Ensure halt is set if a major error occurs
        finally:
            log.info('Consumer log2sqlite shutting down...')
            if not self.input_q.empty():
                 # This should ideally not happen if the shutdown logic worked
                 log.warning(f"Consumer log2sqlite shutting down UNEXPECTEDLY with {self.input_q.qsize()} items remaining in the queue.")

            # Close the database connection gracefully
            await self._close_db_connection()
            log.info('Consumer log2sqlite shut down complete.')

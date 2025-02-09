#!/usr/bin/env python3

import argparse
import socketio
import json
import time
import sqlite3
from escpos.printer import Usb
from datetime import datetime
import threading
import logging
import os
from typing import Dict, Any
from print_receipt import print_receipt


logging.root.setLevel(logging.INFO)

if logging.root.handlers:
    handler = logging.root.handlers[0]

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    handler.setFormatter(formatter)
else:
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

DB_NAME = 'printer_queue.db'


def initialize_db():
    """Initialize the SQLite database and create table if not exists."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS print_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_data TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_attempt TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            last_error TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized/checked.")


class PrinterQueue:
    def __init__(self):
        initialize_db()

    def add_to_queue(self, receipt_data: Dict[str, Any]) -> int:
        """Add a receipt to the queue."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO print_jobs (receipt_data, created_at)
            VALUES (?, ?)
        """, (json.dumps(receipt_data), now))
        job_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Added job {job_id} to queue")
        return job_id

    def get_next_job(self) -> tuple[int, dict] | None:
        """Get the next pending job from the queue."""
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row  # To access columns by name
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, receipt_data, attempts
            FROM print_jobs
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['id'], json.loads(row['receipt_data']), row['attempts']
        return None

    def mark_job_complete(self, job_id: int):
        """Mark a job as completed."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE print_jobs
            SET status = 'completed'
            WHERE id = ?
        """, (job_id,))
        conn.commit()
        conn.close()
        logger.info(f"Job {job_id} completed successfully")

    def mark_job_failed(self, job_id: int, error: str):
        """Mark a job as failed and update retry information."""
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE print_jobs
            SET status = 'pending',
                attempts = attempts + 1,
                last_attempt = ?,
                last_error = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), str(error), job_id))
        conn.commit()
        conn.close()
        logger.warning(
            f"Job {job_id} marked as failed, attempt incremented. Error: {error}")


class PrinterManager:
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.printer = None
        self.queue = PrinterQueue()
        self.max_retries = 3
        self.initial_retry_delay = 0.5

    def connect_printer(self) -> bool:
        """Attempt to connect to the printer."""
        try:
            self.printer = Usb(self.vendor_id, self.product_id)
            self.printer.hw('INIT')
            logger.info("Printer connected successfully!")
            return True
        except Exception as e:
            logger.error(f"Error connecting to printer: {e}")
            self.printer = None
            return False

    def process_queue(self):
        """Main loop for processing the print queue."""
        # Process pending jobs at startup
        self.process_pending_jobs_at_startup()

        while True:
            try:
                job_info = self.queue.get_next_job()
                if job_info:
                    job_id, job_data, attempts = job_info
                    self.print_receipt_with_retry(job_id, job_data, attempts)
                else:
                    time.sleep(1)  # Wait before checking for new jobs
            except Exception as e:
                logger.error(f"Error in process_queue loop: {e}")
                time.sleep(1)

    def process_pending_jobs_at_startup(self):
        """Process any pending jobs in the database at startup."""
        while True:
            job_info = self.queue.get_next_job()
            if not job_info:
                break  # No more pending jobs
            job_id, job_data, attempts = job_info
            logger.info(
                f"Processing pending job {job_id} from database on startup.")
            success = self.print_receipt_with_retry(job_id, job_data, attempts)
            if not success:
                logger.error(
                    f"Failed to process job {job_id} on startup, check logs for details.")

    def print_receipt_with_retry(self, job_id: int, receipt_data: dict, attempts: int) -> bool:
        """Attempt to print a receipt with retry logic."""
        retries_remaining = self.max_retries - attempts
        if retries_remaining <= 0:
            logger.error(
                f"Job {job_id} exceeded maximum retries. Logging failure.")
            # Mark as failed in db, even though status is already pending
            self.queue.mark_job_failed(job_id, "Exceeded maximum retries")
            return False

        for attempt in range(retries_remaining):
            try:
                if not self.printer:
                    if not self.connect_printer():
                        raise Exception("Printer not available")

                print_receipt(receipt_data, self.printer)
                self.queue.mark_job_complete(job_id)
                return True  # Successfully printed

            except Exception as e:
                retry_delay = self.initial_retry_delay * \
                    (2**attempt)  # Exponential backoff
                logger.warning(
                    f"Print attempt {attempts + attempt + 1}/{self.max_retries} for job {job_id} failed: {e}. "
                    f"Retrying in {retry_delay:.2f} seconds..."
                )
                self.printer = None  # Reset printer connection on failure
                time.sleep(retry_delay)

        # If all retries failed
        logger.error(f"Job {job_id} failed after {self.max_retries} attempts.")
        self.queue.mark_job_failed(job_id, str(e))  # e from the last exception
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Run the script in dev or prod mode.')
    parser.add_argument('--mode', '-m', choices=['dev', 'prod'], default='prod',
                        help='Specify the mode: dev or prod. Defaults to prod.')
    args = parser.parse_args()

    if args.mode == 'dev':
        SOCKET_IO_SERVER_URL = 'ws://localhost:5001'
    else:
        SOCKET_IO_SERVER_URL = 'wss://ws-cafe.bitrey.it'
    SOCKET_IO_NAMESPACE = '/purchase'

    logger.info(f"Running in {args.mode} mode")

    # Initialize printer manager
    printer_manager = PrinterManager(
        vendor_id=int("0x1fc9", 16),
        product_id=int("0x2016", 16)
    )

    logger.info("Starting printer queue processor...")

    # Start queue processor in a separate thread
    queue_thread = threading.Thread(
        target=printer_manager.process_queue, daemon=True)
    queue_thread.daemon = True  # Set as daemon thread so it exits when main thread exits
    queue_thread.start()

    # Socket.IO setup
    sio = socketio.Client()

    logger.info("Starting WebSocket connection...")

    @sio.event(namespace=SOCKET_IO_NAMESPACE)
    def connect():
        logger.info("Connected to server ✅")

    @sio.event(namespace=SOCKET_IO_NAMESPACE)
    def connect_error(data):
        logger.error(f"Connection failed ❌: {data}")

    @sio.event(namespace=SOCKET_IO_NAMESPACE)
    def disconnect():
        logger.info("Disconnected from server!")

    @sio.on('purchase-created', namespace=SOCKET_IO_NAMESPACE)
    def purchase_created(data):
        logger.info("New purchase created!")
        printer_manager.queue.add_to_queue(data)

    # Connect to Socket.IO server
    try:
        logger.info(f"Connecting to server at {SOCKET_IO_SERVER_URL}...")
        sio.connect(SOCKET_IO_SERVER_URL, namespaces=[
                    SOCKET_IO_NAMESPACE], retry=True)
        sio.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sio.disconnect()
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == '__main__':
    main()

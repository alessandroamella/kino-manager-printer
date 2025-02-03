#!/usr/bin/env python3

import argparse
import socketio
import json
import time
import redis
from escpos.printer import Usb
from datetime import datetime
import threading
import logging
from typing import Dict, Any
from print_receipt import print_receipt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PrinterQueue:
    def __init__(self, redis_host='localhost', redis_port=6379):
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, decode_responses=True)
        self.queue_key = 'printer_queue'
        self.processing_key = 'processing_queue'
        self.max_retries = 5
        self.retry_delay = 30  # seconds

    def add_to_queue(self, receipt_data: Dict[str, Any]) -> str:
        """Add a receipt to the queue with metadata."""
        job_id = f"job_{int(time.time())}_{receipt_data['id']}"
        job_data = {
            'receipt_data': receipt_data,
            'attempts': 0,
            'created_at': datetime.now().isoformat(),
            'status': 'pending'
        }
        self.redis_client.hset(self.queue_key, job_id, json.dumps(job_data))
        logger.info(f"Added job {job_id} to queue")
        return job_id

    def get_next_job(self) -> tuple[str, dict] | None:
        """Get the next job from the queue."""
        for job_id in self.redis_client.hkeys(self.queue_key):
            job_data = json.loads(
                self.redis_client.hget(self.queue_key, job_id))
            if (job_data['status'] == 'pending' and
                    job_data['attempts'] < self.max_retries):
                return job_id, job_data
        return None

    def mark_job_complete(self, job_id: str):
        """Mark a job as completed and remove it from the queue."""
        self.redis_client.hdel(self.queue_key, job_id)
        logger.info(f"Job {job_id} completed successfully")

    def mark_job_failed(self, job_id: str, job_data: dict, error: str):
        """Mark a job as failed and update retry information."""
        job_data['attempts'] += 1
        job_data['last_error'] = str(error)
        job_data['last_attempt'] = datetime.now().isoformat()

        if job_data['attempts'] >= self.max_retries:
            job_data['status'] = 'failed'
            logger.error(
                f"Job {job_id} failed permanently after {self.max_retries} "
                f"attempts: {error}")
        else:
            logger.warning(
                f"Job {job_id} failed, attempt {job_data['attempts']}/"
                f"{self.max_retries}: {error}"
            )

        self.redis_client.hset(self.queue_key, job_id, json.dumps(job_data))


class PrinterManager:
    def __init__(self, vendor_id: int, product_id: int):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.printer = None
        self.queue = PrinterQueue()
        self.connect_printer()

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
        while True:
            try:
                job = self.queue.get_next_job()
                if job:
                    job_id, job_data = job
                    self.print_receipt(job_id, job_data)
                time.sleep(5)  # Wait before checking for new jobs
            except Exception as e:
                logger.error(f"Error in process_queue: {e}")
                time.sleep(5)

    def print_receipt(self, job_id: str, job_data: dict):
        """Attempt to print a receipt."""
        try:
            if not self.printer:
                if not self.connect_printer():
                    raise Exception("Printer not available")

            receipt_data = job_data['receipt_data']
            print_receipt(receipt_data, self.printer)
            self.queue.mark_job_complete(job_id)

        except Exception as e:
            self.printer = None  # Reset printer connection
            self.queue.mark_job_failed(job_id, job_data, str(e))
            time.sleep(self.queue.retry_delay)  # Wait before retrying


def main():
    parser = argparse.ArgumentParser(
        description='Run the script in dev or prod mode.')
    parser.add_argument('--mode', '-m', choices=['dev', 'prod'], default='dev',
                        help='Specify the mode: dev or prod. Defaults to dev.')
    args = parser.parse_args()

    if args.mode == 'dev':
        SOCKET_IO_SERVER_URL = 'ws://localhost:5001'
    else:
        SOCKET_IO_SERVER_URL = 'ws://cafe.kinocampus.it/purchase'
    SOCKET_IO_NAMESPACE = '/purchase'

    # Initialize printer manager
    printer_manager = PrinterManager(
        vendor_id=int("0x1fc9", 16),
        product_id=int("0x2016", 16)
    )

    # Start queue processor in a separate thread
    queue_thread = threading.Thread(
        target=printer_manager.process_queue, daemon=True)
    queue_thread.start()

    # Socket.IO setup
    sio = socketio.Client()

    @sio.event(namespace=SOCKET_IO_NAMESPACE)
    def connect():
        logger.info("Connected to server!")

    @sio.event(namespace=SOCKET_IO_NAMESPACE)
    def connect_error(data):
        logger.error(f"Connection failed: {data}")

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

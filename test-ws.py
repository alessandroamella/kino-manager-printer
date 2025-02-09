#!/usr/bin/env python3

import socketio
import argparse
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Test WebSocket connection.')
    parser.add_argument('--url', '-u', type=str,
                        default="wss://ws-cafe.bitrey.it",
                        help='WebSocket server URL')
    parser.add_argument('--namespace', '-n', type=str,
                        default='/purchase', help='Socket.IO namespace (default: /)')
    args = parser.parse_args()

    sio = socketio.Client()

    @sio.event(namespace=args.namespace)
    def connect():
        logger.info("Connected to server!")

    @sio.on('purchase-created', namespace=args.namespace)
    def purchase_created(data):
        logger.info("New purchase created!")
        logger.info(data)

    @sio.event(namespace=args.namespace)
    def connect_error(data):
        logger.error(f"Connection failed: {data}")

    @sio.event(namespace=args.namespace)
    def disconnect():
        logger.info("Disconnected from server!")

    try:
        logger.info(f"Connecting to {args.url}...")
        sio.connect(args.url, namespaces=[args.namespace], retry=True)
        sio.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sio.disconnect()
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == '__main__':
    main()

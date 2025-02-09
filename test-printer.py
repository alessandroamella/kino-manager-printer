#!/usr/bin/env python3

from escpos.printer import Usb

VENDOR_ID = int("0x1fc9", 16)
PRODUCT_ID = int("0x2016", 16)

try:
    p = Usb(VENDOR_ID, PRODUCT_ID)

    p.set(align='center')
    p.text("Test print\n")

    p.set(align='left')
    for i in range(5):
        p.text(f" - Item {i}\n")

    p.set(align='center')
    p.text("Total: $5.00\n")

    p.cut()

    print("Printing completed")

    print("Minimal test print command sent.")
except Exception as e:
    print(f"Error during minimal print: {e}")

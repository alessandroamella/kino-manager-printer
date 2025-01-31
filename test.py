from escpos.printer import Usb
from time import sleep

VENDOR_ID = int("0x1fc9", 16)
PRODUCT_ID = int("0x2016", 16)

try:
    p = Usb(VENDOR_ID, PRODUCT_ID)

    # To reset most settings back to default:
    p.hw('RESET')
    sleep(0.5)
    p.hw('INIT')
    sleep(0.5)
    p.set(normal_textsize=True)
    print("Printer initialized (settings reset to default).")

    # ... Continue printing, settings should be back to default ...

    p.text("This text should be in default style.\nSciao belo kebab scinque euro\n")
    p.cut()

    print("Minimal test print command sent.")
except Exception as e:
    print(f"Error during minimal print: {e}")

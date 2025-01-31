import socketio
import sys
from escpos.printer import Usb

# SocketIO Client Configuration
SOCKET_IO_SERVER_URL = 'ws://localhost:5001'
SOCKET_IO_NAMESPACE = '/purchase'
sio = socketio.Client()

# Printer Configuration
VENDOR_ID = int("0x1fc9", 16)
PRODUCT_ID = int("0x2016", 16)

p = None  # Initialize p to None outside the try block
try:
    p = Usb(VENDOR_ID, PRODUCT_ID)
    p.hw('INIT')
    print("Printer connected successfully!")
except Exception as e:
    print(f"Error connecting to printer: {e}")
    sys.exit(1)


def format_pos_text(left: str = "", right: str = "", alignment: str = "left"):
    max_width = 48

    if alignment == "left":
        return left.ljust(max_width)[:max_width]

    elif alignment == "right":
        return right.rjust(max_width)[:max_width]

    elif alignment == "both":
        space_available = max_width - len(left) - len(right)
        if space_available < 1:
            return (left + " " + right)[:max_width]
        return left + (" " * space_available) + right

    else:
        raise ValueError(
            "Invalid alignment. Choose 'left', 'right', or 'both'.")


def format_price_it(price):
    try:
        # Handle comma as decimal in input strings
        price_float = float(str(price).replace(",", "."))
        formatted_price = "{:.2f}".format(price_float).replace(".", ",")
        return f"{formatted_price} EUR"
    except ValueError:
        return str(price)  # Return original value if not convertible to float


# Example:
data = {
    "id": "62",
    "purchaseDate": "2025-01-31T14:32:11.426Z",
    "purchasedItems": [
        {
            "quantity": "2",
            "item": {
                "id": "7",
                "name": "Estathé Pesca Bottiglia",
                "nameShort": None,
                "description": None,
                "price": "1,5"
            }
        },
        {
            "quantity": 1,
            "item": {
                "id": "20",
                "name": "Acqua",
                "nameShort": None,
                "description": None,
                "price": "0,5"
            }
        }
    ],
    "discount": "0.00",
    "paymentMethod": "CARTE DI CREDITO",
    "total": "3.5",
    "givenAmount": "5,00",
    "change": "1,50"
}


def print_ricevuta(data):
    if p is None:
        print("Printer not initialized, skipping receipt printing.")
        return

    try:
        p.set(align='center', normal_textsize=True)
        p.image('logo.png')
        p.text("\nVia Piave, 3\n")
        p.text("41018 - San Cesario sul Panaro (MO)\n")
        p.text("kinocafesancesario@gmail.com\n")
        p.text(f"{'-' * 32}\n")

        p.set(align='left')
        p.text(format_pos_text("DESCRIZIONE", "EURO", "both"))

        p.set(double_height=False, double_width=False)

        for purchased_item in data["purchasedItems"]:
            item = purchased_item["item"]
            left_str = item["name"]
            formatted_price = format_price_it(item["price"])
            right_str = f"{purchased_item['quantity']}x {formatted_price}"
            p.text(format_pos_text(left_str, right_str, "both"))

        p.set(align='center')
        p.text(f"{'-' * 32}\n")

        p.set(align='left')
        formatted_total = format_price_it(data['total'])
        p.text(format_pos_text("TOTALE COMPLESSIVO", formatted_total, "both"))

        formatted_givenAmount = format_price_it(data['givenAmount'])
        p.text(format_pos_text(
            data['paymentMethod'], formatted_givenAmount, "both"))

        if data.get('change'):
            formatted_change = format_price_it(data['change'])
            p.text(format_pos_text("Resto", formatted_change, "both"))

        p.set(align='center')
        p.text(f"\n\n{data['purchaseDate']}\n")
        p.text(f"\nID Acquisto: #{str(data['id']).zfill(4)}\n")

        p.text("*NON FISCALE*\n")

        p.set(align='center')
        p.text("\nGrazie e arrivederci!\n")

        # remove comment to print receipt
        p.cut()

    except Exception as e:
        print(f"Error printing receipt: {e}")


def handle_new_purchase(data):
    print("New purchase created!")
    print("Purchase Data:", data)
    print_ricevuta(data)


@ sio.event(namespace=SOCKET_IO_NAMESPACE)
def connect():
    print("Connected to server!")


@ sio.event(namespace=SOCKET_IO_NAMESPACE)
def connect_error(data):
    print(f"Connection failed: {data}")


@ sio.event(namespace=SOCKET_IO_NAMESPACE)
def disconnect():
    print("Disconnected from server!")


@ sio.on('purchase-created', namespace=SOCKET_IO_NAMESPACE)
def purchase_created(data):
    handle_new_purchase(data)


if __name__ == '__main__':
    try:
        sio.connect(SOCKET_IO_SERVER_URL, namespaces=[
                    SOCKET_IO_NAMESPACE], retry=True)
        sio.wait()  # Keep the script running and listening for events
    except socketio.exceptions.ConnectionError as e:
        print(f"Failed to connect to server: {e}")
    except KeyboardInterrupt:
        print("Disconnecting...")
        if p:
            p.close()  # Close printer connection on exit
        sio.disconnect()

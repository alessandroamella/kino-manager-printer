import logging
from escpos.printer import Usb

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        logger.error(f"Error converting price to float: {price}")
        return str(price)  # Return original value if not convertible to float


def print_receipt(data, printer: Usb):
    if printer is None:  # Check if printer is valid before using
        logger.error("Printer not initialized, skipping receipt printing.")
        return

    try:
        printer.set(align='center', normal_textsize=True)
        printer.image('logo.png')
        printer.text("\nVia Piave, 3\n")
        printer.text("41018 - San Cesario sul Panaro (MO)\n")
        printer.text("kinocafesancesario@gmail.com\n")
        printer.text(f"{'-' * 32}\n")

        printer.set(align='left')
        printer.text(format_pos_text("DESCRIZIONE", "EURO", "both"))

        printer.set(double_height=False, double_width=False)

        for purchased_item in data["purchasedItems"]:
            item = purchased_item["item"]
            left_str = item["name"]
            formatted_price = format_price_it(item["price"])
            right_str = f"{purchased_item['quantity']}x {formatted_price}"
            printer.text(format_pos_text(left_str, right_str, "both"))

        printer.set(align='center')
        printer.text(f"{'-' * 32}\n")

        printer.set(align='left')
        formatted_total = format_price_it(data['total'])
        printer.text(format_pos_text(
            "TOTALE COMPLESSIVO", formatted_total, "both"))

        formatted_givenAmount = format_price_it(data['givenAmount'])
        printer.text(format_pos_text(
            data['paymentMethod'], formatted_givenAmount, "both"))

        if data.get('change'):
            formatted_change = format_price_it(data['change'])
            printer.text(format_pos_text("Resto", formatted_change, "both"))

        printer.set(align='center')
        printer.text(f"\n\n{data['purchaseDate']}\n")
        printer.text(f"\nID Acquisto: #{str(data['id']).zfill(4)}\n")

        printer.text("*NON FISCALE*\n")

        printer.set(align='center')
        printer.text("\nGrazie e arrivederci!\n")

        # remove comment to print receipt
        printer.cut()

    except Exception as e:
        logger.error(f"Error printing receipt: {e}")

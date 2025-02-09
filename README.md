# Kino Manager Printer

## Product ID e Vendor ID

- Su Linux, per trovare il Product ID e Vendor ID della stampante, esegui `lsusb` e cerca il dispositivo.
- La stampante termica in questione ha un Product ID di `0x1fc9` e un Vendor ID di `0x2016`. Se non è la stessa stampante, puoi passare `--vendor-id` e `--product-id` per specificare i valori corretti.
- Puoi stampare i driver per Debian-based Linux [qui](https://www.xprintertech.com/download) (se non funziona, per ora li hosto [qui](https://static.bitrey.it/drivers/printer-driver-xprinter_3.13.3_all.deb)).

### Note

Per risolvere il problema di permessi, crea un file `/etc/udev/rules.d/99-usb-printer.rules` (o qualunque altro nome) con contenuto:

```bash
SUBSYSTEMS=="usb", ATTRS{idVendor}=="<vendor-id>", ATTRS{idProduct}=="<product-id>", MODE="0666", OWNER="<username>", GROUP="lp"
```

Sostituendo `<vendor-id>`, `<product-id>` e `<username>` con i valori corretti.

## Installazione

Installa le dependencies con:

```bash
pip install -r requirements.txt
```

## Come funziona

- `app.py` è il file principale del programma.
- Implementa una coda di stampa (per gestire errori e ritentare la stampa).
- Comunica con il server [socket.io](https://socket.io/) nel backend per ricevere i dati da stampare.
- Prevede di collegarsi con una stampante ESC/POS via USB.

## Utilizzo

```bash
python app.py
```

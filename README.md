# Kino Manager Printer

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

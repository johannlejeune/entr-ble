# ENTR BLE CLI

Run `entr-ble` in an interactive terminal to scan for nearby locks and open the terminal interface. Use `entr-ble tui ADDRESS` to connect directly.

In the terminal interface, press Enter after typing an address to connect, F2 to show or hide other Bluetooth devices, and Ctrl+C to quit. Use the arrow keys and Enter to choose a lock or command; Escape closes a form.

Run `entr-ble --help` for one-shot commands. Each one-shot command opens its own connection, while the terminal interface keeps one connection open until you disconnect or exit.

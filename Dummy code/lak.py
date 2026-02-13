import serial
import time

# -----------------------------
# USER SETTINGS
# -----------------------------
CLI_PORT = 'COM6'      # Change to your radar CLI port
DATA_PORT = 'COM7'     # Change to your radar DATA port
CLI_BAUD  = 115200
DATA_BAUD = 921600
CONFIG_FILE = 'config.cfg'   # Your radar config file

# -----------------------------
# SEND CONFIG FILE TO RADAR
# -----------------------------
def send_config():
    cli_serial = serial.Serial(CLI_PORT, CLI_BAUD, timeout=1)
    time.sleep(0.2)

    with open(CONFIG_FILE, 'r') as f:
        lines = f.readlines()

    for line in lines:
        if len(line.strip()) > 0:
            cli_serial.write((line + '\n').encode())
            print("Sent:", line.strip())
            time.sleep(0.05)  # Allow radar to process command

    cli_serial.close()
    print("\n✔ Config sent successfully!\n")


# -----------------------------
# READ BINARY RADAR DATA
# -----------------------------
def read_radar_data():
    data_serial = serial.Serial(DATA_PORT, DATA_BAUD, timeout=0.005)
    print("📡 Reading radar binary data... Press CTRL+C to stop.\n")

    try:
        while True:
            data = data_serial.read(4096)  # Read 4 KB
            if len(data) > 0:
                print("Received:", len(data), "bytes")
                # TODO: You can parse TLVs here
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        data_serial.close()


# -----------------------------
# MAIN FUNCTION
# -----------------------------
if __name__ == "_main_":
    send_config()
    read_radar_data()
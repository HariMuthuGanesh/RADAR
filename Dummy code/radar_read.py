import serial
import time

CONFIG_PORT = "COM6"       
DATA_PORT = "COM7"       
CFG_FILE = "config.cfg"

def send_config():
    cfg = serial.Serial(CONFIG_PORT, 115200, timeout=1)
    print("Sending config...")

    with open(CFG_FILE, "r") as f:
        for line in f:
            if line.strip() != "":
                cfg.write((line.strip() + "\n").encode())
                time.sleep(0.05)
    
    print("Config sent")
    cfg.close()

def read_data():
    data = serial.Serial(DATA_PORT, 921600, timeout=1)
    print("Reading radar UART frames...")

    while True:
        frame = data.read(1024)
        if(frame):
            print(list(frame))
            print("Frame received\n\n\n\n")

send_config()
read_data()

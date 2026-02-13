import serial
import time

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

cli = serial.Serial("COM6", 115200, timeout=1)
ser = serial.Serial("COM7", 921600, timeout=1)

buffer = bytearray()

def send_config(file_path):
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                cli.write((line + '\n').encode())
                time.sleep(0.01)
            else:
                print("\nEmpty line skipped\n")
                continue

    print("Config sent successfully")

def output_magic_words():
    while True:
        data = ser.read(1024)
        if not data:
            break

        buffer.extend(data)

        idx = buffer.find(MAGIC_WORD)

        if idx != -1:
            frame = buffer[idx:]
            print(frame.hex())
            buffer.clear()

    print("Data not Found")

if __name__ == "__main__":
    send_config("config.cfg")
    time.sleep(1)
    output_magic_words()

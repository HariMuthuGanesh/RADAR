import serial
import struct
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import csv

CFG_PORT  = "COM6"
DATA_PORT = "COM7"

CFG_BAUD  = 115200
DATA_BAUD = 921600

CONFIG_FILE = "awr1843_3d.cfg"
CSV_FILE = "awr1843_3d.csv"

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'

# ========================
# Send Config
# ========================

def send_config():
    cfg = serial.Serial(CFG_PORT, CFG_BAUD)
    time.sleep(1)

    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            cfg.write((line.strip() + '\n').encode())
            time.sleep(0.05)

    cfg.close()
    print("Config sent")

# ========================
# Open Data Port
# ========================

data_port = serial.Serial(DATA_PORT, DATA_BAUD, timeout=0.1)
byte_buffer = bytearray()

# ========================
# CSV
# ========================

csv_file = open(CSV_FILE, 'w', newline='')
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["X", "Y", "Z"])

# ========================
# Matplotlib
# ========================

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

ax.set_xlim(-5, 5)
ax.set_ylim(0, 10)
ax.set_zlim(-3, 3)

scatter = ax.scatter([], [], [], s=20)

# ========================
# Frame Parser
# ========================

def parse_frame():
    global byte_buffer

    byte_buffer.extend(data_port.read(4096))

    if len(byte_buffer) < 40:
        return None

    start_idx = byte_buffer.find(MAGIC_WORD)

    if start_idx == -1:
        return None

    if len(byte_buffer) < start_idx + 40:
        return None

    total_packet_len = struct.unpack('I', byte_buffer[start_idx+12:start_idx+16])[0]

    if len(byte_buffer) < start_idx + total_packet_len:
        return None

    frame = byte_buffer[start_idx:start_idx+total_packet_len]
    byte_buffer = byte_buffer[start_idx+total_packet_len:]

    num_tlvs = struct.unpack('I', frame[32:36])[0]

    offset = 40
    points = []

    for _ in range(num_tlvs):
        tlv_type, tlv_length = struct.unpack('II', frame[offset:offset+8])
        offset += 8

        if tlv_type == 1:
            num_obj = int((tlv_length - 8) / 16)

            for i in range(num_obj):
                x, y, z, v = struct.unpack('ffff', frame[offset:offset+16])
                points.append([x, y, z])
                offset += 16
        else:
            offset += tlv_length - 8

    return np.array(points)

# ========================
# Update Plot
# ========================

def update(frame):
    points = parse_frame()

    if points is not None and len(points) > 0:
        ax.cla()

        ax.set_xlim(-5, 5)
        ax.set_ylim(0, 10)
        ax.set_zlim(-3, 3)

        ax.set_xlabel("X")
        ax.set_ylabel("Y")
        ax.set_zlabel("Z")

        ax.scatter(points[:,0], points[:,1], points[:,2], s=20)

        for p in points:
            csv_writer.writerow(p)

    return scatter,

# ========================
# Main
# ========================

if __name__ == "__main__":
    send_config()

    ani = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    plt.show()

    csv_file.close()
    data_port.close()

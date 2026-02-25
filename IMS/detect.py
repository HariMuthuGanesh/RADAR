import tkinter as tk
from tkinter import filedialog
import serial
import serial.tools.list_ports
import threading
import struct
import math
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as pltha


BAUD_CONFIG = 115200
BAUD_DATA = 921600

MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
TRACK_TLV = 1010

VELOCITY_THRESHOLD = 0.15


class PeopleMotionDetector:

    def __init__(self, root):
        self.root = root
        self.root.title("Industrial Radar - Motion Classification")

        self.data_buffer = bytearray()
        self.tracks = {}
        self.running = False

        self.config_port = None
        self.data_port = None

        self.create_ui()
        self.auto_detect_ports()

    # ---------------- UI ----------------

    def create_ui(self):

        left = tk.Frame(self.root)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        right = tk.Frame(self.root)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Button(left, text="Select Config File", command=self.load_config).pack(fill="x")
        tk.Button(left, text="Start Detection", command=self.start_reading).pack(fill="x", pady=10)

        self.status_label = tk.Label(left, text="Waiting...", fg="blue")
        self.status_label.pack(pady=10)

        self.summary_label = tk.Label(left, text="Moving: 0 | Sitting: 0")
        self.summary_label.pack()

        # 2D Plot
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ---------------- COM ----------------

    def auto_detect_ports(self):
        ports = list(serial.tools.list_ports.comports())
        if len(ports) >= 2:
            self.config_port = ports[0].device
            self.data_port = ports[1].device
            self.status_label.config(
                text=f"Detected {self.config_port} & {self.data_port}",
                fg="green"
            )
        else:
            self.status_label.config(text="Not enough COM ports detected", fg="red")

    # ---------------- Config ----------------

    def load_config(self):
        file_path = filedialog.askopenfilename(filetypes=[("CFG Files", "*.cfg")])
        if not file_path:
            return

        try:
            ser = serial.Serial(self.config_port, BAUD_CONFIG, timeout=1)
            with open(file_path, 'r') as f:
                for line in f:
                    ser.write((line.strip() + '\n').encode())
            ser.close()
            self.status_label.config(text="Config Sent", fg="green")
        except Exception as e:
            self.status_label.config(text="Config Error", fg="red")
            print(e)

    # ---------------- Threading ----------------

    def start_reading(self):
        self.running = True
        thread = threading.Thread(target=self.read_serial, daemon=True)
        thread.start()
        self.status_label.config(text="Detecting...", fg="green")

    def read_serial(self):
        try:
            ser = serial.Serial(self.data_port, BAUD_DATA, timeout=0.1)
            while self.running:
                data = ser.read(4096)
                if data:
                    self.data_buffer.extend(data)
                    self.parse_stream()
        except Exception as e:
            print("Serial Error:", e)

    # ---------------- Parsing ----------------

    def parse_stream(self):

        while True:

            idx = self.data_buffer.find(MAGIC_WORD)
            if idx == -1:
                return

            if len(self.data_buffer) < idx + 40:
                return

            header = self.data_buffer[idx:idx + 40]
            unpacked = struct.unpack('<8I', header[8:40])

            total_len = unpacked[1]
            num_tlvs = unpacked[6]

            if len(self.data_buffer) < idx + total_len:
                return

            packet = self.data_buffer[idx:idx + total_len]
            self.parse_frame(packet, num_tlvs)

            del self.data_buffer[:idx + total_len]

    def parse_frame(self, packet, num_tlvs):

        offset = 40
        self.tracks.clear()

        for _ in range(num_tlvs):

            tlv_type, tlv_len = struct.unpack('<2I', packet[offset:offset + 8])
            offset += 8

            payload = packet[offset:offset + tlv_len - 8]

            if tlv_type == TRACK_TLV:
                self.parse_targets(payload)

            offset += tlv_len - 8

        self.root.after(0, self.update_plot)

    def parse_targets(self, payload):

        size = 108
        count = len(payload) // size

        for i in range(count):

            chunk = payload[i * size:(i + 1) * size]
            data = struct.unpack('<I26f', chunk)

            tid = data[0]
            posX = data[1]
            posY = data[2]
            velX = data[3]
            velY = data[4]

            velocity = math.sqrt(velX**2 + velY**2)

            state = "Moving" if velocity > VELOCITY_THRESHOLD else "Sitting"

            self.tracks[tid] = (posX, posY, state)

    # ---------------- 2D Plot ----------------

    def update_plot(self):

        self.ax.clear()

        moving_count = 0
        sitting_count = 0

        for tid, (x, y, state) in self.tracks.items():

            if state == "Moving":
                self.ax.scatter(x, y, c='red', s=100)
                moving_count += 1
            else:
                self.ax.scatter(x, y, c='blue', s=100)
                sitting_count += 1

            self.ax.text(x, y, f"ID {tid}", fontsize=8)

        self.ax.set_xlabel("X (m)")
        self.ax.set_ylabel("Y (m)")
        self.ax.set_xlim(-5, 5)
        self.ax.set_ylim(0, 10)

        self.summary_label.config(
            text=f"Moving: {moving_count} | Sitting: {sitting_count}"
        )

        self.canvas.draw()


if __name__ == "__main__":
    root = tk.Tk()
    app = PeopleMotionDetector(root)
    root.mainloop()



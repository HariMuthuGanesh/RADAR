import serial
import struct
import time
import csv
import os
import numpy as np
import plotly.graph_objects as go
from collections import deque

MAGIC_WORD = [2, 1, 4, 3, 6, 5, 8, 7]

CFG_PORT  = "COM6"     # CHANGE if needed
DATA_PORT = "COM7"     # CHANGE if needed


class RadarParser:
    def __init__(self):
        self.cfg = serial.Serial(CFG_PORT, 115200, timeout=0.5)
        self.data = serial.Serial(DATA_PORT, 921600, timeout=0.5)
        self.buffer = bytearray()

    def send_config(self, cfg_path):
        with open(cfg_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.cfg.write((line + "\n").encode())
                    time.sleep(0.01)

    def read_frame(self):
        if self.data.in_waiting:
            self.buffer += self.data.read(self.data.in_waiting)

        buf_len = len(self.buffer)

        for i in range(buf_len - 8):
            if list(self.buffer[i:i + 8]) != MAGIC_WORD:
                continue

            if i + 36 > buf_len:
                return None

            packet_len = struct.unpack("<I", self.buffer[i + 12:i + 16])[0]

            if i + packet_len > buf_len:
                return None

            frame_num = struct.unpack("<I", self.buffer[i + 20:i + 24])[0]
            num_tlvs  = struct.unpack("<I", self.buffer[i + 32:i + 36])[0]
            header_len = 40

            points = []
            idx = i + header_len

            for _ in range(num_tlvs):
                if idx + 8 > buf_len:
                    return None

                tlv_type, tlv_len = struct.unpack(
                    "<II", self.buffer[idx:idx + 8]
                )

                if idx + 8 + tlv_len > buf_len:
                    return None

                if tlv_type == 1:
                    data_start = idx + 8
                    data_len = tlv_len - 8
                    for j in range(data_len // 16):
                        off = data_start + j * 16
                        x, y, z, v = struct.unpack(
                            "<ffff", self.buffer[off:off + 16]
                        )
                        points.append((x, y, z, v))

                idx += 8 + tlv_len

            self.buffer = self.buffer[i + packet_len:]
            return frame_num, points

        return None


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, "radar_profile.cfg")

    radar = RadarParser()
    radar.send_config(cfg_path)

    # csv_path = os.path.join(script_dir, "radar_live.csv")
    # csv_file = open(csv_path, "w", newline="")
    # writer = csv.writer(csv_file)
    # writer.writerow(["frame", "x", "y", "z", "velocity"])

    # xb, yb, zb, vb = (
    #     deque(maxlen=400),
    #     deque(maxlen=400),
    #     deque(maxlen=400),
    #     deque(maxlen=400),
    # )

    fig = go.Figure(
        data=[go.Scatter3d(
            x=[], y=[], z=[],
            mode="markers",
            marker=dict(size=4, color=[], colorscale="Jet")
        )]
    )

    fig.update_layout(
        title="Live 2D Radar Plot",
        scene=dict(
            xaxis=dict(range=[-6, 6]),
            yaxis=dict(range=[0, 10]),
            zaxis=dict(range=[-3, 3])
        )
    )

    fig.show()

    start = time.time()
    duration = 60

    while time.time() - start < duration:
        frame = radar.read_frame()
        if frame is None:
            continue

        fid, pts = frame

        for x, y, z, v in pts:
            xb.append(x)
            yb.append(y)
            zb.append(z)
            vb.append(v)
            writer.writerow([fid, x, y, z, v])

        csv_file.flush()

        fig.data[0].x = list(xb)
        fig.data[0].y = list(yb)
        fig.data[0].z = list(zb)
        fig.data[0].marker.color = list(vb)

    csv_file.close()
    radar.cfg.close()
    radar.data.close()


if __name__ == "__main__":
        main()

import streamlit as st
import serial
import struct
import time
import os
import plotly.graph_objects as go

MAGIC_WORD = bytes([2, 1, 4, 3, 6, 5, 8, 7])

CFG_PORT  = "COM6"
DATA_PORT = "COM7"


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
        i = 0

        while i <= buf_len - 8:
            if self.buffer[i:i+8] != MAGIC_WORD:
                i += 1
                continue

            if i + 40 > buf_len:
                return None

            packet_len = struct.unpack("<I", self.buffer[i+12:i+16])[0]

            if i + packet_len > buf_len:
                return None

            frame_num = struct.unpack("<I", self.buffer[i+20:i+24])[0]
            num_tlvs  = struct.unpack("<I", self.buffer[i+32:i+36])[0]

            idx = i + 40
            points = []

            for _ in range(num_tlvs):
                if idx + 8 > i + packet_len:
                    break

                tlv_type, tlv_len = struct.unpack("<II", self.buffer[idx:idx+8])

                if tlv_len < 8:
                    break

                if tlv_type == 1:
                    data_start = idx + 8
                    num_points = (tlv_len - 8) // 16

                    for j in range(num_points):
                        off = data_start + j * 16
                        x, y, z, v = struct.unpack("<ffff", self.buffer[off:off+16])
                        points.append((x, y, z, v))

                idx += tlv_len

            self.buffer = self.buffer[i + packet_len:]
            return frame_num, points

        return None

    def close(self):
        self.cfg.close()
        self.data.close()


def main():
    st.set_page_config(layout="wide")
    st.title("📡 Live 3D Radar Visualization")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, "radar_profile.cfg")

    radar = RadarParser()
    radar.send_config(cfg_path)

    plot_placeholder = st.empty()

    # Create figure ONCE
    fig = go.Figure(
        data=[go.Scatter3d(
            x=[],
            y=[],
            z=[],
            mode="markers",
            marker=dict(
                size=4,
                color=[],
                colorscale="Jet",
                colorbar=dict(title="Velocity")
            )
        )]
    )

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[-6, 6]),
            yaxis=dict(range=[0, 10]),
            zaxis=dict(range=[-3, 3])
        ),
        margin=dict(l=0, r=0, b=0, t=40)
    )

    start = time.time()
    duration = 60  # seconds

    while time.time() - start < duration:
        frame = radar.read_frame()
        if frame is None:
            continue

        fid, pts = frame
        if not pts:
            continue

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        zs = [p[2] for p in pts]
        vs = [p[3] for p in pts]

        # Update existing figure
        fig.data[0].x = xs
        fig.data[0].y = ys
        fig.data[0].z = zs
        fig.data[0].marker.color = vs

        plot_placeholder.plotly_chart(
            fig,
            use_container_width=True,
            key="radar_plot"
        )

    radar.close()


if __name__ == "__main__":
    main()

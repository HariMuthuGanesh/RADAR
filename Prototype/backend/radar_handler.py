import serial
import struct
import asyncio
import time
from typing import List, Tuple, Optional

MAGIC_WORD = bytes([2, 1, 4, 3, 6, 5, 8, 7])

class RadarHandler:
    def __init__(self, cfg_port: str = "COM6", data_port: str = "COM7"):
        self.cfg_port = cfg_port
        self.data_port = data_port
        self.cfg_serial = None
        self.data_serial = None
        self.buffer = bytearray()
        self.is_running = False

    def connect(self):
        try:
            self.cfg_serial = serial.Serial(self.cfg_port, 115200, timeout=0.5)
            self.data_serial = serial.Serial(self.data_port, 921600, timeout=0.5)
            return True
        except Exception as e:
            print(f"Error connecting to radar: {e}")
            return False

    def send_config(self, cfg_path: str):
        if not self.cfg_serial:
            return False
        try:
            with open(cfg_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('%'):
                        self.cfg_serial.write((line + "\n").encode())
                        time.sleep(0.01)
            return True
        except Exception as e:
            print(f"Error sending config: {e}")
            return False

    def parse_frame(self) -> Optional[Tuple[int, List[dict]]]:
        if not self.data_serial or self.data_serial.in_waiting == 0:
            return None

        self.buffer += self.data_serial.read(self.data_serial.in_waiting)
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

                if tlv_type == 1:
                    data_start = idx + 8
                    num_points = (tlv_len - 8) // 16

                    for j in range(num_points):
                        off = data_start + j * 16
                        x, y, z, v = struct.unpack("<ffff", self.buffer[off:off+16])
                        points.append({
                            "x": float(x),
                            "y": float(y),
                            "z": float(z),
                            "v": float(v)
                        })

                idx += tlv_len

            self.buffer = self.buffer[i + packet_len:]
            return frame_num, points

        return None

    async def start_streaming(self, callback):
        self.is_running = True
        while self.is_running:
            frame = self.parse_frame()
            if frame:
                frame_num, points = frame
                await callback({"frame": frame_num, "points": points, "timestamp": time.time()})
            await asyncio.sleep(0.01)

    def stop(self):
        self.is_running = False
        if self.cfg_serial: self.cfg_serial.close()
        if self.data_serial: self.data_serial.close()

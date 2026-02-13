import os
import csv
import serial
import struct
import numpy as np
import time
import matplotlib.pyplot as plt

MAGIC_WORD = [0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07]


class RadarFrameParser:
    def __init__(self, config_port='COM6', data_port='COM7'):
        self.config_port = config_port
        self.data_port = data_port
        self.config_serial = None
        self.data_serial = None
        self.byte_buffer = np.zeros(2**15, dtype=np.uint8)
        self.byte_buffer_length = 0

    def connect(self):
        try:
            self.config_serial = serial.Serial(self.config_port, 115200, timeout=0.5)
            self.data_serial = serial.Serial(self.data_port, 921600, timeout=0.5)
            print("Connected to config port:", self.config_port)
            print("Connected to data port  :", self.data_port)
            return True
        except Exception as e:
            print("Connection failed:", e)
            return False

    def send_config(self, cfg_file):
        try:
            with open(cfg_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('%'):
                        self.config_serial.write((line + '\n').encode())
                        time.sleep(0.01)
                        response = self.config_serial.readline().decode(errors='ignore')
                        print("CFG >", line)
                        print("RSP <", response.strip())
            return True
        except Exception as e:
            print("Config error:", e)
            return False

    def check_magic_word(self, data, idx):
        for i in range(8):
            if data[idx + i] != MAGIC_WORD[i]:
                return False
        return True

    def parse_frame_header(self, data):
        try:
            packet_length = struct.unpack('<I', data[12:16])[0]
            frame_num = struct.unpack('<I', data[20:24])[0]
            num_tlvs = struct.unpack('<I', data[32:36])[0]
            header_len = 36
            version = struct.unpack('<I', data[8:12])[0]
            if version > 0x01000005:
                header_len = 40
            return packet_length, frame_num, num_tlvs, header_len
        except:
            return None

    def parse_tlv(self, data, idx):
        tlv_type = struct.unpack('<I', data[idx:idx+4])[0]
        tlv_length = struct.unpack('<I', data[idx+4:idx+8])[0]
        return tlv_type, tlv_length

    def parse_detected_points(self, data, tlv_length):
        points = []
        num_points = (tlv_length - 8) // 16
        for i in range(num_points):
            off = i * 16
            try:
                x, y, z, v = struct.unpack('<ffff', data[off:off+16])
                points.append({
                    'x': x,
                    'y': y,
                    'z': z,
                    'velocity': v,
                    'range': np.sqrt(x*x + y*y + z*z)
                })
            except:
                pass
        return points

    def read_and_parse_frame(self):
        try:
            count = self.data_serial.in_waiting
            if count > 0:
                raw = self.data_serial.read(count)
                for b in raw:
                    self.byte_buffer[self.byte_buffer_length] = b
                    self.byte_buffer_length += 1
                    if self.byte_buffer_length >= len(self.byte_buffer):
                        self.byte_buffer_length = 0

            magic_idx = None
            for i in range(self.byte_buffer_length - 8):
                if self.check_magic_word(self.byte_buffer, i):
                    magic_idx = i
                    break

            if magic_idx is None:
                return None

            header = self.parse_frame_header(self.byte_buffer[magic_idx:])
            if header is None:
                return None

            packet_length, frame_num, num_tlvs, header_len = header

            if self.byte_buffer_length < magic_idx + packet_length:
                return None

            frame = {
                'frame_num': frame_num,
                'timestamp': time.time(),
                'detected_points': []
            }

            idx = magic_idx + header_len

            for _ in range(num_tlvs):
                tlv_type, tlv_length = self.parse_tlv(self.byte_buffer, idx)
                if tlv_type == 1:
                    start = idx + 8
                    end = start + tlv_length - 8
                    pts = self.parse_detected_points(self.byte_buffer[start:end], tlv_length)
                    frame['detected_points'].extend(pts)
                idx += 8 + tlv_length

            remain = self.byte_buffer_length - (magic_idx + packet_length)
            if remain > 0:
                self.byte_buffer[:remain] = self.byte_buffer[
                    magic_idx + packet_length:self.byte_buffer_length
                ]
                self.byte_buffer_length = remain
            else:
                self.byte_buffer_length = 0

            return frame
        except:
            self.byte_buffer_length = 0
            return None

    def close(self):
        if self.config_serial:
            self.config_serial.close()
        if self.data_serial:
            self.data_serial.close()


class LiveRadarPlot:
    def __init__(self):
        plt.ion()
        self.fig, self.ax = plt.subplots(figsize=(7, 7))
        self.sc = self.ax.scatter([], [], s=20)

        self.ax.set_xlim(-6, 6)
        self.ax.set_ylim(0, 10)
        self.ax.set_xlabel("X (meters)")
        self.ax.set_ylabel("Y (meters)")
        self.ax.set_title("Live Radar Detected Points")
        self.ax.grid(True)

    def update(self, points):
        if not points:
            return
        xs = [p['x'] for p in points]
        ys = [p['y'] for p in points]
        self.sc.set_offsets(list(zip(xs, ys)))
        plt.pause(0.001)

def main():
    parser = RadarFrameParser(
        config_port='COM6',
        data_port='COM7'
    )

    if not parser.connect():
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(script_dir, 'radar_profile.cfg')

    if not parser.send_config(cfg_path):
        parser.close()
        return

    plotter = LiveRadarPlot()

    duration = 45
    output_csv = 'radar_points.csv'
    start = time.time()

    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'frame',
            'timestamp',
            'idx',
            'x',
            'y',
            'z',
            'velocity',
            'range'
        ])

        while time.time() - start < duration:
            frame = parser.read_and_parse_frame()
            if frame is None:
                time.sleep(0.005)
                continue

            plotter.update(frame['detected_points'])

            for i, p in enumerate(frame['detected_points']):
                writer.writerow([
                    frame['frame_num'],
                    frame['timestamp'],
                    i,
                    p['x'],
                    p['y'],
                    p['z'],
                    p['velocity'],
                    p['range']
                ])

            print(
                "Frame",
                frame['frame_num'],
                "Points",
                len(frame['detected_points'])
            )

    parser.close()
    print("Capture finished")


if __name__ == '__main__':
    main()

import csv
import serial
import struct
import numpy as np
import time

# Magic word that indicates start of a frame
MAGIC_WORD = [0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07]


class RadarFrameParser:
    def init(self, config_port='COM6', data_port='COM7'):
        """Initialize radar serial ports"""
        self.config_port = config_port
        self.data_port = data_port
        self.config_serial = None
        self.data_serial = None
        self.byte_buffer = np.zeros(2**15, dtype='uint8')
        self.byte_buffer_length = 0

    def connect(self):
        """Establish serial connections"""
        try:
            self.config_serial = serial.Serial(self.config_port, 115200, timeout=0.5)
            self.data_serial = serial.Serial(self.data_port, 921600, timeout=0.5)
            print(f"✓ Connected to Config port: {self.config_port}")
            print(f"✓ Connected to Data port: {self.data_port}")
            return True

        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def send_config(self, config_file):
        """Send configuration commands (.cfg file)"""
        if not self.config_serial:
            print("✗ Config port not connected")
            return False

        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()

                    if line and not line.startswith('%'):
                        self.config_serial.write((line + '\n').encode())
                        time.sleep(0.01)
                        response = self.config_serial.readline().decode('utf-8', errors='ignore')
                        print(f"Sent: {line}")
                        print(f"Response: {response.strip()}")

            print("✓ Configuration sent successfully\n")
            return True

        except Exception as e:
            print(f"✗ Config error: {e}")
            return False

    def check_magic_word(self, data, offset=0):
        return list(data[offset:offset + 8]) == MAGIC_WORD

    def parse_frame_header(self, data):
        """Parse mmWave header"""
        try:
            version = struct.unpack('<I', data[8:12])[0]
            packet_length = struct.unpack('<I', data[12:16])[0]
            frame_num = struct.unpack('<I', data[20:24])[0]
            time_cpu_cycles = struct.unpack('<I', data[24:28])[0]
            num_detected_obj = struct.unpack('<I', data[28:32])[0]
            num_tlvs = struct.unpack('<I', data[32:36])[0]

            header_len = 40 if version > 0x01000005 else 36

            return {
                'frame_num': frame_num,
                'packet_length': packet_length,
                'num_detected_obj': num_detected_obj,
                'num_tlvs': num_tlvs,
                'header_length': header_len,
                'time_cpu_cycles': time_cpu_cycles
            }

        except Exception as e:
            print(f"✗ Header parse error: {e}")
            return None

    def parse_tlv(self, data, tlv_start):
        try:
            tlv_type = struct.unpack('<I', data[tlv_start: tlv_start + 4])[0]
            tlv_length = struct.unpack('<I', data[tlv_start + 4: tlv_start + 8])[0]
            return tlv_type, tlv_length
        except:
            return None, None

    def parse_detected_points(self, data, tlv_length):
        points = []
        num_points = tlv_length // 16

        for i in range(num_points):
            offset = i * 16
            try:
                x = struct.unpack('<f', data[offset: offset + 4])[0]
                y = struct.unpack('<f', data[offset + 4: offset + 8])[0]
                z = struct.unpack('<f', data[offset + 8: offset + 12])[0]
                velocity = struct.unpack('<f', data[offset + 12: offset + 16])[0]

                points.append({
                    'x': x, 'y': y, 'z': z,
                    'velocity': velocity,
                    'range': np.sqrt(x*x + y*y + z*z)
                })
            except:
                continue

        return points

    def read_and_parse_frame(self):
        if not self.data_serial:
            print("✗ Data port not connected")
            return None

        try:
            available_bytes = self.data_serial.in_waiting

            if available_bytes > 0:
                read_data = self.data_serial.read(available_bytes)

                for b in read_data:
                    self.byte_buffer[self.byte_buffer_length] = b
                    self.byte_buffer_length += 1

                    if self.byte_buffer_length >= len(self.byte_buffer):
                        self.byte_buffer_length = 0

            # Find magic word
            magic_idx = None
            for i in range(self.byte_buffer_length - 8):
                if self.check_magic_word(self.byte_buffer, i):
                    magic_idx = i
                    break

            if magic_idx is None:
                return None

            header = self.parse_frame_header(self.byte_buffer[magic_idx:])
            if header is None:
                self.byte_buffer_length = 0
                return None

            # Check complete packet
            if self.byte_buffer_length < magic_idx + header['packet_length']:
                return None

            frame_data = {
                'frame_num': header['frame_num'],
                'timestamp': time.time(),
                'detected_points': []
            }

            tlv_start = magic_idx + header['header_length']

            for _ in range(header['num_tlvs']):
                tlv_type, tlv_length = self.parse_tlv(self.byte_buffer, tlv_start)

                if tlv_type == 1:
                    tlv_data = self.byte_buffer[tlv_start + 8: tlv_start + 8 + tlv_length]
                    frame_data['detected_points'].extend(
                        self.parse_detected_points(tlv_data, tlv_length)
                    )

                tlv_start += 8 + tlv_length

            # Remove processed frame from buffer
            new_length = self.byte_buffer_length - (magic_idx + header['packet_length'])
            if new_length > 0:
                self.byte_buffer[:new_length] = self.byte_buffer[
                    magic_idx + header['packet_length']: self.byte_buffer_length
                ]
                self.byte_buffer_length = new_length
            else:
                self.byte_buffer_length = 0

            return frame_data

        except Exception as e:
            print(f"✗ Frame parse error: {e}")
            self.byte_buffer_length = 0
            return None

    def close(self):
        if self.config_serial:
            self.config_serial.close()
        if self.data_serial:
            self.data_serial.close()
        print("✓ Connections closed")


def main():

    parser = RadarFrameParser(config_port='COM6', data_port='COM7')

    if not parser.connect():
        return

    # ENTER YOUR CONFIG FILE HERE (FULL PATH)
    config_file = r"D:\TI\CODE\mmwave.cfg"

    if not parser.send_config(config_file):
        parser.close()
        return

    capture_duration = 45
    output_csv = "radar_points.csv"

    print("\n📡 Starting mmWave Data Capture...")
    print(f"⏱ Duration: {capture_duration} seconds")
    print(f"💾 Saving CSV: {output_csv}")

    start_time = time.time()
    frame_count = 0
    point_count = 0

    try:
        with open(output_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(
                ['frame_num', 'timestamp', 'point_index',
                 'x_m', 'y_m', 'z_m', 'velocity_mps', 'range_m'])

            while time.time() - start_time < capture_duration:
                frame = parser.read_and_parse_frame()

                if frame is None:
                    time.sleep(0.005)
                    continue

                frame_count += 1
                print(f"Frame #{frame['frame_num']} → {len(frame['detected_points'])} points")

                for i, p in enumerate(frame['detected_points']):
                    writer.writerow([
                        frame['frame_num'],
                        frame['timestamp'],
                        i,
                        p['x'], p['y'], p['z'],
                        p['velocity'], p['range']
                    ])
                    point_count += 1

        print("\n✅ DONE!")
        print(f"   Frames captured: {frame_count}")
        print(f"   Points saved   : {point_count}")
        print(f"   File saved     : {output_csv}")

    except KeyboardInterrupt:
        print("\n⛔ Stopped by user.")

    finally:
        parser.close()

main()

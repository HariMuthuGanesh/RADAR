#!/usr/bin/env python3
import csv
import serial
import struct
import numpy as np
import time

# Magic word that indicates start of a frame
MAGIC_WORD = [0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07]

class RadarFrameParser:
    def __init__(self, config_port='COM11', data_port='COM12'):
        """
        Initialize radar serial connections
        
        Args:
            config_port: Serial port for configuration commands (115200 baud)
            data_port: Serial port for data output (921600 baud)
        """
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
            print(f"Connected to Config port: {self.config_port}")
            print(f"Connected to Data port: {self.data_port}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def send_config(self, config_file):
        """
        Send configuration commands to radar
        
        Args:
            config_file: Path to .cfg file
        """
        if not self.config_serial:
            print("✗ Config port not connected")
            return False
            
        try:
            with open(config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if line and not line.startswith('%'):
                        self.config_serial.write((line + '\n').encode())
                        time.sleep(0.01)
                        response = self.config_serial.readline().decode('utf-8', errors='ignore')
                        print(f"Sent: {line}")
                        print(f"Response: {response.strip()}")
            print("✓ Configuration sent successfully")
            return True
        except Exception as e:
            print(f"✗ Config error: {e}")
            return False
    
    def check_magic_word(self, data, offset=0):
        """Check if magic word is present at given offset"""
        for i in range(8):
            if data[offset + i] != MAGIC_WORD[i]:
                return False
        return True
    
    def parse_frame_header(self, data):
        """
        Parse frame header structure
        Returns: (frame_num, num_detected_obj, num_tlvs, packet_length)
        """
        try:
            # Header structure (36 or 40 bytes depending on version)
            magic = struct.unpack('<Q', data[0:8])[0]
            version = struct.unpack('<I', data[8:12])[0]
            packet_length = struct.unpack('<I', data[12:16])[0]
            platform = struct.unpack('<I', data[16:20])[0]
            frame_num = struct.unpack('<I', data[20:24])[0]
            time_cpu_cycles = struct.unpack('<I', data[24:28])[0]
            num_detected_obj = struct.unpack('<I', data[28:32])[0]
            num_tlvs = struct.unpack('<I', data[32:36])[0]
            
            # Check for subframe (SDK 3.x and later)
            header_length = 36
            subframe_num = 0
            if version > 0x01000005:
                subframe_num = struct.unpack('<I', data[36:40])[0]
                header_length = 40
            
            return {
                'frame_num': frame_num,
                'num_detected_obj': num_detected_obj,
                'num_tlvs': num_tlvs,
                'packet_length': packet_length,
                'subframe_num': subframe_num,
                'header_length': header_length,
                'time_cpu_cycles': time_cpu_cycles
            }
        except Exception as e:
            print(f"✗ Header parse error: {e}")
            return None
    
    def parse_tlv(self, data, tlv_start):
        """
        Parse TLV (Type-Length-Value) structure
        Common TLV types:
        - 1: Detected Points (x, y, z, velocity)
        - 2: Range Profile
        - 6: Statistics
        """
        try:
            tlv_type = struct.unpack('<I', data[tlv_start:tlv_start+4])[0]
            tlv_length = struct.unpack('<I', data[tlv_start+4:tlv_start+8])[0]
            
            return tlv_type, tlv_length
        except:
            return None, None
    
    def parse_detected_points(self, data, tlv_length):
        """
        Parse detected points TLV (Type 1)
        Each point: x, y, z (meters), velocity (m/s)
        """
        points = []
        num_points = tlv_length // 16  # Each point is 16 bytes (4 floats)
        
        for i in range(num_points):
            offset = i * 16
            try:
                x = struct.unpack('<f', data[offset:offset+4])[0]
                y = struct.unpack('<f', data[offset+4:offset+8])[0]
                z = struct.unpack('<f', data[offset+8:offset+12])[0]
                velocity = struct.unpack('<f', data[offset+12:offset+16])[0]
                
                points.append({
                    'x': x,
                    'y': y, 
                    'z': z,
                    'velocity': velocity,
                    'range': np.sqrt(x**2 + y**2 + z**2)
                })
            except:
                continue
                
        return points
    
    def read_and_parse_frame(self):
        """
        Read one complete frame from data port
        Returns: Dictionary with frame data or None
        """
        if not self.data_serial:
            print("✗ Data port not connected")
            return None
        
        # Read available data
        try:
            available_bytes = self.data_serial.in_waiting
            if available_bytes > 0:
                read_data = self.data_serial.read(available_bytes)
                
                # Append to buffer
                for byte in read_data:
                    self.byte_buffer[self.byte_buffer_length] = byte
                    self.byte_buffer_length += 1
                    
                    # Prevent buffer overflow
                    if self.byte_buffer_length >= len(self.byte_buffer):
                        self.byte_buffer_length = 0
            
            # Search for magic word
            magic_idx = None
            for i in range(self.byte_buffer_length - 8):
                if self.check_magic_word(self.byte_buffer, i):
                    magic_idx = i
                    break
            
            if magic_idx is None:
                return None
            
            # Parse header
            header = self.parse_frame_header(self.byte_buffer[magic_idx:])
            if header is None:
                self.byte_buffer_length = 0
                return None
            
            # Check if we have complete packet
            if self.byte_buffer_length < magic_idx + header['packet_length']:
                return None  # Wait for more data
            
            # Parse TLVs
            frame_data = {
                'frame_num': header['frame_num'],
                'num_detected_obj': header['num_detected_obj'],
                'timestamp': time.time(),
                'detected_points': []
            }
            
            tlv_start = magic_idx + header['header_length']
            
            for i in range(header['num_tlvs']):
                tlv_type, tlv_length = self.parse_tlv(self.byte_buffer, tlv_start)
                
                if tlv_type == 1:  # Detected Points
                    tlv_data = self.byte_buffer[tlv_start+8:tlv_start+8+tlv_length]
                    points = self.parse_detected_points(tlv_data, tlv_length)
                    frame_data['detected_points'].extend(points)
                
                # Move to next TLV
                tlv_start += 8 + tlv_length
            
            # Remove processed data from buffer
            remaining_length = self.byte_buffer_length - (magic_idx + header['packet_length'])
            if remaining_length > 0:
                self.byte_buffer[:remaining_length] = self.byte_buffer[
                    magic_idx + header['packet_length']:self.byte_buffer_length
                ]
                self.byte_buffer_length = remaining_length
            else:
                self.byte_buffer_length = 0
            
            return frame_data
            
        except Exception as e:
            print(f"✗ Frame parse error: {e}")
            self.byte_buffer_length = 0
            return None
    
    def close(self):
        """Close serial connections"""
        if self.config_serial:
            self.config_serial.close()
        if self.data_serial:
            self.data_serial.close()
        print("✓ Connections closed")


def main():
    # Initialize parser
    parser = RadarFrameParser(
        config_port='COM11',  # Change to your ports
        data_port='COM12'
    )
    
    # Connect to radar
    if not parser.connect():
        return
    
    # Send configuration
    config_file = 'xwr18xx_profile_2025_12_11T09_34_22_755.cfg'  # Path to your .cfg file
    if not parser.send_config(config_file):
        parser.close()
        return
    
    # How long to capture (in seconds)
    capture_duration = 45  # e.g., 10 seconds
    
    # Output CSV file name
    output_csv = 'radar_points.csv'
    
    print("\n📡 Starting frame capture...")
    print(f"⏱️ Capturing for {capture_duration} seconds")
    print(f"💾 Saving to: {output_csv}\n")
    
    frame_count = 0
    point_count = 0
    start_time = time.time()
    
    try:
        # Open CSV file
        with open(output_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'frame_num', 'timestamp', 'point_index',
                'x_m', 'y_m', 'z_m', 'velocity_mps', 'range_m'
            ])
            
            # Capture loop
            while time.time() - start_time < capture_duration:
                frame = parser.read_and_parse_frame()
                
                if frame is None:
                    time.sleep(0.005)
                    continue
                
                frame_count += 1
                timestamp = frame['timestamp']
                
                # Write each detected point
                for idx, point in enumerate(frame['detected_points']):
                    writer.writerow([
                        frame['frame_num'],
                        timestamp,
                        idx,
                        point['x'],
                        point['y'],
                        point['z'],
                        point['velocity'],
                        point['range']
                    ])
                    point_count += 1
                
                print(f"Frame #{frame['frame_num']}: {len(frame['detected_points'])} points")
        
        print(f"\n✅ Capture finished.")
        print(f"   Frames captured: {frame_count}")
        print(f"   Points saved   : {point_count}")
        print(f"   CSV file       : {output_csv}")
    
    except KeyboardInterrupt:
        print("\n⛔ Stopped by user.")
    
    finally:
        parser.close()

if __name__ == '__main__':
    main()

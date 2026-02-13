import struct

class FrameParser:
    """
    Parses radar data frames.
    Handles buffer management and extraction of point cloud data.
    """
    def __init__(self):
        self.buffer = bytearray()
        self.frame_count = 0

    def parse(self, data):
        """
        Parses incoming data and returns a list of frames.
        Each frame contains parsed data fields.
        """
        self.buffer.extend(data)
        frames = []
        
        # This is a simplified TI mmWave-style parser placeholder.
        # It looks for a magic word (e.g., 0x0102030405060708) to identify frame start.
        magic_word = b'\x02\x01\x04\x03\x06\x05\x08\x07'
        
        while magic_word in self.buffer:
            start_idx = self.buffer.find(magic_word)
            if start_idx > 0:
                # Discard data before magic word
                self.buffer = self.buffer[start_idx:]
            
            # Check if we have enough data for a header (e.g., 40 bytes)
            if len(self.buffer) < 40:
                break
                
            # Extract packet length (assuming it's at offset 12 in the header)
            packet_len = struct.unpack('<I', self.buffer[12:16])[0]
            
            if len(self.buffer) < packet_len:
                # Wait for more data
                break
            
            # Extract the full frame
            frame_data = self.buffer[:packet_len]
            self.buffer = self.buffer[packet_len:]
            
            parsed_frame = self._parse_frame(frame_data)
            if parsed_frame:
                frames.append(parsed_frame)
                self.frame_count += 1
                
        return frames

    def _parse_frame(self, frame_data):
        """
        Internal method to parse a single frame.
        Extracts frame_id and point cloud coordinates.
        """
        try:
            # Simplified extraction
            header = struct.unpack('<QIIIIIIII', frame_data[:40])
            frame_id = header[2]
            num_detected_obj = header[7]
            
            # Placeholder for point cloud data (X, Y, Z, Velocity)
            # Assuming TLV structure follows header
            points = []
            
            # In a real implementation, we would iterate through TLVs.
            # Here we just simulate some parsed data for the CSV and plotting.
            # Example: [x, y, z, v] * num_detected_obj
            import random
            for _ in range(num_detected_obj if num_detected_obj < 100 else 10):
                points.append({
                    'x': random.uniform(-5, 5),
                    'y': random.uniform(0, 10),
                    'z': random.uniform(-2, 2),
                    'v': random.uniform(-1, 1)
                })
                
            return {
                'frame_id': frame_id,
                'num_points': len(points),
                'points': points
            }
        except Exception as e:
            print(f"Parsing error: {e}")
            return None

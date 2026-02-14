import struct
import time
from datetime import datetime

class FrameParser:
    """
    Parses raw radar data into structured frames.
    Currently implements a mock parser for demonstration.
    """
    
    def __init__(self):
        self.leftover_data = b''

    def parse(self, raw_data):
        """
        Parses incoming raw bytes and returns a list of data points.
        In a real application, this would handle packet headers, TLVs, etc.
        For this task, we'll simulate parsing meaningful fields.
        """
        # Simulated parsing: extracting fake (x, y, z, velocity, intensity)
        # Assuming each 'point' is 20 bytes for this mock.
        all_points = []
        
        # In a real scenario, you'd find magic headers here.
        # Here we just treat segments of data as points for demo.
        data_to_parse = self.leftover_data + raw_data
        point_size = 20
        
        num_points = len(data_to_parse) // point_size
        self.leftover_data = data_to_parse[num_points * point_size:]
        
        timestamp = datetime.now().isoformat(timespec='milliseconds')
        
        for i in range(num_points):
            segment = data_to_parse[i*point_size : (i+1)*point_size]
            # Mock parsing logic
            try:
                # Just unpack some floats as a placeholder
                # x, y, z, v, i
                vals = struct.unpack('fffff', segment)
                all_points.append({
                    'timestamp': timestamp,
                    'x': vals[0],
                    'y': vals[1],
                    'z': vals[2],
                    'velocity': vals[3],
                    'intensity': vals[4]
                })
            except Exception:
                continue
                
        return all_points

    def get_mock_frame(self, frame_id):
        """Generates a mock frame for testing/UI development."""
        import random
        num_points = random.randint(10, 50)
        timestamp = datetime.now().isoformat(timespec='milliseconds')
        points = []
        for _ in range(num_points):
            points.append({
                'timestamp': timestamp,
                'frame_id': frame_id,
                'x': random.uniform(-5, 5),
                'y': random.uniform(0, 10),
                'z': random.uniform(-2, 2),
                'velocity': random.uniform(-2, 2),
                'intensity': random.uniform(0, 100)
            })
        return points

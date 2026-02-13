import csv
import os
from datetime import datetime

class CSVLogger:
    """
    Handles logging of parsed radar data to CSV.
    Files are stored in the 'output_excel' directory.
    """
    def __init__(self, output_dir='output_excel'):
        self.output_dir = output_dir
        self._ensure_output_dir()
        
        # Generate filename with timestamp
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(self.output_dir, f"radar_output_{timestamp_str}.csv")
        
        self.file = None
        self.writer = None
        self.header_written = False

    def _ensure_output_dir(self):
        """Creates the output directory if it doesn't exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"Created directory: {self.output_dir}")

    def start(self):
        """Opens the CSV file for writing."""
        try:
            self.file = open(self.filename, mode='a', newline='')
            # Define fieldnames based on requirement: timestamp, frame_id, parsed data fields
            # We'll use a generic 'data' field or expand as needed.
            fieldnames = ['timestamp', 'frame_id', 'num_points', 'point_data']
            self.writer = csv.DictWriter(self.file, fieldnames=fieldnames)
            
            if not self.header_written:
                self.writer.writeheader()
                self.header_written = True
            
            print(f"Logging initialized. File: {os.path.abspath(self.filename)}")
        except Exception as e:
            print(f"Failed to start logger: {e}")

    def log_frame(self, parsed_frame):
        """Appends a frame's data to the CSV."""
        if not self.writer:
            return

        try:
            timestamp = datetime.now().isoformat(timespec='milliseconds')
            row = {
                'timestamp': timestamp,
                'frame_id': parsed_frame.get('frame_id'),
                'num_points': parsed_frame.get('num_points'),
                'point_data': str(parsed_frame.get('points')) # Store as string for Excel compatibility
            }
            self.writer.writerow(row)
            self.file.flush() # Ensure data is written
        except Exception as e:
            print(f"Logging error: {e}")

    def close(self):
        """Safely closes the CSV file."""
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None
            print("CSV logger closed safely.")

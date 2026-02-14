import csv
import os
from datetime import datetime

class CSVLogger:
    """
    Handles saving session data to CSV files.
    """
    def __init__(self, directory="saved_files"):
        self.directory = directory
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

    def save_session(self, session_data):
        """
        Saves a list of dictionaries to a CSV file.
        Returns the absolute path of the saved file.
        """
        if not session_data:
            return None

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"radar_capture_{timestamp_str}.csv"
        filepath = os.path.join(self.directory, filename)

        # Extract headers from the first data point
        headers = session_data[0].keys()

        try:
            with open(filepath, mode='w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(session_data)
            return os.path.abspath(filepath)
        except Exception as e:
            print(f"Error saving CSV: {e}")
            return None

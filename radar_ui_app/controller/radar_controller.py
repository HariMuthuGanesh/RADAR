from PySide6.QtCore import QObject, Signal, Slot
from communication.serial_manager import SerialManager
from parser.frame_parser import FrameParser
from logger.csv_logger import CSVLogger

class RadarController(QObject):
    """
    Main controller for the radar application.
    Coordinates between UI, serial communication, parsing, and logging.
    """
    data_updated = Signal(list)  # Emits parsed points for plotting
    status_message = Signal(str)
    connection_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.serial_manager = SerialManager()
        self.parser = FrameParser()
        self.logger = CSVLogger()
        
        self.session_data = []
        self.is_streaming = False
        self.frame_count = 0

        # Connect serial manager signals
        self.serial_manager.log_message.connect(self.status_message)
        self.serial_manager.data_ready.connect(self.process_incoming_data)
        self.serial_manager.connection_status.connect(self.connection_changed)

    def connect_radar(self):
        """Attempts to connect to the radar configuration port."""
        return self.serial_manager.connect_ports()

    def disconnect_radar(self):
        """Disconnects radar and stops any active streaming."""
        self.stop_streaming()
        self.serial_manager.disconnect_ports()

    def send_config(self, cfg_path):
        """Sends a configuration file to the radar."""
        if self.serial_manager.send_config(cfg_path):
            self.status_message.emit(f"Config {cfg_path} sent successfully.")
            return True
        return False

    def start_streaming(self):
        """Starts data acquisition and initiates parsing."""
        if not self.is_streaming:
            self.session_data = [] # Reset data for new session
            self.frame_count = 0
            self.is_streaming = True
            self.serial_manager.start_reading()
            self.status_message.emit("Streaming started.")

    def stop_streaming(self):
        """Stops data acquisition."""
        if self.is_streaming:
            self.is_streaming = False
            self.serial_manager.stop_reading()
            self.status_message.emit("Streaming stopped.")

    @Slot(bytes)
    def process_incoming_data(self, raw_data):
        """Slot to handle raw data from serial manager."""
        if not self.is_streaming:
            return

        parsed_points = self.parser.parse(raw_data)
        if parsed_points:
            self.frame_count += 1
            for pt in parsed_points:
                pt['frame_id'] = self.frame_count
                self.session_data.append(pt)
            
            # Emit data for plotting (last frame segments)
            self.data_updated.emit(parsed_points)

    def download_data(self):
        """Saves session data to CSV via the logger."""
        if not self.session_data:
            self.status_message.emit("No data to download.")
            return None
        
        filepath = self.logger.save_session(self.session_data)
        if filepath:
            self.status_message.emit(f"Data saved to {filepath}")
        else:
            self.status_message.emit("Failed to save data.")
        return filepath
        
    def get_mock_data(self):
        """Triggers mock data for UI testing when hardware is not present."""
        if self.is_streaming:
            self.frame_count += 1
            pts = self.parser.get_mock_frame(self.frame_count)
            self.session_data.extend(pts)
            self.data_updated.emit(pts)

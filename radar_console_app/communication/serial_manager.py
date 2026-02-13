import serial
import time
import threading

class SerialManager:
    """
    Handles serial communication for the radar.
    - Config Port: COM6 (115200 baud)
    - Data Port: COM7 (921600 baud)
    """
    def __init__(self, config_port='COM6', data_port='COM7', config_baud=115200, data_baud=921600):
        self.config_port = config_port
        self.data_port = data_port
        self.config_baud = config_baud
        self.data_baud = data_baud
        
        self.config_serial = None
        self.data_serial = None
        self.is_running = False

    def connect(self):
        """Connects to both config and data ports."""
        try:
            self.config_serial = serial.Serial(self.config_port, self.config_baud, timeout=1)
            self.data_serial = serial.Serial(self.data_port, self.data_baud, timeout=1)
            print(f"Connected to {self.config_port} and {self.data_port}")
            return True
        except serial.SerialException as e:
            print(f"Serial Error: {e}")
            return False

    def send_config(self, config_file_path):
        """Sends each line of the config file to the radar."""
        if not self.config_serial:
            print("Config serial not connected.")
            return

        try:
            with open(config_file_path, 'r') as f:
                lines = f.readlines()
                
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.config_serial.write((line + '\n').encode())
                    time.sleep(0.01)  # Brief pause between commands
            print(f"Configuration sent from {config_file_path}")
        except Exception as e:
            print(f"Error sending config: {e}")

    def read_data(self):
        """Reads raw data from the data port."""
        if self.data_serial and self.data_serial.in_waiting > 0:
            return self.data_serial.read(self.data_serial.in_waiting)
        return None

    def close(self):
        """Closes all serial connections."""
        if self.config_serial:
            self.config_serial.close()
        if self.data_serial:
            self.data_serial.close()
        print("Serial connections closed.")

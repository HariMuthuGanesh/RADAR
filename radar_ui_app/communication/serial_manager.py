import serial
import time
from PySide6.QtCore import QObject, QThread, Signal, Slot

class SerialReader(QObject):
    """
    Worker class to read serial data from the data port in a separate thread.
    """
    data_received = Signal(bytes)
    error_occurred = Signal(str)
    finished = Signal()

    def __init__(self, port, baudrate):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.is_running = False
        self.serial_port = None

    @Slot()
    def run(self):
        try:
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=1)
            self.is_running = True
            while self.is_running:
                if self.serial_port.in_waiting > 0:
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    self.data_received.emit(data)
                else:
                    time.sleep(0.01)  # Avoid high CPU usage
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            self.finished.emit()

    def stop(self):
        self.is_running = False

class SerialManager(QObject):
    """
    Manages serial communication for both configuration and data ports.
    """
    log_message = Signal(str)
    data_ready = Signal(bytes)
    connection_status = Signal(bool)

    def __init__(self, config_port="COM6", data_port="COM7", config_baud=115200, data_baud=921600):
        super().__init__()
        self.config_port = config_port
        self.data_port = data_port
        self.config_baud = config_baud
        self.data_baud = data_baud
        
        self.config_ser = None
        self.reader_thread = None
        self.reader_worker = None

    def connect_ports(self):
        """Opens the configuration serial port."""
        try:
            self.config_ser = serial.Serial(self.config_port, self.config_baud, timeout=1)
            self.log_message.emit(f"Connected to config port {self.config_port}")
            self.connection_status.emit(True)
            return True
        except Exception as e:
            self.log_message.emit(f"Failed to connect to config port: {str(e)}")
            self.connection_status.emit(False)
            return False

    def disconnect_ports(self):
        """Closes all serial ports and stops data reading."""
        self.stop_reading()
        if self.config_ser and self.config_ser.is_open:
            self.config_ser.close()
            self.log_message.emit("Disconnected config port.")
        self.connection_status.emit(False)

    def send_config(self, filepath):
        """Sends configuration commands from a .cfg file."""
        if not self.config_ser or not self.config_ser.is_open:
            self.log_message.emit("Error: Config port not open.")
            return False

        try:
            with open(filepath, 'r') as f:
                commands = f.readlines()
            
            for cmd in commands:
                cmd = cmd.strip()
                if cmd and not cmd.startswith('%'):
                    self.config_ser.write((cmd + '\n').encode())
                    self.log_message.emit(f"Sent: {cmd}")
                    time.sleep(0.1)  # Delay between commands
            return True
        except Exception as e:
            self.log_message.emit(f"Error sending config: {str(e)}")
            return False

    def start_reading(self):
        """Starts the data reading thread."""
        if self.reader_thread and self.reader_thread.isRunning():
            return

        self.reader_thread = QThread()
        self.reader_worker = SerialReader(self.data_port, self.data_baud)
        self.reader_worker.moveToThread(self.reader_thread)

        self.reader_thread.started.connect(self.reader_worker.run)
        self.reader_worker.data_received.connect(self.data_ready)
        self.reader_worker.error_occurred.connect(lambda e: self.log_message.emit(f"Data Serial Error: {e}"))
        self.reader_worker.finished.connect(self.reader_thread.quit)
        self.reader_worker.finished.connect(self.reader_worker.deleteLater)
        self.reader_thread.finished.connect(self.reader_thread.deleteLater)

        self.reader_thread.start()
        self.log_message.emit(f"Started reading data from {self.data_port}")

    def stop_reading(self):
        """Stops the data reading thread."""
        if self.reader_worker:
            self.reader_worker.stop()
        if self.reader_thread:
            self.reader_thread.quit()
            self.reader_thread.wait()
            self.reader_thread = None
            self.reader_worker = None
        self.log_message.emit("Stopped reading data.")

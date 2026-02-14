import os
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt, QTimer
from ui.control_panel import ControlPanel
from ui.status_bar import StatusBar
from ui.log_widget import LogWidget
from plotting.plot_manager import PlotManager
from controller.radar_controller import RadarController

class MainWindow(QMainWindow):
    """
    Main application window for the Radar UI.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Radar Visualization Application")
        self.resize(1200, 800)

        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left: Control Panel
        self.control_panel = ControlPanel()
        main_layout.addWidget(self.control_panel, 1)

        # Right: Plotting Area and Logs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Splitter for Plot and Logs
        self.splitter = QSplitter(Qt.Vertical)
        
        self.plot_manager = PlotManager()
        self.log_widget = LogWidget()
        
        self.splitter.addWidget(self.plot_manager)
        self.splitter.addWidget(self.log_widget)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        
        right_layout.addWidget(self.splitter)
        main_layout.addWidget(right_panel, 4)

        # Status Bar
        self.status_bar = StatusBar()
        self.setStatusBar(self.status_bar)

    def connect_signals(self):
        # Signal connections from Control Panel to Controller
        self.control_panel.connect_btn.clicked.connect(self.handle_connection)
        self.control_panel.start_btn.clicked.connect(self.handle_start)
        self.control_panel.stop_btn.clicked.connect(self.handle_stop)
        self.control_panel.download_btn.clicked.connect(self.controller.download_data)

        # Signal connections from Controller to UI
        self.controller.status_message.connect(self.log_widget.log)
        self.controller.connection_changed.connect(self.status_bar.set_connection_status)
        self.controller.connection_changed.connect(self.control_panel.set_connected)
        self.controller.data_updated.connect(self.plot_manager.update_data)

    def handle_connection(self):
        if self.control_panel.connect_btn.text() == "Connect":
            if self.controller.connect_radar():
                # Automatically send config if connected
                cfg_file = self.control_panel.config_combo.currentText()
                cfg_path = os.path.join("config", cfg_file)
                self.controller.send_config(cfg_path)
        else:
            self.controller.disconnect_radar()

    def handle_start(self):
        mode = self.control_panel.mode_combo.currentText()
        self.plot_manager.set_mode(mode)
        self.plot_manager.clear_plots()
        self.controller.start_streaming()
        self.control_panel.set_streaming(True)

    def handle_stop(self):
        self.controller.stop_streaming()
        self.control_panel.set_streaming(False)

    def closeEvent(self, event):
        """Cleanup on window close."""
        self.controller.disconnect_radar()
        event.accept()

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel, QGroupBox

class ControlPanel(QWidget):
    """
    User interface for controlling radar connection, configuration, and streaming.
    """
    def __init__(self, config_dir="config"):
        super().__init__()
        self.config_dir = config_dir
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Config Selection Group
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout()
        
        self.config_combo = QComboBox()
        self.refresh_configs()
        config_layout.addWidget(QLabel("Select .cfg file:"))
        config_layout.addWidget(self.config_combo)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Plot Mode Selection Group
        mode_group = QGroupBox("Plotting Mode")
        mode_layout = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["2D", "3D"])
        mode_layout.addWidget(self.mode_combo)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Control Buttons Group
        btn_group = QGroupBox("Controls")
        btn_layout = QVBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.download_btn = QPushButton("Download")
        
        # Initial states
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.download_btn)
        
        btn_group.setLayout(btn_layout)
        layout.addWidget(btn_group)
        
        layout.addStretch()

    def refresh_configs(self):
        """Reloads .cfg files from the config directory."""
        self.config_combo.clear()
        if os.path.exists(self.config_dir):
            configs = [f for f in os.listdir(self.config_dir) if f.endswith('.cfg')]
            self.config_combo.addItems(configs)
        else:
            self.config_combo.addItem("No config dir found")

    def set_connected(self, connected):
        """Updates UI based on connection state."""
        self.connect_btn.setText("Disconnect") if connected else self.connect_btn.setText("Connect")
        self.start_btn.setEnabled(connected)
        self.config_combo.setEnabled(not connected)

    def set_streaming(self, streaming):
        """Updates UI based on streaming state."""
        self.start_btn.setEnabled(not streaming)
        self.stop_btn.setEnabled(streaming)
        self.connect_btn.setEnabled(not streaming)
        self.download_btn.setEnabled(not streaming)
        self.mode_combo.setEnabled(not streaming)

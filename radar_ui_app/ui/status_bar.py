from PySide6.QtWidgets import QStatusBar, QLabel

class StatusBar(QStatusBar):
    """
    Status bar to show connection state and streaming status.
    """
    def __init__(self):
        super().__init__()
        self.status_label = QLabel("Disconnected")
        self.addWidget(self.status_label)
        
        self.fps_label = QLabel("FPS: 0")
        self.addPermanentWidget(self.fps_label)

    def set_connection_status(self, connected):
        if connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green;")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: red;")

    def set_fps(self, fps):
        self.fps_label.setText(f"FPS: {fps}")

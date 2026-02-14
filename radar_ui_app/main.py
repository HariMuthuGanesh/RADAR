import sys
from PySide6.QtWidgets import QApplication
from controller.radar_controller import RadarController
from ui.main_window import MainWindow

def main():
    """
    Entry point for the Radar UI Application.
    """
    app = QApplication(sys.argv)
    
    # Apply a dark theme or styling if desired
    app.setStyle("Fusion")
    
    controller = RadarController()
    window = MainWindow(controller)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

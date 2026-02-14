from PySide6.QtWidgets import QStackedWidget
from plotting.plot2d import Plot2D
from plotting.plot3d import Plot3D

class PlotManager(QStackedWidget):
    """
    Manages switching between 2D and 3D radar plots.
    """
    def __init__(self):
        super().__init__()
        self.plot2d = Plot2D()
        self.plot3d = Plot3D()
        
        self.addWidget(self.plot2d) # Index 0
        self.addWidget(self.plot3d) # Index 1
        
        self.current_mode = "2D"

    def set_mode(self, mode):
        """Switches the visible plot."""
        if mode == "2D":
            self.setCurrentIndex(0)
            self.current_mode = "2D"
        elif mode == "3D":
            self.setCurrentIndex(1)
            self.current_mode = "3D"

    def update_data(self, points):
        """Passes data to the active plot."""
        if self.current_mode == "2D":
            self.plot2d.update_plot(points)
        else:
            self.plot3d.update_plot(points)

    def clear_plots(self):
        """Clears all plots."""
        self.plot2d.clear()
        self.plot3d.clear()

from .plot2d import Plot2D
from .plot3d import Plot3D

class PlotManager:
    """
    Manages plotting mode selection and delegation.
    """
    def __init__(self, mode='2D'):
        self.mode = mode.upper()
        self.plotter = None

    def start(self):
        """Initializes the selected plotter."""
        if self.mode == '2D':
            self.plotter = Plot2D()
        elif self.mode == '3D':
            self.plotter = Plot3D()
        else:
            print(f"Unknown plotting mode: {self.mode}. Defaulting to 2D.")
            self.plotter = Plot2D()

    def update(self, parsed_frame):
        """Passes data to the active plotter."""
        if self.plotter:
            self.plotter.update(parsed_frame)

    def close(self):
        """Closes the active plotter."""
        if self.plotter:
            self.plotter.close()
            print(f"{self.mode} Plotter closed.")

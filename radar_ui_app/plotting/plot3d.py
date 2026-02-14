import numpy as np
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QWidget, QVBoxLayout

class Plot3D(QWidget):
    """
    3D Point Cloud View for radar data.
    """
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.view_widget = gl.GLViewWidget()
        self.layout.addWidget(self.view_widget)

        # Environment grid
        grid = gl.GLGridItem()
        grid.scale(1, 1, 1)
        self.view_widget.addItem(grid)

        # Coordinate axes
        axis = gl.GLAxisItem()
        self.view_widget.addItem(axis)

        # Scatter plot item
        self.scatter = gl.GLScatterPlotItem(size=5, pxMode=True)
        self.view_widget.addItem(self.scatter)
        
        self.view_widget.setCameraPosition(distance=15, elevation=30, azimuth=45)

    def update_plot(self, points):
        """Updates the 3D items with new data points."""
        if not points:
            return

        pos = np.array([[p['x'], p['y'], p['z']] for p in points])
        # Color based on intensity (simulated)
        colors = np.array([[1, 1, 1, 0.8] for _ in points]) 
        
        self.scatter.setData(pos=pos, color=colors)

    def clear(self):
        self.scatter.setData(pos=np.empty((0, 3)))

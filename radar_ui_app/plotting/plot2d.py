import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout

class Plot2D(QWidget):
    """
    2D Scatter Plot for radar data.
    """
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.plot_widget = pg.PlotWidget(title="Radar 2D View (X-Y)")
        self.layout.addWidget(self.plot_widget)

        self.scatter = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        self.plot_widget.addItem(self.scatter)
        
        self.plot_widget.setLabel('left', 'Y (m)')
        self.plot_widget.setLabel('bottom', 'X (m)')
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setXRange(-5, 5)
        self.plot_widget.setYRange(0, 10)

    def update_plot(self, points):
        """Updates the scatter plot with new data points."""
        if not points:
            return
            
        x_data = [p['x'] for p in points]
        y_data = [p['y'] for p in points]
        
        self.scatter.setData(x=x_data, y=y_data)

    def clear(self):
        self.scatter.clear()

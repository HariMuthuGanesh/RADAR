import matplotlib.pyplot as plt

class Plot2D:
    """
    Handles 2D scatter plotting for radar data.
    """
    def __init__(self):
        self.fig, self.ax = plt.subplots()
        self.scatter = None
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(0, 20)
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_title('Radar 2D Detection')
        plt.ion() # Interactive mode on
        plt.show(block=False)

    def update(self, parsed_frame):
        """Updates the plot with new frame data."""
        points = parsed_frame.get('points', [])
        if not points:
            return

        x = [p['x'] for p in points]
        y = [p['y'] for p in points]

        if self.scatter is None:
            self.scatter = self.ax.scatter(x, y, c='r', marker='o')
        else:
            self.scatter.set_offsets(list(zip(x, y)))
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def close(self):
        plt.close(self.fig)

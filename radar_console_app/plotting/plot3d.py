import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class Plot3D:
    """
    Handles 3D scatter plotting for radar data.
    """
    def __init__(self):
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.scatter = None
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(0, 20)
        self.ax.set_zlim(-5, 5)
        self.ax.set_xlabel('X (m)')
        self.ax.set_ylabel('Y (m)')
        self.ax.set_zlabel('Z (m)')
        self.ax.set_title('Radar 3D Detection')
        plt.ion() # Interactive mode on
        plt.show(block=False)

    def update(self, parsed_frame):
        """Updates the plot with new frame data."""
        points = parsed_frame.get('points', [])
        if not points:
            return

        x = [p['x'] for p in points]
        y = [p['y'] for p in points]
        z = [p['z'] for p in points]

        if self.scatter is None:
            self.scatter = self.ax.scatter(x, y, z, c='b', marker='o')
        else:
            # Matplotlib 3D scatter update is slightly different
            self.scatter._offsets3d = (x, y, z)
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def close(self):
        plt.close(self.fig)

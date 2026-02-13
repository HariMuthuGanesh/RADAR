import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D      
import numpy as np

CSV_FILE = "visual.csv"    # Change if needed

def load_data(csv_path):
    """Load radar point cloud CSV"""
    try:
        df = pd.read_csv(csv_path)
        print(f"✓ Loaded {len(df)} points from {csv_path}")
        return df
    except Exception as e:
        print(f"✗ Error loading CSV: {e}")
        exit()

def plot_point_cloud(df, frame_num=None):
    """Plot the point cloud for a given frame or all frames"""
    if frame_num is not None:
        df = df[df['frame_num'] == frame_num]
        print(f"Plotting frame {frame_num} with {len(df)} points.")
    else:
        print(f"Plotting ALL frames ({len(df)} points).")

    if len(df) == 0:
        print("✗ No points to plot.")
        return

    x = df['x_m']
    y = df['y_m']
    z = df['z_m']
    velocity = df['velocity_mps']

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    # Scatter plot with color mapped to velocity
    scatter = ax.scatter(
        x, y, z,
        c=velocity,
        cmap='jet',      # Nice gradient color
        s=8,             # Point size
        alpha=0.8
    )

    # Axis labels
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title("mmWave Radar 3D Point Cloud")

    # Colorbar
    cbar = fig.colorbar(scatter, ax=ax)
    cbar.set_label("Velocity (m/s)")

    # Equal scaling for all axes
    max_range = np.array([x.max()-x.min(), y.max()-y.min(), z.max()-z.min()]).max() / 2.0

    mid_x = (x.max() + x.min()) * 0.5
    mid_y = (y.max() + y.min()) * 0.5
    mid_z = (z.max() + z.min()) * 0.5

    ax.set_xlim(mid_x - max_range, mid_x + max_range)
    ax.set_ylim(mid_y - max_range, mid_y + max_range)
    ax.set_zlim(mid_z - max_range, mid_z + max_range)

    plt.show()


def main():
    df = load_data(CSV_FILE)

    # Option 1: Visualize ALL frames
    plot_point_cloud(df)

    # Option 2: Visualize a specific frame
    # plot_point_cloud(df, frame_num=10)


if __name__ == "__main__":
    main()

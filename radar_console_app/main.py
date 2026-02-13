import os
import sys
import time
from communication.serial_manager import SerialManager
from parser.frame_parser import FrameParser
from logger.csv_logger import CSVLogger
from plotting.plot_manager import PlotManager

def select_config():
    """Prompts user to select a config file from the config folder."""
    config_dir = 'config'
    if not os.path.exists(config_dir):
        print(f"Error: {config_dir} folder not found.")
        sys.exit(1)
        
    configs = [f for f in os.listdir(config_dir) if f.endswith('.cfg')]
    if not configs:
        print("No .cfg files found in config folder.")
        sys.exit(1)
        
    print("\n--- Available Configurations ---")
    for idx, cfg in enumerate(configs):
        print(f"{idx + 1}. {cfg}")
        
    while True:
        try:
            choice = int(input("Select config file number: ")) - 1
            if 0 <= choice < len(configs):
                return os.path.join(config_dir, configs[choice])
        except ValueError:
            pass
        print("Invalid choice. Try again.")

def select_plotting_mode():
    """Prompts user to choose between 2D and 3D plotting."""
    print("\n--- Plotting Mode ---")
    print("1. 2D Plot")
    print("2. 3D Plot")
    
    while True:
        choice = input("Select mode (1 or 2): ")
        if choice == '1':
            return '2D'
        elif choice == '2':
            return '3D'
        print("Invalid choice. Try again.")

def main():
    print("=== Radar Data Acquisition and Plotting Application ===")
    
    # Selection Menus
    config_file = select_config()
    plot_mode = select_plotting_mode()
    
    # Initialize Modules
    serial_manager = SerialManager(config_port='COM6', data_port='COM7')
    parser = FrameParser()
    logger = CSVLogger()
    plotter = PlotManager(mode=plot_mode)
    
    # Connect
    if not serial_manager.connect():
        print("Could not connect to radar ports. Exiting.")
        return
        
    try:
        # Start Logger
        logger.start()
        
        # Send Configuration
        serial_manager.send_config(config_file)
        
        # Start Plotter
        plotter.start()
        
        print("\nRadar is running. Press Ctrl+C to stop.")
        
        # Main Loop
        while True:
            # Read Raw Data
            raw_data = serial_manager.read_data()
            if raw_data:
                # Parse Frames
                frames = parser.parse(raw_data)
                for frame in frames:
                    # Log to CSV
                    logger.log_frame(frame)
                    # Update Plot
                    plotter.update(frame)
            
            time.sleep(0.01) # Small delay to prevent CPU hogging
            
    except KeyboardInterrupt:
        print("\nShutdown signal received.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
    finally:
        # Clean Shutdown
        plotter.close()
        logger.close()
        serial_manager.close()
        print("Application exited cleanly.")

if __name__ == "__main__":
    main()

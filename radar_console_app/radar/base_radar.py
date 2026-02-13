from abc import ABC, abstractmethod

class BaseRadar(ABC):
    """
    Abstract base class for all radar types.
    Defines the interface for parsing frames.
    """

    def __init__(self, name):
        """
        Initialize the radar with a name.
        
        Args:
            name (str): The type or name of the radar.
        """
        self.name = name

    @abstractmethod
    def parse_frame(self, raw_data):
        """
        Parses raw data received from the serial port.
        
        Args:
            raw_data (bytes): The raw data chunk to parse.
            
        Returns:
            dict: A dictionary containing parsed frame information.
        """
        pass

    def __str__(self):
        return f"Radar Type: {self.name}"

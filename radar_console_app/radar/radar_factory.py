from .ti_radar import TIRadar
from .custom_radar import CustomRadar

class RadarFactory:
    """
    Factory class to instantiate radar objects based on selection.
    """

    @staticmethod
    def get_radar(radar_type):
        """
        Returns an instance of the requested radar type.
        
        Args:
            radar_type (int): Selection ID (1 for TI, 2 for Custom).
            
        Returns:
            BaseRadar: An instance of a subclass of BaseRadar.
        """
        if radar_type == 1:
            return TIRadar()
        elif radar_type == 2:
            return CustomRadar()
        else:
            raise ValueError(f"Unknown radar type selection: {radar_type}")

class KioskState:
    def __init__(self):
        self._is_handling_print_error = False
    
    def set_handling_print_error(self, value: bool):
        """Set flag when print job is handling an error"""
        self._is_handling_print_error = value
    
    def is_handling_print_error(self) -> bool:
        """Check if a print error is currently being handled"""
        return self._is_handling_print_error

# Global instance
kiosk_state = KioskState()

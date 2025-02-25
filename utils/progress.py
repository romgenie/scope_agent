# utils/progress.py
class ProgressIndicator:
    """Static progress indicator that doesn't cause blinking."""
    def __init__(self):
        self.active = False
    
    def start(self, message="Working"):
        """Display a static progress message without animation."""
        self.active = True
        print(f"\n{message}")
    
    def update(self, message):
        """Update the progress message if needed."""
        if self.active:
            print(f"{message}")
    
    def stop(self):
        """Stop the progress indicator."""
        self.active = False
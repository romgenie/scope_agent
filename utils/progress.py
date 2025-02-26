# utils/progress.py
import sys
import threading
import itertools
import time

class ProgressIndicator:
    """Animated progress indicator for console applications."""
    
    def __init__(self):
        self.active = False
        self._thread = None
        self._current_message = ""
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    
    def _animate(self):
        """Animation loop that runs in a separate thread."""
        while self.active:
            if self._current_message:
                sys.stdout.write(f'\r{next(self.spinner)} {self._current_message}')
                sys.stdout.flush()
                time.sleep(0.1)
    
    def start(self, message="Working"):
        """Start the progress indicator with an initial message."""
        if not self.active:
            self.active = True
            self._current_message = message
            print(f"\n{next(self.spinner)} {message}", end="")  # Make initial indicator more visible
            sys.stdout.flush()
            self._thread = threading.Thread(target=self._animate)
            self._thread.daemon = True
            self._thread.start()
    
    def update(self, message):
        """Update the progress message."""
        if self.active:
            self._current_message = message
            sys.stdout.write('\r' + ' ' * (len(self._current_message) + 2))  # Clear line
            sys.stdout.flush()
    
    def stop(self):
        """Stop the progress indicator."""
        if self.active:
            self.active = False
            if self._thread:
                self._thread.join()
            sys.stdout.write('\r' + ' ' * (len(self._current_message) + 2) + '\r')  # Clear line
            sys.stdout.flush()
            print()  # Add a newline after stopping
    """Animated progress indicator for console applications."""
    
    def __init__(self):
        self.active = False
        self._thread = None
        self._current_message = ""
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    
    def _animate(self):
        """Animation loop that runs in a separate thread."""
        while self.active:
            if self._current_message:
                sys.stdout.write(f'\r{next(self.spinner)} {self._current_message}')
                sys.stdout.flush()
                time.sleep(0.1)
    
    def start(self, message="Working"):
        """Start the progress indicator with an initial message."""
        if not self.active:
            self.active = True
            self._current_message = message
            print()  # Start on a new line
            self._thread = threading.Thread(target=self._animate)
            self._thread.daemon = True
            self._thread.start()
    
    def update(self, message):
        """Update the progress message."""
        if self.active:
            self._current_message = message
            sys.stdout.write('\r' + ' ' * (len(self._current_message) + 2))  # Clear line
            sys.stdout.flush()
    
    def stop(self):
        """Stop the progress indicator."""
        if self.active:
            self.active = False
            if self._thread:
                self._thread.join()
            sys.stdout.write('\r' + ' ' * (len(self._current_message) + 2) + '\r')  # Clear line
            sys.stdout.flush()
import logging
import os
import sys
from datetime import datetime


class Logger:
    def __init__(self, name: str = "carrymem"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
            try:
                os.makedirs(logs_dir, exist_ok=True)
                log_file = os.path.join(logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(logging.INFO)
                formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except OSError:
                pass

            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(logging.Formatter("%(name)s - %(levelname)s - %(message)s"))
            self.logger.addHandler(console_handler)
            self.logger.propagate = False

    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, exc_info: bool = False, **kwargs):
        self.logger.error(message, *args, exc_info=exc_info, **kwargs)

    def critical(self, message: str, *args, exc_info: bool = False, **kwargs):
        self.logger.critical(message, *args, exc_info=exc_info, **kwargs)


logger = Logger()

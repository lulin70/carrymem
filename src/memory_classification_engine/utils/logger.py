import logging
import os
import sys
from datetime import datetime


class Logger:
    def __init__(self, name: str = "memory-classification-engine"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
            )
            try:
                os.makedirs(logs_dir, exist_ok=True)
                log_file = os.path.join(
                    logs_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log"
                )
                file_handler = logging.FileHandler(log_file)
                file_handler.setLevel(logging.INFO)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except OSError:
                pass

            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(
                logging.Formatter("%(name)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(console_handler)
            self.logger.propagate = False

    def debug(self, message: str):
        self.logger.debug(message)

    def info(self, message: str):
        self.logger.info(message)

    def warning(self, message: str):
        self.logger.warning(message)

    def error(self, message: str, exc_info: bool = False):
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False):
        self.logger.critical(message, exc_info=exc_info)


logger = Logger()

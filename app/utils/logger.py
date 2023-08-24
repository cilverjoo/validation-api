import os

from loguru import logger

from app.config import Config, load_env

file_log_format = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{name}:{function}:{line} - "
    "{message}"
)

log_file = "/app/logs/app.log"

local_env_path = load_env()
if local_env_path:
    log_dir_path = os.path.join(local_env_path, "logs")
    os.makedirs(log_dir_path, exist_ok=True)
    log_file = os.path.join(log_dir_path, "app.log")

logger.remove()
logger.add(log_file, level=Config.log_level, format=file_log_format, rotation="10 MB", retention="10 days")

__all__ = ["logger"]

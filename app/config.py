from dotenv import find_dotenv, load_dotenv
import os


class Config:
    load_dotenv()
    dotenv_path = find_dotenv()
    app_env = os.getenv("APP_ENV", "production")
    log_level = os.getenv("LOG_LEVEL", "INFO")


def load_env():
    if Config.app_env == "local":
        return os.path.dirname(Config.dotenv_path)
    else:
        return None

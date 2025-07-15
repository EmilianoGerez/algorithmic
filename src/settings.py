from pydantic import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Market Structure Detection"
    debug: bool = True

settings = Settings()

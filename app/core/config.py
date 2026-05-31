import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


@dataclass
class Settings:
    app_mode: str = os.getenv("APP_MODE", "mock")
    tr_phone: str = os.getenv("TR_PHONE_NUMBER", "")
    tr_pin: str = os.getenv("TR_PIN", "")
    tr_cookies_file: str = os.getenv("TR_COOKIES_FILE", "./pytr_cookies.json")
    actual_url: str = os.getenv("ACTUAL_URL", "")
    actual_password: str = os.getenv("ACTUAL_PASSWORD", "")
    actual_budget_id: str = os.getenv("ACTUAL_BUDGET_ID", "")
    actual_account_name: str = os.getenv("ACTUAL_ACCOUNT_NAME", "")
    # E2E Encryption support for Actual Budget files (AES-256-GCM)
    actual_encryption_password: str = os.getenv("ACTUAL_ENCRYPTION_PASSWORD", "")


settings = Settings()

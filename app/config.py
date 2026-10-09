from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./kenova_shop.db")
    admin_ids_raw: str = os.getenv("ADMIN_IDS", "")
    shop_name: str = os.getenv("SHOP_NAME", "KENOVA SHOP")
    support_username: str = os.getenv("SUPPORT_USERNAME", "@KENOVA_Support")
    min_deposit: int = int(os.getenv("MIN_DEPOSIT", "20"))
    bkash_number: str = os.getenv("PAYMENT_BKASH_NUMBER", "")
    nagad_number: str = os.getenv("PAYMENT_NAGAD_NUMBER", "")
    rocket_number: str = os.getenv("PAYMENT_ROCKET_NUMBER", "")

    @property
    def admin_ids(self) -> set[int]:
        result: set[int] = set()
        for value in self.admin_ids_raw.split(","):
            value = value.strip()
            if value.isdigit():
                result.add(int(value))
        return result

    def validate(self) -> None:
        if not self.bot_token or self.bot_token == "PASTE_BOTFATHER_TOKEN_HERE":
            raise ValueError("BOT_TOKEN is missing. Add your BotFather token to .env.")
        if self.min_deposit < 1:
            raise ValueError("MIN_DEPOSIT must be at least 1.")

settings = Settings()

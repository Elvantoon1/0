from dotenv import load_dotenv
import os
from loguru import logger

# تحميل متغيرات البيئة من ملف .env
load_dotenv()

class Config:
    """
    فئة لتخزين إعدادات البوت ومتغيرات البيئة.
    """
    
    # ---------------------------
    # الإعدادات الأساسية
    # ---------------------------
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    try:
        ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
    except ValueError:
        logger.error("ADMIN_ID environment variable is not a valid integer.")
        ADMIN_ID: int = 0
    
    # ---------------------------
    # إعدادات قاعدة البيانات
    # ---------------------------
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///data/bot.db")
    
    # ---------------------------
    # إعدادات الويب هوك (للنشر على Render)
    # ---------------------------
    WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    WEB_SERVER_HOST: str = "0.0.0.0"
    try:
        WEB_SERVER_PORT: int = int(os.getenv("PORT", 8080))
    except ValueError:
        logger.error("PORT environment variable is not a valid integer.")
        WEB_SERVER_PORT: int = 8080
    
    # ---------------------------
    # إعدادات القنوات
    # ---------------------------
    PROOF_CHANNEL_ID: str = os.getenv("PROOF_CHANNEL_ID", "")
    ACTIVATION_CHANNEL_ID: str = os.getenv("ACTIVATION_CHANNEL_ID", "")

    # ---------------------------
    # الإعدادات الافتراضية للقاعدة (تستخدم عند تهيئة DB لأول مرة)
    # ---------------------------
    DEFAULT_SETTINGS = {
        "daily_bonus_points": "10",
        "invite_points": "5",
        "proof_points": "3",
        "pro_days_duration": "30",
        "pro_points_cost": "100",
        "welcome_message": "مرحباً بك في بوت الأرقام المجانية! ابدأ باستخدام /start.",
        "broadcast_interval_hours": "24",
        "default_language": "ar",
        "numbers_channel_link": "https://t.me/your_numbers_channel"
    }

    @staticmethod
    def validate():
        """التحقق من صحة المتغيرات الأساسية."""
        if not Config.BOT_TOKEN:
            logger.error("BOT_TOKEN is not set in environment variables.")
            raise ValueError("BOT_TOKEN is required.")
        if Config.ADMIN_ID == 0:
            logger.warning("ADMIN_ID is not set or set to 0. Admin features will be disabled.")
        
        logger.info("Configuration loaded and validated successfully.")

# التحقق من الإعدادات عند تحميل الملف
Config.validate()

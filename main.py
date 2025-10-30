import asyncio
import os
import sys
from loguru import logger
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Request, Response
import uvicorn

# --- Configure Logging ---
logger.remove()
logger.add(sys.stderr, format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}", level="INFO")

# Import Configuration
from config import Config

# Import Database and Managers
from database import Database
from services.points_manager import PointsManager
from services.pro_manager import ProManager
from services.ads_manager import AdsManager
from services.setup_manager import SetupManager
from services.number_manager import NumberManager # New Manager

# Import Handlers
from handlers import user_handlers, admin_handlers, number_handlers # New Handler

# --- Initialization ---
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Configuration Error: {e}")
    sys.exit(1)

DB = Database(Config.DATABASE_URL)
BOT = Bot(token=Config.BOT_TOKEN, parse_mode="HTML")
DP = Dispatcher()

# Initialize Managers (Dependency Injection)
PM = PointsManager(DB)
PRM = ProManager(DB)
ADM = AdsManager(DB, PM)
SM = SetupManager(DB)
NM = NumberManager(DB) # Initialize Number Manager

# Inject dependencies into handlers
user_handlers.DB = DB
user_handlers.PM = PM
user_handlers.PRM = PRM
user_handlers.SM = SM
user_handlers.ADM = ADM
user_handlers.NM = NM # Inject new manager

admin_handlers.DB = DB
admin_handlers.PM = PM
admin_handlers.PRM = PRM
admin_handlers.SM = SM
admin_handlers.ADM = ADM
admin_handlers.NM = NM # Inject new manager

number_handlers.DB = DB
number_handlers.PM = PM
number_handlers.PRM = PRM
number_handlers.SM = SM
number_handlers.NM = NM # Inject new manager

# Register Handlers
DP.include_router(admin_handlers.router)
DP.include_router(user_handlers.router)
DP.include_router(number_handlers.router) # Register new handler

# --- FastAPI Setup for Webhook ---
app = FastAPI(
    title="nxrxbot-pro Telegram Bot Webhook",
    description="Backend for handling Telegram Webhook updates and health checks.",
    version="1.0.0"
)

@app.on_event("startup")
async def on_startup():
    """تهيئة قاعدة البيانات وضبط الويب هوك عند بدء التشغيل."""
    logger.info("Starting up application...")
    
    # 1. تهيئة قاعدة البيانات
    await DB.init_db(Config.DEFAULT_SETTINGS)
    
    # 2. ضبط الويب هوك إذا كان WEBHOOK_URL متاحًا
    if Config.WEBHOOK_URL:
        webhook_url = f"{Config.WEBHOOK_URL}/webhook"
        logger.info(f"Setting webhook to: {webhook_url}")
        try:
            await BOT.set_webhook(url=webhook_url, secret_token=Config.WEBHOOK_SECRET)
            logger.info("Webhook set successfully.")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            
    logger.info("Application startup complete.")

@app.on_event("shutdown")
async def on_shutdown():
    """إغلاق الاتصالات عند إغلاق التطبيق."""
    logger.info("Shutting down application...")
    await DB.close()
    await BOT.session.close()
    logger.info("Application shutdown complete.")

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """معالج طلبات الويب هوك من Telegram."""
    if Config.WEBHOOK_SECRET and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != Config.WEBHOOK_SECRET:
        logger.warning("Webhook request with invalid secret token.")
        return Response(status_code=403)
        
    try:
        # قراءة الجسم كـ JSON
        json_data = await request.json()
        
        # التحقق من أن الجسم يحتوي على تحديث صالح
        if not json_data:
            return Response(status_code=200)

        update = Update.model_validate(json_data, context={"bot": BOT})
        
        # معالجة التحديث
        await DP.feed_update(BOT, update)
        
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        # يجب أن يعود البوت بـ 200 حتى لو حدث خطأ داخلي لتجنب إعادة إرسال التحديث
        return Response(status_code=200)
    
    return Response(status_code=200)

@app.get("/healthz")
async def health_check():
    """نقطة فحص الصحة لـ Render."""
    return {"status": "ok"}

# --- Polling Mode (Local Development) ---
async def main_polling():
    """تشغيل البوت في وضع Polling."""
    logger.info("Starting bot in Polling mode...")
    
    # تهيئة قاعدة البيانات
    await DB.init_db(Config.DEFAULT_SETTINGS)
    
    # حذف الويب هوك القديم إذا وجد
    await BOT.delete_webhook(drop_pending_updates=True)
    
    # بدء البوت
    await DP.start_polling(BOT)

if __name__ == "__main__":
    if Config.WEBHOOK_URL:
        # تشغيل FastAPI مع Uvicorn في وضع الويب هوك
        logger.info(f"Starting Uvicorn server on {Config.WEB_SERVER_HOST}:{Config.WEB_SERVER_PORT}")
        uvicorn.run(
            "main:app", 
            host=Config.WEB_SERVER_HOST, 
            port=Config.WEB_SERVER_PORT, 
            log_level="info"
        )
    else:
        # تشغيل البوت في وضع Polling
        try:
            asyncio.run(main_polling())
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
        except Exception as e:
            logger.error(f"An error occurred during polling: {e}")

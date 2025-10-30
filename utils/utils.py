from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from loguru import logger
from typing import Optional

async def safe_edit_message_text(
    message: types.Message,
    text: str,
    reply_markup: Optional[types.InlineKeyboardMarkup] = None
) -> Optional[types.Message]:
    """
    تعديل رسالة موجودة بأمان، مع معالجة الأخطاء الشائعة (مثل عدم وجود تغيير في النص).
    
    :param message: كائن الرسالة.
    :param text: النص الجديد.
    :param reply_markup: لوحة المفاتيح الجديدة.
    :return: كائن الرسالة المعدلة أو None في حالة الفشل.
    """
    try:
        if message.text == text and message.reply_markup == reply_markup:
            # لا حاجة للتعديل إذا لم يتغير شيء
            return message
            
        return await message.edit_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        # معالجة أخطاء عدم وجود تغيير في الرسالة
        if "message is not modified" in str(e):
            return message
        logger.warning(f"TelegramBadRequest during safe_edit_message_text: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in safe_edit_message_text: {e}")
        return None

async def safe_send_message(
    bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[types.InlineKeyboardMarkup | types.ReplyKeyboardMarkup] = None
) -> Optional[types.Message]:
    """
    إرسال رسالة بأمان مع معالجة الأخطاء.
    
    :param bot: كائن البوت (Dispatcher.bot).
    :param chat_id: معرف الدردشة.
    :param text: نص الرسالة.
    :param reply_markup: لوحة المفاتيح.
    :return: كائن الرسالة المرسلة أو None في حالة الفشل.
    """
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in safe_send_message to {chat_id}: {e}")
        return None

def extract_user_data(user: types.User) -> tuple:
    """استخلاص بيانات المستخدم الأساسية."""
    return (
        user.id,
        user.username or "",
        user.first_name or "",
        user.last_name or ""
    )

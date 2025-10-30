from typing import Dict, Any, List, Optional
from loguru import logger
from database import Database
from config import Config

class SetupManager:
    """
    إدارة نظام الإعداد الأولي للبوت (Setup) وإدارة القنوات الإلزامية والإعدادات العامة.
    """

    def __init__(self, db: Database):
        """
        تهيئة مدير الإعدادات.

        :param db: كائن قاعدة البيانات (Database instance).
        """
        self.db = db

    async def is_setup_complete(self) -> bool:
        """
        التحقق مما إذا كان الإعداد الأولي قد اكتمل.
        نعتبر الإعداد مكتملاً إذا تم تعيين قيمة "setup_complete" في جدول الإعدادات إلى '1'.

        :return: True إذا اكتمل الإعداد، False بخلاف ذلك.
        """
        setting = await self.db.get_setting("setup_complete")
        return setting == "1"

    async def mark_setup_complete(self):
        """
        وضع علامة على أن الإعداد الأولي قد اكتمل.
        """
        await self.db.set_setting("setup_complete", "1")
        logger.info("Initial setup marked as complete.")

    # --- إدارة القنوات الإلزامية ---

    async def get_mandatory_channels(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة القنوات الإلزامية النشطة.
        
        :return: قائمة من القواميس ببيانات القنوات.
        """
        return await self.db.get_mandatory_channels()

    async def add_mandatory_channel(self, admin_id: int, channel_id: str, is_group: bool = False) -> bool:
        """
        إضافة قناة أو مجموعة إجبارية للاشتراك.

        :param admin_id: معرف المدير.
        :param channel_id: معرف القناة (@username أو ID).
        :param is_group: هل هو مجموعة (True) أم قناة (False).
        :return: True عند النجاح.
        """
        try:
            sql = """
                INSERT INTO mandatory_channels (channel_id, is_group)
                VALUES (?, ?)
            """
            await self.db.execute(sql, (channel_id, 1 if is_group else 0))
            await self.db.log_action(admin_id, "MANDATORY_CHANNEL_ADDED", f"Channel: {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add mandatory channel {channel_id}: {e}")
            return False

    async def remove_mandatory_channel(self, admin_id: int, channel_id: str) -> bool:
        """
        إزالة قناة أو مجموعة إجبارية.

        :param admin_id: معرف المدير.
        :param channel_id: معرف القناة.
        :return: True عند النجاح.
        """
        try:
            sql = "DELETE FROM mandatory_channels WHERE channel_id = ?"
            await self.db.execute(sql, (channel_id,))
            await self.db.log_action(admin_id, "MANDATORY_CHANNEL_REMOVED", f"Channel: {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove mandatory channel {channel_id}: {e}")
            return False
            
    # --- إدارة الإعدادات العامة ---

    async def get_welcome_message(self) -> str:
        """
        جلب رسالة الترحيب.
        
        :return: رسالة الترحيب المحفوظة أو الافتراضية.
        """
        message = await self.db.get_setting("welcome_message")
        return message or Config.DEFAULT_SETTINGS["welcome_message"]

    async def update_setting(self, admin_id: int, key: str, value: str) -> bool:
        """
        تحديث قيمة إعداد عام.
        
        :param admin_id: معرف المدير.
        :param key: مفتاح الإعداد.
        :param value: القيمة الجديدة.
        :return: True عند النجاح.
        """
        try:
            await self.db.set_setting(key, value)
            await self.db.log_action(admin_id, "SETTING_UPDATED", f"Key: {key}, Value: {value}")
            return True
        except Exception as e:
            logger.error(f"Failed to update setting {key}: {e}")
            return False

    async def check_user_subscription(self, bot, user_id: int) -> Optional[List[str]]:
        """
        التحقق من اشتراك المستخدم في جميع القنوات الإلزامية.

        :param bot: كائن البوت (للوصول إلى Telegram API).
        :param user_id: معرف المستخدم.
        :return: قائمة بأسماء القنوات التي لم يشترك بها المستخدم، أو None إذا كان مشتركاً في جميعها.
        """
        channels = await self.get_mandatory_channels()
        unsubscribed_channels = []
        
        for channel in channels:
            channel_id = channel['channel_id']
            try:
                # استخدام get_chat_member للتحقق من حالة الاشتراك
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                # حالة left, kicked, banned تعني عدم الاشتراك
                if member.status in ['left', 'kicked', 'banned']:
                    unsubscribed_channels.append(channel_id)
            except Exception as e:
                # إذا حدث خطأ (مثل عدم وجود البوت في القناة كمدير)، نعتبره غير مشترك
                logger.warning(f"Could not check subscription for channel {channel_id}: {e}")
                unsubscribed_channels.append(channel_id)

        return unsubscribed_channels if unsubscribed_channels else None

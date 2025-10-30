from typing import Dict, Any, List, Optional
from loguru import logger
from database import Database
from services.points_manager import PointsManager
import random

class AdsManager:
    """
    إدارة نظام الإعلانات (View-for-Points) في البوت.
    تتضمن إدارة الإعلانات (CRUD)، وعرضها، ومكافأة المستخدمين على المشاهدة.
    """

    def __init__(self, db: Database, points_manager: PointsManager):
        """
        تهيئة مدير الإعلانات.

        :param db: كائن قاعدة البيانات (Database instance).
        :param points_manager: كائن مدير النقاط (PointsManager instance).
        """
        self.db = db
        self.points_manager = points_manager

    # --- إدارة الإعلانات (Admin CRUD) ---

    async def create_ad(self, admin_id: int, ad_type: str, content: str, reward_points: int, media_file_id: Optional[str] = None) -> Optional[int]:
        """
        إنشاء إعلان جديد.

        :param admin_id: معرف المدير.
        :param ad_type: نوع الإعلان (text, photo, video, link).
        :param content: محتوى الإعلان (النص أو الرابط).
        :param reward_points: عدد النقاط الممنوحة للمشاهدة.
        :param media_file_id: معرف ملف الوسائط (لصور/فيديو Telegram).
        :return: معرف الإعلان الذي تم إنشاؤه، أو None في حالة الفشل.
        """
        try:
            sql = """
                INSERT INTO ads (ad_type, content, media_file_id, reward_points, created_by)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor = await self.db.execute(sql, (ad_type, content, media_file_id, reward_points, admin_id))
            ad_id = cursor.lastrowid
            await self.db.log_action(admin_id, "AD_CREATED", f"Ad ID: {ad_id}, Type: {ad_type}")
            return ad_id
        except Exception as e:
            logger.error(f"Failed to create ad: {e}")
            return None

    async def get_ad(self, ad_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب بيانات إعلان معين.
        
        :param ad_id: معرف الإعلان.
        :return: بيانات الإعلان، أو None.
        """
        sql = "SELECT * FROM ads WHERE id = ?"
        return await self.db.fetchone(sql, (ad_id,))

    async def get_all_ads(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع الإعلانات.
        
        :return: قائمة من القواميس ببيانات الإعلانات.
        """
        sql = "SELECT id, ad_type, content, reward_points, is_active FROM ads ORDER BY id DESC"
        return await self.db.fetchall(sql)

    async def update_ad_status(self, admin_id: int, ad_id: int, is_active: bool) -> bool:
        """
        تحديث حالة الإعلان (تفعيل/تعطيل).
        
        :param admin_id: معرف المدير.
        :param ad_id: معرف الإعلان.
        :param is_active: الحالة الجديدة (True لنشط، False لغير نشط).
        :return: True عند النجاح.
        """
        try:
            status = 1 if is_active else 0
            sql = "UPDATE ads SET is_active = ? WHERE id = ?"
            await self.db.execute(sql, (status, ad_id))
            await self.db.log_action(admin_id, "AD_STATUS_UPDATED", f"Ad ID: {ad_id}, Status: {status}")
            return True
        except Exception as e:
            logger.error(f"Failed to update ad status: {e}")
            return False

    async def delete_ad(self, admin_id: int, ad_id: int) -> bool:
        """
        حذف إعلان.
        
        :param admin_id: معرف المدير.
        :param ad_id: معرف الإعلان.
        :return: True عند النجاح.
        """
        try:
            sql = "DELETE FROM ads WHERE id = ?"
            await self.db.execute(sql, (ad_id,))
            await self.db.log_action(admin_id, "AD_DELETED", f"Ad ID: {ad_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete ad: {e}")
            return False

    # --- منطق عرض الإعلانات ومكافأة المشاهدة ---

    async def get_random_unviewed_ad(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب إعلان عشوائي نشط لم يشاهده المستخدم بعد.
        
        :param user_id: معرف المستخدم.
        :return: بيانات الإعلان، أو None.
        """
        # 1. جلب جميع الإعلانات النشطة
        active_ads_sql = "SELECT id FROM ads WHERE is_active = 1"
        active_ads = await self.db.fetchall(active_ads_sql)
        
        if not active_ads:
            return None

        active_ad_ids = [ad['id'] for ad in active_ads]

        # 2. جلب الإعلانات التي شاهدها المستخدم
        viewed_ads_sql = "SELECT ad_id FROM ad_views WHERE user_id = ?"
        viewed_ads = await self.db.fetchall(viewed_ads_sql, (user_id,))
        viewed_ad_ids = {ad['ad_id'] for ad in viewed_ads}

        # 3. تحديد الإعلانات غير المشاهدة
        unviewed_ad_ids = [ad_id for ad_id in active_ad_ids if ad_id not in viewed_ad_ids]

        if not unviewed_ad_ids:
            return None

        # 4. اختيار إعلان عشوائي
        random_ad_id = random.choice(unviewed_ad_ids)
        return await self.get_ad(random_ad_id)

    async def mark_ad_viewed_and_reward(self, user_id: int, ad_id: int) -> bool:
        """
        تسجيل مشاهدة الإعلان ومنح النقاط للمستخدم.

        :param user_id: معرف المستخدم.
        :param ad_id: معرف الإعلان.
        :return: True عند النجاح.
        """
        ad = await self.get_ad(ad_id)
        if not ad or ad['is_active'] == 0:
            logger.warning(f"Attempted to reward for inactive or non-existent ad {ad_id} by user {user_id}.")
            return False

        # 1. التحقق مرة أخرى لضمان عدم تكرار المشاهدة
        view_check_sql = "SELECT id FROM ad_views WHERE user_id = ? AND ad_id = ?"
        viewed = await self.db.fetchone(view_check_sql, (user_id, ad_id))
        
        if viewed:
            logger.warning(f"User {user_id} already viewed ad {ad_id}.")
            return False

        # 2. تسجيل المشاهدة
        try:
            view_sql = "INSERT INTO ad_views (ad_id, user_id) VALUES (?, ?)"
            await self.db.execute(view_sql, (ad_id, user_id))
        except Exception as e:
            logger.error(f"Failed to log ad view for user {user_id}, ad {ad_id}: {e}")
            return False

        # 3. منح النقاط
        reward = ad['reward_points']
        reason = f"مشاهدة إعلان رقم {ad_id}"
        success = await self.points_manager.add_points(user_id, reward, reason, ad_id)

        if success:
            await self.db.log_action(user_id, "AD_VIEWED_AND_REWARDED", f"Ad ID: {ad_id}, Points: {reward}")
            return True
        else:
            # إذا فشل منح النقاط، يجب التفكير في حذف سجل المشاهدة (معقد، لذا نكتفي بالتسجيل)
            logger.error(f"Failed to reward user {user_id} for ad {ad_id} despite logging view.")
            return False

    async def get_ad_stats(self, ad_id: int) -> Dict[str, Any]:
        """
        جلب إحصائيات إعلان معين (عدد المشاهدات).
        
        :param ad_id: معرف الإعلان.
        :return: قاموس يحتوي على عدد المشاهدات وبيانات الإعلان.
        """
        sql = "SELECT COUNT(id) as views FROM ad_views WHERE ad_id = ?"
        result = await self.db.fetchone(sql, (ad_id,))
        
        ad_info = await self.get_ad(ad_id)
        
        if not ad_info:
            return {"views": 0, "ad_info": None}
            
        return {
            "views": result['views'] if result else 0,
            "ad_info": ad_info
        }

    async def get_total_unviewed_ads_count(self, user_id: int) -> int:
        """
        جلب عدد الإعلانات النشطة التي لم يشاهدها المستخدم بعد.
        
        :param user_id: معرف المستخدم.
        :return: عدد الإعلانات غير المشاهدة.
        """
        sql = """
            SELECT COUNT(a.id)
            FROM ads a
            LEFT JOIN ad_views av ON a.id = av.ad_id AND av.user_id = ?
            WHERE a.is_active = 1 AND av.id IS NULL
        """
        result = await self.db.fetchone(sql, (user_id,))
        # نتيجة fetchone لـ COUNT هي صف واحد يحتوي على قيمة واحدة
        return result[0] if result and result[0] is not None else 0

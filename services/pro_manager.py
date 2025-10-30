from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from loguru import logger
import secrets
import string

# Import the Database class from the database module
from database import Database
from config import Config

class ProManager:
    """
    إدارة نظام PRO (الاشتراك المميز) في البوت.
    تتضمن تفعيل/إلغاء الاشتراكات، التحقق من الصلاحية، وإدارة أكواد PRO.
    """

    def __init__(self, db: Database):
        """
        تهيئة مدير PRO.

        :param db: كائن قاعدة البيانات (Database instance).
        """
        self.db = db
        # قيم افتراضية يتم تحديثها من الإعدادات
        self.pro_days_duration = int(Config.DEFAULT_SETTINGS.get("pro_days_duration", "30"))
        self.pro_points_cost = int(Config.DEFAULT_SETTINGS.get("pro_points_cost", "100"))

    async def _get_pro_config(self):
        """
        جلب إعدادات PRO من قاعدة البيانات.
        """
        try:
            self.pro_days_duration = int(await self.db.get_setting("pro_days_duration") or self.pro_days_duration)
            self.pro_points_cost = int(await self.db.get_setting("pro_points_cost") or self.pro_points_cost)
        except Exception as e:
            logger.error(f"Error loading PRO config: {e}")

    async def is_pro(self, user_id: int) -> bool:
        """
        التحقق من حالة PRO للمستخدم.
        
        :param user_id: معرف المستخدم.
        :return: True إذا كان المستخدم PRO ونشط، False خلاف ذلك.
        """
        user = await self.db.get_user(user_id)
        if not user:
            return False

        if user['is_pro'] == 1 and user['pro_expiry']:
            try:
                expiry_date = datetime.strptime(user['pro_expiry'], "%Y-%m-%d %H:%M:%S")
                if expiry_date > datetime.now():
                    return True
                else:
                    # انتهاء الصلاحية - تحديث حالة المستخدم
                    await self.deactivate_pro(user_id, "expired")
                    return False
            except ValueError:
                # خطأ في تنسيق التاريخ
                await self.deactivate_pro(user_id, "date_format_error")
                return False
        
        return False

    async def activate_pro(self, user_id: int, duration_days: int, method: str, related_id: Optional[str] = None) -> bool:
        """
        تفعيل حالة PRO للمستخدم.

        :param user_id: معرف المستخدم.
        :param duration_days: مدة الاشتراك بالأيام.
        :param method: طريقة التفعيل (points, code, admin).
        :param related_id: معرف الكود أو العملية المرتبطة (اختياري).
        :return: True عند النجاح، False عند الفشل.
        """
        try:
            expiry_date = datetime.now() + timedelta(days=duration_days)
            expiry_str = expiry_date.strftime("%Y-%m-%d %H:%M:%S")

            # 1. تحديث جدول المستخدمين
            await self.db.execute(
                "UPDATE users SET is_pro = 1, pro_expiry = ? WHERE id = ?",
                (expiry_str, user_id)
            )

            # 2. تسجيل الاشتراك في جدول pro_subscriptions
            await self.db.execute(
                """
                INSERT INTO pro_subscriptions (user_id, expires_at, duration_days, method)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, expiry_str, duration_days, method)
            )
            
            await self.db.log_action(user_id, "PRO_ACTIVATED", f"Duration: {duration_days} days, Method: {method}, Related: {related_id}")

            logger.info(f"PRO activated for user {user_id} for {duration_days} days via {method}.")
            return True
        except Exception as e:
            logger.error(f"Failed to activate PRO for user {user_id}: {e}")
            return False

    async def deactivate_pro(self, user_id: int, reason: str) -> bool:
        """
        إلغاء تفعيل حالة PRO للمستخدم.

        :param user_id: معرف المستخدم.
        :param reason: سبب الإلغاء (expired, admin_revoked, etc.).
        :return: True عند النجاح، False عند الفشل.
        """
        try:
            # 1. تحديث جدول المستخدمين
            await self.db.execute(
                "UPDATE users SET is_pro = 0, pro_expiry = NULL WHERE id = ?",
                (user_id,)
            )

            # 2. تحديث الاشتراك الأخير كغير نشط (للتاريخ)
            await self.db.execute(
                """
                UPDATE pro_subscriptions SET is_active = 0 
                WHERE user_id = ? AND is_active = 1
                """,
                (user_id,)
            )
            
            # 3. تسجيل الإجراء
            await self.db.log_action(user_id, "PRO_DEACTIVATED", f"Reason: {reason}")

            logger.info(f"PRO deactivated for user {user_id}. Reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate PRO for user {user_id}: {e}")
            return False

    # --- إدارة أكواد PRO ---

    def _generate_pro_code(self, length: int = 10) -> str:
        """
        توليد كود PRO عشوائي.

        :param length: طول الكود المطلوب.
        :return: كود PRO مكون من أحرف كبيرة وأرقام.
        """
        characters = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(characters) for _ in range(length))

    async def create_pro_code(self, admin_id: int, duration_days: int) -> Optional[str]:
        """
        إنشاء كود PRO جديد.

        :param admin_id: معرف المدير الذي أنشأ الكود.
        :param duration_days: مدة التفعيل بالأيام.
        :return: الكود الذي تم إنشاؤه، أو None في حالة الفشل.
        """
        code = self._generate_pro_code()
        try:
            await self.db.execute(
                "INSERT INTO pro_codes (code, duration_days, created_by) VALUES (?, ?, ?)",
                (code, duration_days, admin_id)
            )
            await self.db.log_action(admin_id, "PRO_CODE_CREATED", f"Code: {code}, Days: {duration_days}")
            return code
        except Exception as e:
            logger.error(f"Failed to create PRO code: {e}")
            return None

    async def use_pro_code(self, user_id: int, code: str) -> bool:
        """
        استخدام كود PRO لتفعيل الاشتراك.

        :param user_id: معرف المستخدم.
        :param code: كود PRO المراد استخدامه.
        :return: True عند النجاح، False عند الفشل.
        """
        code_data = await self.db.fetchone(
            "SELECT * FROM pro_codes WHERE code = ? AND is_active = 1 AND used_by IS NULL",
            (code,)
        )

        if not code_data:
            return False # الكود غير موجود أو مستخدم

        duration = code_data['duration_days']

        # 1. تفعيل الاشتراك
        success = await self.activate_pro(user_id, duration, "code", code_data['code'])

        if success:
            # 2. تحديث حالة الكود
            await self.db.execute(
                "UPDATE pro_codes SET used_by = ?, used_at = ?, is_active = 0 WHERE code = ?",
                (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), code)
            )
            await self.db.log_action(user_id, "PRO_CODE_USED", f"Code: {code}")
            return True
        
        return False

    # --- دوال لوحة تحكم الأدمن ---

    async def get_all_pro_users(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع المستخدمين المشتركين حاليًا في PRO.

        :return: قائمة من القواميس ببيانات المستخدمين (id, username, pro_expiry).
        """
        sql = "SELECT id, username, pro_expiry FROM users WHERE is_pro = 1 AND pro_expiry IS NOT NULL"
        return await self.db.fetchall(sql)

    async def get_pro_codes(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """
        جلب قائمة بأكواد PRO (النشطة أو غير النشطة).
        
        :param is_active: True لجلب الأكواد النشطة وغير المستخدمة، False لجلب الأكواد المستخدمة.
        :return: قائمة من القواميس ببيانات الأكواد.
        """
        if is_active:
            sql = "SELECT code, duration_days, created_by FROM pro_codes WHERE is_active = 1 AND used_by IS NULL"
        else:
            sql = "SELECT code, duration_days, used_by, used_at FROM pro_codes WHERE used_by IS NOT NULL"
        return await self.db.fetchall(sql)

    async def extend_pro_subscription(self, user_id: int, days: int, admin_id: int) -> Optional[datetime]:
        """
        تمديد اشتراك PRO لمستخدم حالي.

        :param user_id: معرف المستخدم.
        :param days: عدد الأيام المراد تمديدها.
        :param admin_id: معرف المدير الذي قام بالتمديد.
        :return: تاريخ الانتهاء الجديد (datetime object)، أو None إذا لم يتم العثور على المستخدم.
        """
        user = await self.db.get_user(user_id)
        if not user:
            return None

        current_expiry = datetime.now()
        if user['pro_expiry']:
            try:
                current_expiry = datetime.strptime(user['pro_expiry'], "%Y-%m-%d %H:%M:%S")
                # إذا كان قد انتهى، ابدأ من الآن، وإلا فمدد من تاريخ الانتهاء الحالي
                if current_expiry < datetime.now():
                    current_expiry = datetime.now()
            except ValueError:
                # في حالة وجود خطأ في تنسيق التاريخ، ابدأ من الآن
                current_expiry = datetime.now()

        new_expiry = current_expiry + timedelta(days=days)
        new_expiry_str = new_expiry.strftime("%Y-%m-%d %H:%M:%S")

        await self.db.execute(
            "UPDATE users SET is_pro = 1, pro_expiry = ? WHERE id = ?",
            (new_expiry_str, user_id)
        )
        
        # تسجيل الاشتراك الجديد/التمديد
        await self.db.execute(
            """
            INSERT INTO pro_subscriptions (user_id, started_at, expires_at, duration_days, method)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_expiry_str, days, "admin_extend")
        )
        await self.db.log_action(admin_id, "PRO_EXTENDED", f"User: {user_id}, Days: {days}")

        return new_expiry

    async def buy_pro_with_points(self, user_id: int, points_manager) -> bool:
        """
        شراء اشتراك PRO باستخدام النقاط.
        
        :param user_id: معرف المستخدم.
        :param points_manager: كائن PointsManager لإدارة النقاط (يجب تمريره لتجنب التبعية الدائرية).
        :return: True عند النجاح، False عند الفشل.
        """
        await self._get_pro_config() # تحديث الإعدادات
        
        user = await self.db.get_user(user_id)
        if not user or user['points'] < self.pro_points_cost:
            return False # نقاط غير كافية

        # 1. خصم النقاط
        success = await points_manager.subtract_points(
            user_id, 
            self.pro_points_cost, 
            "شراء اشتراك PRO"
        )

        if success:
            # 2. تفعيل الاشتراك
            return await self.activate_pro(
                user_id, 
                self.pro_days_duration, 
                "points"
            )
        
        return False

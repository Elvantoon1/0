from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from database import Database
from datetime import datetime, timedelta
import uuid
import random

class NumberManager:
    """
    إدارة نظام الأرقام المجانية (Virtual Numbers) في البوت.
    تتولى مسؤولية إدارة الدول والأرقام، ومعالجة طلبات الأرقام من المستخدمين.
    """

    def __init__(self, db: Database):
        """
        تهيئة مدير الأرقام.

        :param db: كائن قاعدة البيانات (Database instance).
        """
        self.db = db
        self.request_expiry_minutes = 5 # مدة صلاحية طلب الرقم بالدقائق

    # --- إدارة الدول (Admin) ---

    async def add_country(self, admin_id: int, name: str, flag: str) -> Optional[int]:
        """
        إضافة دولة جديدة.

        :param admin_id: معرف المدير.
        :param name: اسم الدولة.
        :param flag: علم الدولة (إيموجي).
        :return: معرف الدولة الذي تم إنشاؤه، أو None.
        """
        try:
            sql = "INSERT INTO countries (name, flag) VALUES (?, ?)"
            cursor = await self.db.execute(sql, (name, flag))
            country_id = cursor.lastrowid
            await self.db.log_action(admin_id, "COUNTRY_ADDED", f"ID: {country_id}, Name: {name}")
            return country_id
        except Exception as e:
            logger.error(f"Failed to add country {name}: {e}")
            return None

    async def get_country(self, country_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب بيانات دولة معينة.

        :param country_id: معرف الدولة.
        :return: قاموس ببيانات الدولة، أو None.
        """
        sql = "SELECT * FROM countries WHERE id = ?"
        return await self.db.fetchone(sql, (country_id,))

    async def get_all_countries(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع الدول النشطة مع عدد الأرقام المتاحة لكل منها.

        :return: قائمة من القواميس ببيانات الدول.
        """
        sql = """
            SELECT c.id, c.name, c.flag, COUNT(n.id) as number_count
            FROM countries c
            LEFT JOIN numbers n ON c.id = n.country_id AND n.is_active = 1
            WHERE c.is_active = 1
            GROUP BY c.id, c.name, c.flag
            HAVING number_count > 0
            ORDER BY c.name
        """
        return await self.db.fetchall(sql)

    async def get_countries_management_list(self) -> List[Dict[str, Any]]:
        """
        جلب قائمة بجميع الدول (نشطة وغير نشطة) لإدارة المدير.

        :return: قائمة من القواميس ببيانات الدول.
        """
        sql = "SELECT id, name, flag, is_active FROM countries ORDER BY name"
        return await self.db.fetchall(sql)

    # --- إدارة الأرقام (Admin) ---

    async def add_number(self, admin_id: int, country_id: int, number: str, platform: str, is_premium: bool, premium_pattern: Optional[str] = None) -> Optional[int]:
        """
        إضافة رقم جديد.

        :param admin_id: معرف المدير.
        :param country_id: معرف الدولة التابع لها الرقم.
        :param number: الرقم الفعلي.
        :param platform: المنصة (Telegram, WhatsApp, etc.).
        :param is_premium: هل الرقم مميز (True/False).
        :param premium_pattern: نمط الرقم المميز (اختياري).
        :return: معرف الرقم الذي تم إنشاؤه، أو None.
        """
        try:
            sql = """
                INSERT INTO numbers (country_id, number, platform, added_by, is_premium, premium_pattern)
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor = await self.db.execute(sql, (country_id, number, platform, admin_id, 1 if is_premium else 0, premium_pattern))
            number_id = cursor.lastrowid
            await self.db.log_action(admin_id, "NUMBER_ADDED", f"ID: {number_id}, Number: {number}")
            return number_id
        except Exception as e:
            logger.error(f"Failed to add number {number}: {e}")
            return None

    async def get_numbers_for_country(self, country_id: int, is_pro: bool, page: int, limit: int) -> List[Dict[str, Any]]:
        """
        جلب قائمة الأرقام المتاحة لدولة معينة مع دعم التصفح.

        :param country_id: معرف الدولة.
        :param is_pro: هل المستخدم PRO (لعرض الأرقام المميزة).
        :param page: رقم الصفحة.
        :param limit: عدد الأرقام في الصفحة.
        :return: قائمة من القواميس ببيانات الأرقام.
        """
        offset = (page - 1) * limit
        
        # الأرقام غير المميزة متاحة للجميع
        sql = """
            SELECT id, number, platform, is_premium
            FROM numbers
            WHERE country_id = ? AND is_active = 1
        """
        params: List[Any] = [country_id]
        
        if not is_pro:
            # المستخدم العادي يرى الأرقام غير المميزة فقط
            sql += " AND is_premium = 0"
        
        sql += " ORDER BY is_premium DESC, added_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        return await self.db.fetchall(sql, tuple(params))

    async def get_total_numbers_count(self, country_id: int) -> int:
        """
        جلب العدد الكلي للأرقام النشطة لدولة معينة.

        :param country_id: معرف الدولة.
        :return: العدد الكلي للأرقام.
        """
        sql = "SELECT COUNT(id) FROM numbers WHERE country_id = ? AND is_active = 1"
        result = await self.db.fetchone(sql, (country_id,))
        return result[0] if result else 0

    async def search_premium_numbers(self, country_id: int, pattern: str) -> List[Dict[str, Any]]:
        """
        البحث عن أرقام مميزة تطابق نمط معين (ميزة PRO).

        :param country_id: معرف الدولة.
        :param pattern: نمط البحث (يحتوي على *).
        :return: قائمة بالأرقام المطابقة.
        """
        # تحويل نمط Telegram إلى نمط SQL LIKE
        sql_pattern = pattern.replace('*', '%')
        
        sql = """
            SELECT id, number, platform
            FROM numbers
            WHERE country_id = ? AND is_active = 1 AND is_premium = 1 AND number LIKE ?
            ORDER BY added_at DESC
        """
        return await self.db.fetchall(sql, (country_id, sql_pattern))

    # --- منطق طلب الرقم (User) ---

    async def initialize_number_request(self, user_id: int, number_id: int) -> Optional[Dict[str, Any]]:
        """
        بدء عملية حجز الرقم للمستخدم.

        :param user_id: معرف المستخدم.
        :param number_id: معرف الرقم المطلوب.
        :return: بيانات طلب الرقم (بما في ذلك الرقم والمنصة وتاريخ الانتهاء)، أو None.
        """
        number_data = await self.db.fetchone(
            "SELECT id, number, platform FROM numbers WHERE id = ? AND is_active = 1",
            (number_id,)
        )
        
        if not number_data:
            return None
            
        # 1. محاكاة طلب API خارجي
        api_request_id = str(uuid.uuid4())
        
        # 2. تحديد تاريخ الانتهاء
        expires_at = datetime.now() + timedelta(minutes=self.request_expiry_minutes)
        expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")

        # 3. تسجيل الطلب
        try:
            sql = """
                INSERT INTO number_requests (user_id, number_id, api_request_id, status, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """
            await self.db.execute(sql, (user_id, number_id, api_request_id, "PENDING", expires_at_str))
            
            # 4. تحديث حالة الرقم (للتأكد من عدم استخدامه من قبل مستخدم آخر)
            await self.db.execute(
                "UPDATE numbers SET is_active = 0, last_used = ?, last_used_by = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id, number_id)
            )
            
            await self.db.log_action(user_id, "NUMBER_REQUEST_INITIATED", f"Number ID: {number_id}, API ID: {api_request_id}")
            
            return {
                "number_id": number_id,
                "number": number_data['number'],
                "platform": number_data['platform'],
                "api_request_id": api_request_id,
                "expires_at": expires_at_str
            }
        except Exception as e:
            logger.error(f"Failed to initialize number request for user {user_id}, number {number_id}: {e}")
            return None

    async def check_for_code(self, user_id: int, number_id: int) -> Optional[str]:
        """
        التحقق من وصول كود التفعيل للطلب الحالي.

        :param user_id: معرف المستخدم.
        :param number_id: معرف الرقم المطلوب.
        :return: كود التفعيل (str)، "EXPIRED" إذا انتهت الصلاحية، أو None إذا لم يصل الكود بعد.
        """
        request = await self.db.fetchone(
            """
            SELECT * FROM number_requests 
            WHERE user_id = ? AND number_id = ? AND status = 'PENDING'
            ORDER BY requested_at DESC LIMIT 1
            """,
            (user_id, number_id)
        )
        
        if not request:
            return None # لا يوجد طلب معلق

        expires_at = datetime.strptime(request['expires_at'], "%Y-%m-%d %H:%M:%S")
        
        if expires_at < datetime.now():
            await self.finalize_number_request(user_id, number_id, "EXPIRED")
            return "EXPIRED"

        # 1. محاكاة التحقق من API
        code = self._simulate_api_check(request['api_request_id'])
        
        if code:
            await self.finalize_number_request(user_id, number_id, "SUCCESS", code)
            return code
            
        return None

    def _simulate_api_check(self, api_request_id: str) -> Optional[str]:
        """
        محاكاة التحقق من API خارجي لوصول كود التفعيل.
        
        :param api_request_id: معرف الطلب الخارجي.
        :return: كود التفعيل (str) أو None.
        """
        # في بيئة الإنتاج، سيتم استبدال هذا بربط API حقيقي
        # محاكاة وصول الكود بنسبة 30%
        if random.random() < 0.3:
            # محاكاة كود تفعيل 6 أرقام
            return str(random.randint(100000, 999999))
        return None

    async def finalize_number_request(self, user_id: int, number_id: int, status: str, code: Optional[str] = None):
        """
        إنهاء طلب الرقم وتحديث حالة الرقم.

        :param user_id: معرف المستخدم.
        :param number_id: معرف الرقم.
        :param status: الحالة النهائية (SUCCESS, EXPIRED, CANCELLED).
        :param code: كود التفعيل (إذا كان SUCCESS).
        """
        # 1. تحديث حالة الطلب
        await self.db.execute(
            "UPDATE number_requests SET status = ?, code = ? WHERE user_id = ? AND number_id = ? AND status = 'PENDING'",
            (status, code, user_id, number_id)
        )
        
        # 2. تحديث حالة الرقم (إعادته كنشط إذا لم يكن ناجحاً)
        if status in ["EXPIRED", "CANCELLED"]:
            # إعادة تفعيل الرقم ليصبح متاحاً للاستخدام مرة أخرى
            await self.db.execute(
                "UPDATE numbers SET is_active = 1 WHERE id = ?",
                (number_id,)
            )
            await self.db.log_action(user_id, "NUMBER_REQUEST_FAILED", f"Number ID: {number_id}, Status: {status}")
        elif status == "SUCCESS":
            # زيادة عداد الاستخدام
            await self.db.execute(
                "UPDATE numbers SET times_used = times_used + 1 WHERE id = ?",
                (number_id,)
            )
            await self.db.log_action(user_id, "NUMBER_REQUEST_SUCCESS", f"Number ID: {number_id}, Code: {code}")

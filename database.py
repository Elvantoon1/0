import aiosqlite
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from datetime import datetime
from urllib.parse import urlparse
import os

class Database:
    """
    طبقة الوصول للبيانات (Data Access Layer - DAL) للتعامل مع قاعدة بيانات SQLite
    بشكل غير متزامن باستخدام `aiosqlite`. تتولى هذه الفئة مسؤولية الاتصال بقاعدة
    البيانات، وتنفيذ الاستعلامات، وإدارة هيكل الجداول (Schema).
    """

    def __init__(self, db_url: str):
        """
        تهيئة كائن قاعدة البيانات.

        :param db_url: مسار قاعدة البيانات (مثل: sqlite:///data/bot.db).
        """
        self.db_url = db_url
        self.db_path = self._get_db_path(db_url)
        self.conn: Optional[aiosqlite.Connection] = None
        logger.info(f"Database initialized with path: {self.db_path}")

    def _get_db_path(self, db_url: str) -> str:
        """
        تحويل URL قاعدة البيانات إلى مسار ملف محلي.

        :param db_url: مسار قاعدة البيانات على شكل URL.
        :return: المسار المحلي لملف قاعدة البيانات.
        """
        parsed = urlparse(db_url)
        if parsed.scheme == 'sqlite':
            # إزالة الشرطة المائلة الأمامية من جزء المسار
            return parsed.path.lstrip('/')
        # دعم SQLite فقط حالياً
        return parsed.path.lstrip('/')

    async def connect(self):
        """
        إنشاء اتصال غير متزامن بقاعدة البيانات.
        """
        if self.conn is None:
            try:
                # التأكد من وجود المجلد لملف SQLite
                os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
                self.conn = await aiosqlite.connect(self.db_path)
                self.conn.row_factory = aiosqlite.Row # لتمكين جلب النتائج كقاموس
                await self.conn.execute("PRAGMA foreign_keys = ON")
                await self.conn.commit()
                logger.info("Database connection established.")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise

    async def close(self):
        """
        إغلاق اتصال قاعدة البيانات.
        """
        if self.conn:
            await self.conn.close()
            self.conn = None
            logger.info("Database connection closed.")

    async def execute(self, sql: str, params: Tuple = ()) -> aiosqlite.Cursor:
        """
        تنفيذ استعلام SQL (مثل INSERT, UPDATE, DELETE).

        :param sql: استعلام SQL المراد تنفيذه.
        :param params: معلمات الاستعلام (Tuple).
        :return: كائن المؤشر (Cursor).
        """
        if self.conn is None:
            await self.connect()
        try:
            cursor = await self.conn.execute(sql, params)
            await self.conn.commit()
            return cursor
        except Exception as e:
            logger.error(f"Database execute error: {e} | SQL: {sql} | Params: {params}")
            raise

    async def fetchone(self, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """
        تنفيذ استعلام SQL وجلب نتيجة واحدة (مثل SELECT).

        :param sql: استعلام SQL المراد تنفيذه.
        :param params: معلمات الاستعلام (Tuple).
        :return: قاموس يمثل الصف الأول، أو None إذا لم يتم العثور على نتيجة.
        """
        if self.conn is None:
            await self.connect()
        try:
            async with self.conn.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Database fetchone error: {e}")
            return None

    async def fetchall(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        تنفيذ استعلام SQL وجلب جميع النتائج (مثل SELECT).

        :param sql: استعلام SQL المراد تنفيذه.
        :param params: معلمات الاستعلام (Tuple).
        :return: قائمة من القواميس تمثل النتائج.
        """
        if self.conn is None:
            await self.connect()
        try:
            async with self.conn.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Database fetchall error: {e}")
            return []

    async def init_db(self, default_settings: Dict[str, str]):
        """
        تهيئة قاعدة البيانات وإنشاء جميع الجداول المطلوبة إذا لم تكن موجودة.

        :param default_settings: قاموس بالإعدادات الافتراضية للبوت.
        """
        await self.connect()
        
        # 1. جدول المستخدمين (users)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                banned INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0,
                points INTEGER DEFAULT 0,
                invited_by INTEGER DEFAULT NULL,
                total_invites INTEGER DEFAULT 0,
                is_pro INTEGER DEFAULT 0,
                pro_expiry TEXT DEFAULT NULL,
                last_daily_bonus TEXT DEFAULT NULL,
                proofs_submitted INTEGER DEFAULT 0
            )
        """)
        
        # 2. جدول الإعدادات (settings)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # 3. جدول سجل النقاط (points_history)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS points_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                points_change INTEGER,
                reason TEXT,
                related_id INTEGER DEFAULT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 4. جدول القنوات الإلزامية (mandatory_channels)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS mandatory_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT UNIQUE, -- @username or -100...
                is_group INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # 5. جدول الإعلانات (ads)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_type TEXT, -- text, photo, video, link
                content TEXT,
                media_file_id TEXT DEFAULT NULL,
                reward_points INTEGER,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 6. جدول سجل مشاهدات الإعلانات (ad_views)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS ad_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id INTEGER,
                user_id INTEGER,
                viewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(ad_id) REFERENCES ads(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 7. جدول أكواد PRO (pro_codes)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS pro_codes (
                code TEXT PRIMARY KEY,
                duration_days INTEGER,
                created_by INTEGER,
                used_by INTEGER DEFAULT NULL,
                used_at TEXT DEFAULT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # 8. جدول اشتراكات PRO (pro_subscriptions)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS pro_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                duration_days INTEGER,
                method TEXT, -- points, code, admin
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        
        # 9. جدول الدول (countries)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                flag TEXT,
                platform TEXT DEFAULT 'Telegram',
                is_active INTEGER DEFAULT 1
            )
        """)
        
        # 10. جدول الأرقام (numbers)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_id INTEGER,
                number TEXT,
                platform TEXT,
                added_by INTEGER,
                added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_premium INTEGER DEFAULT 0,
                premium_pattern TEXT DEFAULT NULL,
                times_used INTEGER DEFAULT 0,
                last_used TEXT DEFAULT NULL,
                is_active INTEGER DEFAULT 1, -- إضافة حقل is_active
                last_used_by INTEGER DEFAULT NULL,
                FOREIGN KEY(country_id) REFERENCES countries(id) ON DELETE CASCADE
            )
        """)
        
        # 11. جدول طلبات الأرقام (number_requests)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS number_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                number_id INTEGER,
                api_request_id TEXT NOT NULL,
                status TEXT NOT NULL, -- PENDING, SUCCESS, EXPIRED, CANCELLED
                expires_at TEXT NOT NULL,
                code TEXT DEFAULT NULL,
                requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(number_id) REFERENCES numbers(id) ON DELETE CASCADE
            )
        """)
        
        # 12. جدول سجل العمليات (logs)
        await self.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                who INTEGER,
                action TEXT,
                meta TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # إدراج الإعدادات الافتراضية
        for key, value in default_settings.items():
            await self.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
                (key, value)
            )
        
        await self.conn.commit()
        logger.info("Database initialization complete: All tables created and default settings inserted.")

    # --- دوال مساعدة للوصول السريع (DAL Helpers) ---

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        جلب بيانات مستخدم معين.
        
        :param user_id: معرف المستخدم.
        :return: قاموس ببيانات المستخدم، أو None.
        """
        sql = "SELECT * FROM users WHERE id = ?"
        return await self.fetchone(sql, (user_id,))

    async def add_user(self, user_id: int, username: str, first_name: str, last_name: str, invited_by: Optional[int] = None):
        """
        إضافة مستخدم جديد أو تحديث بياناته.
        
        :param user_id: معرف المستخدم.
        :param username: اسم المستخدم.
        :param first_name: الاسم الأول.
        :param last_name: الاسم الأخير.
        :param invited_by: معرف المستخدم الداعي.
        """
        sql = """
            INSERT OR IGNORE INTO users (id, username, first_name, last_name, invited_by) 
            VALUES (?, ?, ?, ?, ?)
        """
        await self.execute(sql, (user_id, username, first_name, last_name, invited_by))
        
        if invited_by:
            # زيادة عدد الدعوات للمستخدم الداعي
            await self.execute("UPDATE users SET total_invites = total_invites + 1 WHERE id = ?", (invited_by,))

    async def update_user_points(self, user_id: int, points_change: int, reason: str, related_id: Optional[int] = None):
        """
        تحديث نقاط المستخدم وتسجيل العملية في السجل.
        
        :param user_id: معرف المستخدم.
        :param points_change: مقدار التغيير في النقاط (موجب للإضافة، سالب للخصم).
        :param reason: سبب التغيير.
        :param related_id: معرف كيان مرتبط (مثل ad_id).
        """
        await self.execute("UPDATE users SET points = points + ? WHERE id = ?", (points_change, user_id))
        
        # تسجيل العملية في سجل النقاط
        sql_log = """
            INSERT INTO points_history (user_id, points_change, reason, related_id) 
            VALUES (?, ?, ?, ?)
        """
        await self.execute(sql_log, (user_id, points_change, reason, related_id))

    async def get_setting(self, key: str) -> Optional[str]:
        """
        جلب قيمة إعداد معين.
        
        :param key: مفتاح الإعداد.
        :return: قيمة الإعداد كنص، أو None.
        """
        sql = "SELECT value FROM settings WHERE key = ?"
        result = await self.fetchone(sql, (key,))
        return result['value'] if result else None

    async def set_setting(self, key: str, value: str):
        """
        تحديث أو إدراج قيمة إعداد معين.
        
        :param key: مفتاح الإعداد.
        :param value: القيمة الجديدة.
        """
        sql = "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)"
        await self.execute(sql, (key, value))

    async def get_mandatory_channels(self) -> List[Dict[str, Any]]:
        """
        جلب القنوات الإلزامية النشطة.
        
        :return: قائمة من القواميس ببيانات القنوات.
        """
        sql = "SELECT channel_id FROM mandatory_channels WHERE is_active = 1"
        return await self.fetchall(sql)
    
    async def log_action(self, who: int, action: str, meta: str = ""):
        """
        تسجيل إجراء في جدول السجلات (logs).
        
        :param who: معرف المستخدم الذي قام بالإجراء.
        :param action: نوع الإجراء.
        :param meta: بيانات وصفية إضافية.
        """
        sql = "INSERT INTO logs (who, action, meta) VALUES (?, ?, ?)"
        await self.execute(sql, (who, action, meta))

    async def get_points_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        جلب سجل النقاط الأخير للمستخدم.

        :param user_id: معرف المستخدم.
        :param limit: الحد الأقصى لعدد العمليات المراد جلبها.
        :return: قائمة من القواميس بسجل النقاط.
        """
        sql = "SELECT points_change, reason, created_at FROM points_history WHERE user_id = ? ORDER BY id DESC LIMIT ?"
        return await self.fetchall(sql, (user_id, limit))

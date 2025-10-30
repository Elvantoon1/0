from typing import Dict, Any, Optional, List
from loguru import logger
from database import Database
from config import Config
from datetime import datetime

class PointsManager:
    """
    إدارة نظام النقاط في البوت.
    تتضمن إضافة/خصم النقاط، تسجيل السجل، وإدارة المكافآت اليومية والدعوات.
    """

    def __init__(self, db: Database):
        """
        تهيئة مدير النقاط.

        :param db: كائن قاعدة البيانات (Database instance).
        """
        self.db = db
        # قيم افتراضية يتم تحديثها من الإعدادات
        self.daily_bonus_points = int(Config.DEFAULT_SETTINGS.get("daily_bonus_points", "10"))
        self.invite_points = int(Config.DEFAULT_SETTINGS.get("invite_points", "5"))
        self.proof_points = int(Config.DEFAULT_SETTINGS.get("proof_points", "3"))

    async def _get_points_config(self):
        """
        جلب إعدادات النقاط من قاعدة البيانات.
        """
        try:
            self.daily_bonus_points = int(await self.db.get_setting("daily_bonus_points") or self.daily_bonus_points)
            self.invite_points = int(await self.db.get_setting("invite_points") or self.invite_points)
            self.proof_points = int(await self.db.get_setting("proof_points") or self.proof_points)
        except Exception as e:
            logger.error(f"Error loading Points config: {e}")

    async def add_points(self, user_id: int, points: int, reason: str, related_id: Optional[int] = None) -> bool:
        """
        إضافة نقاط إلى رصيد المستخدم وتسجيل العملية.

        :param user_id: معرف المستخدم.
        :param points: عدد النقاط المراد إضافتها (يجب أن يكون موجباً).
        :param reason: سبب الإضافة.
        :param related_id: معرف الكيان المرتبط (مثل معرف الإعلان أو المستخدم الداعي).
        :return: True عند النجاح، False عند الفشل.
        """
        if points <= 0:
            return False
        
        try:
            await self.db.update_user_points(user_id, points, reason, related_id)
            logger.info(f"Added {points} points to user {user_id} for reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to add points to user {user_id}: {e}")
            return False

    async def subtract_points(self, user_id: int, points: int, reason: str, related_id: Optional[int] = None) -> bool:
        """
        خصم نقاط من رصيد المستخدم وتسجيل العملية.
        يتحقق أولاً من أن الرصيد كافٍ.

        :param user_id: معرف المستخدم.
        :param points: عدد النقاط المراد خصمها (يجب أن يكون موجباً).
        :param reason: سبب الخصم.
        :param related_id: معرف الكيان المرتبط (مثل معرف الاشتراك).
        :return: True عند النجاح، False عند عدم كفاية الرصيد أو الفشل.
        """
        if points <= 0:
            return False
        
        user = await self.db.get_user(user_id)
        if not user or user['points'] < points:
            logger.warning(f"User {user_id} attempted to subtract {points} but only has {user['points']} points.")
            return False
        
        try:
            # الخصم يكون قيمة سالبة
            await self.db.update_user_points(user_id, -points, reason, related_id)
            logger.info(f"Subtracted {points} points from user {user_id} for reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Failed to subtract points from user {user_id}: {e}")
            return False

    # --- مكافآت وكسب النقاط ---

    async def claim_daily_bonus(self, user_id: int) -> Optional[int]:
        """
        منح المكافأة اليومية للمستخدم.

        :param user_id: معرف المستخدم.
        :return: عدد النقاط الممنوحة، أو 0 إذا تم المطالبة بها بالفعل اليوم، أو None عند خطأ.
        """
        await self._get_points_config()
        user = await self.db.get_user(user_id)
        if not user:
            return None

        today = datetime.now().strftime("%Y-%m-%d")
        
        if user['last_daily_bonus'] == today:
            return 0 # تم المطالبة بها اليوم

        try:
            # 1. إضافة النقاط
            await self.add_points(user_id, self.daily_bonus_points, "مكافأة يومية")
            
            # 2. تحديث تاريخ المطالبة
            await self.db.execute(
                "UPDATE users SET last_daily_bonus = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id)
            )
            
            logger.info(f"User {user_id} claimed daily bonus of {self.daily_bonus_points} points.")
            return self.daily_bonus_points
        except Exception as e:
            logger.error(f"Failed to claim daily bonus for user {user_id}: {e}")
            return None

    async def reward_inviter(self, inviter_id: int, invited_user_id: int) -> bool:
        """
        مكافأة المستخدم الداعي عند انضمام مستخدم جديد.

        :param inviter_id: معرف المستخدم الداعي.
        :param invited_user_id: معرف المستخدم المدعو.
        :return: True عند النجاح.
        """
        await self._get_points_config()
        
        # التأكد من أن المستخدم الداعي موجود ولم يتم حظره
        inviter = await self.db.get_user(inviter_id)
        if not inviter or inviter['banned'] == 1:
            return False

        reason = f"مكافأة دعوة مستخدم جديد: {invited_user_id}"
        return await self.add_points(inviter_id, self.invite_points, reason, invited_user_id)

    async def reward_for_proof(self, user_id: int) -> bool:
        """
        مكافأة المستخدم عند تقديم إثبات استخدام ناجح.

        :param user_id: معرف المستخدم.
        :return: True عند النجاح.
        """
        await self._get_points_config()
        reason = "مكافأة تقديم إثبات استخدام ناجح"
        return await self.add_points(user_id, self.proof_points, reason)

    # --- سجل النقاط ---

    async def get_points_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        جلب سجل النقاط للمستخدم.

        :param user_id: معرف المستخدم.
        :param limit: عدد السجلات المراد جلبها.
        :return: قائمة بسجلات النقاط.
        """
        return await self.db.get_points_history(user_id, limit)

    # --- تحويل النقاط ---

    async def transfer_points(self, sender_id: int, receiver_id: int, points: int) -> str:
        """
        تحويل النقاط بين مستخدمين.

        :param sender_id: معرف المستخدم المرسل.
        :param receiver_id: معرف المستخدم المستقبل.
        :param points: عدد النقاط المراد تحويلها.
        :return: رسالة حالة (success, insufficient_points, receiver_not_found, self_transfer, invalid_amount, error).
        """
        if sender_id == receiver_id:
            return "self_transfer"
        
        if points <= 0:
            return "invalid_amount"

        sender = await self.db.get_user(sender_id)
        receiver = await self.db.get_user(receiver_id)

        if not sender or sender['banned'] == 1:
            return "sender_not_found"
        
        if not receiver or receiver['banned'] == 1:
            return "receiver_not_found"

        if sender['points'] < points:
            return "insufficient_points"

        try:
            # 1. خصم النقاط من المرسل
            await self.subtract_points(
                sender_id, 
                points, 
                f"تحويل إلى المستخدم {receiver_id}", 
                receiver_id
            )

            # 2. إضافة النقاط إلى المستقبل
            await self.add_points(
                receiver_id, 
                points, 
                f"استلام من المستخدم {sender_id}", 
                sender_id
            )
            
            logger.info(f"Points transfer: {sender_id} -> {receiver_id} ({points} points)")
            return "success"
        except Exception as e:
            logger.error(f"Points transfer failed: {e}")
            return "error"

    # --- لوحة تحكم الأدمن ---

    async def admin_add_points(self, admin_id: int, user_id: int, points: int, reason: str) -> bool:
        """
        إضافة نقاط للمستخدم من قبل المدير.

        :param admin_id: معرف المدير.
        :param user_id: معرف المستخدم.
        :param points: عدد النقاط.
        :param reason: سبب الإضافة.
        :return: True عند النجاح.
        """
        user = await self.db.get_user(user_id)
        if not user:
            return False

        reason_log = f"إضافة بواسطة المدير {admin_id}: {reason}"
        success = await self.add_points(user_id, points, reason_log, admin_id)
        if success:
            await self.db.log_action(admin_id, "ADMIN_ADD_POINTS", f"User: {user_id}, Points: {points}, Reason: {reason}")
        return success

    async def admin_subtract_points(self, admin_id: int, user_id: int, points: int, reason: str) -> bool:
        """
        خصم نقاط من المستخدم من قبل المدير.

        :param admin_id: معرف المدير.
        :param user_id: معرف المستخدم.
        :param points: عدد النقاط.
        :param reason: سبب الخصم.
        :return: True عند النجاح.
        """
        user = await self.db.get_user(user_id)
        if not user:
            return False

        reason_log = f"خصم بواسطة المدير {admin_id}: {reason}"
        
        # لا نستخدم دالة subtract_points العادية لأن المدير يمكنه الخصم حتى لو كان الرصيد غير كافٍ (ليصبح بالسالب)
        try:
            await self.db.update_user_points(user_id, -points, reason_log, admin_id)
            await self.db.log_action(admin_id, "ADMIN_SUBTRACT_POINTS", f"User: {user_id}, Points: {points}, Reason: {reason}")
            return True
        except Exception as e:
            logger.error(f"Admin {admin_id} failed to subtract points from user {user_id}: {e}")
            return False
        
    async def get_top_users(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        جلب قائمة بأعلى المستخدمين من حيث النقاط.
        
        :param limit: عدد المستخدمين المراد جلبهم.
        :return: قائمة من القواميس ببيانات المستخدمين.
        """
        sql = """
            SELECT id, username, points, total_invites
            FROM users
            ORDER BY points DESC
            LIMIT ?
        """
        return await self.db.fetchall(sql, (limit,))

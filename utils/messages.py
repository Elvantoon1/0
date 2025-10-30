from typing import Dict, Any, List
from datetime import datetime

# --- رسائل عامة ---

MSG_WELCOME = "مرحباً بك في بوت الأرقام المجانية الاحترافي! 🤖\n\nاستخدم الأزرار أدناه للتنقل بين ميزات البوت."
MSG_MAIN_MENU = "أهلاً بك في القائمة الرئيسية. اختر ما تريد: 👇"
MSG_ADMIN_MENU = "أهلاً بك يا مدير! 👑\nهنا لوحة التحكم الخاصة بك. اختر الإجراء المطلوب:"
MSG_INVALID_COMMAND = "أمر غير صالح. يرجى استخدام الأزرار أو الأوامر المتاحة."
MSG_ACCESS_DENIED = "عذراً، هذه الميزة متاحة فقط للمدير أو لمستخدمي PRO."
MSG_CHANNEL_REQUIRED = "يجب عليك الاشتراك في القنوات التالية للمتابعة:\n{channels_list}\n\nبعد الاشتراك، اضغط /start مرة أخرى."
MSG_ERROR = "حدث خطأ غير متوقع. يرجى المحاولة لاحقاً."

# --- رسائل PRO ---

def get_pro_status_message(user: Dict[str, Any]) -> str:
    """رسالة حالة اشتراك PRO."""
    if user['is_pro'] == 1:
        expiry = datetime.strptime(user['pro_expiry'], "%Y-%m-%d %H:%M:%S")
        remaining = expiry - datetime.now()
        
        return (
            "✅ **حالة حسابك: PRO مفعل**\n\n"
            f"🌟 **تاريخ الانتهاء:** {expiry.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"⏳ **المتبقي:** {remaining.days} يوماً و {remaining.seconds // 3600} ساعة.\n\n"
            "استمتع بالميزات الحصرية!"
        )
    else:
        return (
            "❌ **حالة حسابك: مستخدم عادي**\n\n"
            "للحصول على سرعة معالجة أعلى، أولوية في الأرقام، وميزات أخرى، اشترك في PRO الآن!"
        )

def get_pro_price_message(cost: int, duration: int) -> str:
    """رسالة سعر اشتراك PRO."""
    return (
        "💰 **شراء اشتراك PRO**\n\n"
        f"مدة الاشتراك: **{duration} يوماً**\n"
        f"التكلفة: **{cost} نقطة**\n\n"
        "هل أنت متأكد من الشراء؟ سيتم خصم النقاط من رصيدك."
    )

MSG_PRO_BUY_SUCCESS = "🎉 تم شراء اشتراك PRO بنجاح! تم تفعيله لمدة {duration} يوماً. استمتع بالمزايا!"
MSG_PRO_BUY_FAILED_POINTS = "❌ فشل الشراء. رصيدك الحالي ({current_points} نقطة) غير كافٍ. تحتاج إلى {required_points} نقطة."
MSG_PRO_BUY_FAILED_GENERAL = "❌ فشل الشراء. حدث خطأ أثناء تفعيل الاشتراك."
MSG_PRO_ENTER_CODE = "🔑 يرجى إدخال كود PRO الذي لديك الآن:"
MSG_PRO_CODE_SUCCESS = "🎉 تم تفعيل اشتراك PRO بنجاح باستخدام الكود! تم تفعيله لمدة {duration} يوماً."
MSG_PRO_CODE_INVALID = "❌ كود PRO غير صالح، أو مستخدم مسبقاً، أو منتهي الصلاحية."

# --- رسائل النقاط ---

def get_user_profile_message(user: Dict[str, Any]) -> str:
    """رسالة ملف المستخدم الشخصي."""
    return (
        "👤 **ملفك الشخصي**\n\n"
        f"🆔 **معرف المستخدم:** `{user['id']}`\n"
        f"🌟 **النقاط الحالية:** **{user['points']}** نقطة\n"
        f"👑 **حالة الحساب:** {'⭐ PRO' if user['is_pro'] == 1 else '👤 عادي'}\n"
        f"💌 **إجمالي الدعوات:** {user['total_invites']}\n"
        f"✅ **إثباتات مقبولة:** {user['proofs_submitted']}\n"
        f"🗓️ **تاريخ الانضمام:** {user['joined_at'].split(' ')[0]}"
    )

def get_daily_bonus_message(points: int) -> str:
    """رسالة المكافأة اليومية."""
    if points > 0:
        return f"🎁 تهانينا! لقد حصلت على **{points}** نقطة كمكافأة يومية. يمكنك المطالبة بها مرة أخرى غداً."
    elif points == 0:
        return "⏳ لقد طالبت بالمكافأة اليومية بالفعل. عد إلينا غداً!"
    else:
        return MSG_ERROR

MSG_POINTS_ENTER_TRANSFER_AMOUNT = "💸 يرجى إدخال عدد النقاط التي تريد تحويلها:"
MSG_POINTS_ENTER_RECEIVER_ID = "👤 يرجى إدخال معرف المستخدم (ID) الذي تريد تحويل النقاط إليه:"
MSG_POINTS_TRANSFER_SUCCESS = "✅ تم تحويل **{points}** نقطة بنجاح إلى المستخدم `{receiver_id}`."
MSG_POINTS_TRANSFER_FAILED_INSUFFICIENT = "❌ فشل التحويل. رصيدك غير كافٍ."
MSG_POINTS_TRANSFER_FAILED_RECEIVER = "❌ فشل التحويل. لم يتم العثور على المستخدم المستقبِل أو أنه محظور."
MSG_POINTS_TRANSFER_FAILED_SELF = "❌ لا يمكنك تحويل النقاط إلى نفسك."
MSG_POINTS_TRANSFER_FAILED_INVALID_AMOUNT = "❌ يرجى إدخال عدد صحيح موجب للنقاط."
MSG_POINTS_HISTORY_HEADER = "📜 **سجل النقاط الأخير** (آخر {limit} عملية):\n"
MSG_POINTS_HISTORY_ITEM = "• **{change:+d}** نقطة ({reason}) في {date}"
MSG_POINTS_HISTORY_EMPTY = "لا يوجد سجل نقاط حتى الآن."

# --- رسائل الإعلانات ---

def get_ad_message(ad: Dict[str, Any]) -> str:
    """رسالة عرض الإعلان للمستخدم."""
    return (
        "📢 **إعلان مدفوع**\n\n"
        f"**المكافأة:** **{ad['reward_points']}** نقطة\n\n"
        f"**المحتوى:**\n{ad['content']}\n\n"
        "يرجى الضغط على زر **تأكيد المشاهدة** للحصول على النقاط."
    )

MSG_AD_REWARD_SUCCESS = "🎉 شكراً لك على المشاهدة! تم إضافة **{points}** نقطة إلى رصيدك."
MSG_AD_REWARD_ALREADY_VIEWED = "👀 لقد شاهدت هذا الإعلان بالفعل وحصلت على مكافأتك."
MSG_AD_NO_ADS = "لا توجد إعلانات متاحة للمشاهدة حالياً. يرجى المحاولة لاحقاً."

# --- رسائل المدير ---

MSG_ADMIN_SETUP_WELCOME = "مرحباً بك في إعداد البوت الأولي! 🛠️\n\nلضمان عمل البوت بكفاءة، يرجى ضبط الإعدادات الأساسية."
MSG_ADMIN_SETUP_CHANNELS = "🔗 **الخطوة 1: القنوات الإلزامية**\n\nيرجى إرسال معرف (ID) أو اسم المستخدم (@username) للقناة الإلزامية الأولى. (أرسل /skip للتخطي)."
MSG_ADMIN_SETUP_POINTS = "💰 **الخطوة 2: إعدادات النقاط الافتراضية**\n\nيرجى إرسال النقاط الافتراضية للمكافأة اليومية (القيمة الحالية: {current_value})."
MSG_ADMIN_SETUP_COMPLETE = "✅ اكتمل الإعداد الأولي بنجاح! يمكنك الآن استخدام لوحة تحكم المدير ⚙️."
MSG_ADMIN_ENTER_USER_ID = "👤 يرجى إدخال معرف المستخدم (ID) المطلوب:"
MSG_ADMIN_ENTER_POINTS = "💰 يرجى إدخال عدد النقاط (قيمة موجبة للإضافة، أو سالبة للخصم):"
MSG_ADMIN_ENTER_REASON = "📝 يرجى إدخال سبب الإجراء (للتوثيق):"
MSG_ADMIN_POINTS_ADDED = "✅ تم إضافة {points} نقطة بنجاح للمستخدم `{user_id}`."
MSG_ADMIN_POINTS_SUBTRACTED = "✅ تم خصم {points} نقطة بنجاح من المستخدم `{user_id}`."
MSG_ADMIN_USER_NOT_FOUND = "❌ لم يتم العثور على المستخدم بالمعرف المدخل."
MSG_ADMIN_INVALID_INPUT = "❌ إدخال غير صالح. يرجى التأكد من إدخال رقم صحيح."

# --- رسائل الأرقام ---

MSG_NUMBERS_MENU = "🌍 **قائمة الأرقام المجانية**\n\nاختر الدولة التي تريد الحصول على رقم منها:"
MSG_NUMBERS_SELECT_COUNTRY = "يرجى اختيار الدولة:"
MSG_NUMBERS_NO_NUMBERS = "عذراً، لا توجد أرقام متاحة لهذه الدولة حالياً."

MSG_NUMBER_REQUEST_INITIATED = (
    "⏳ **جاري حجز الرقم**\n\n"
    "**الرقم:** `{number}`\n"
    "**المنصة:** {platform}\n\n"
    "تم حجز الرقم بنجاح. يرجى استخدام الرقم في التطبيق المطلوب (مثل Telegram أو WhatsApp) والضغط على زر **التحقق من وصول الكود**.\n\n"
    "**ملاحظة:** سينتهي الحجز في {expiry}."
)

MSG_NUMBER_REQUEST_CHECK = "🔄 جاري التحقق من وصول كود التفعيل..."

MSG_NUMBER_CODE_RECEIVED = (
    "🎉 **وصل الكود بنجاح!**\n\n"
    "**كود التفعيل هو:** `{code}`\n\n"
    "يرجى استخدامه فوراً في التطبيق. شكراً لاستخدامك البوت!"
)

MSG_NUMBER_REQUEST_EXPIRED = (
    "❌ **انتهت صلاحية الحجز**\n\n"
    "للأسف، انتهت صلاحية حجز الرقم. يرجى المحاولة مرة أخرى باختيار رقم آخر."
)

MSG_NUMBER_REQUEST_NOT_READY = "⏳ لم يصل الكود بعد. يرجى المحاولة مرة أخرى بعد قليل."

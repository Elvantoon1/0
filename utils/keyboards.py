from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# --- لوحات مفاتيح الرد (Reply Keyboards) ---

def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """لوحة المفاتيح الرئيسية للمستخدم العادي والمدير."""
    builder = ReplyKeyboardBuilder()
    
    # صف المستخدمين
    builder.row(
        KeyboardButton(text="🌍 أرقام مجانية"),
        KeyboardButton(text="💰 كسب النقاط")
    )
    builder.row(
        KeyboardButton(text="⭐ حسابي PRO"),
        KeyboardButton(text="👤 ملفي الشخصي")
    )
    
    # صف المدير
    if is_admin:
        builder.row(KeyboardButton(text="⚙️ لوحة تحكم المدير"))
        
    return builder.as_markup(resize_keyboard=True)

# --- لوحات مفاتيح السطر (Inline Keyboards) ---

def points_earning_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح طرق كسب النقاط."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎁 مكافأة يومية", callback_data="points_daily_bonus"),
        InlineKeyboardButton(text="📢 مشاهدة إعلانات", callback_data="ads_view")
    )
    builder.row(
        InlineKeyboardButton(text="💌 دعوة صديق", callback_data="points_invite"),
        InlineKeyboardButton(text="💸 تحويل نقاط", callback_data="points_transfer")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="main_menu"))
    return builder.as_markup()

def pro_menu_keyboard(is_pro: bool = False) -> InlineKeyboardMarkup:
    """لوحة مفاتيح نظام PRO."""
    builder = InlineKeyboardBuilder()
    if not is_pro:
        builder.row(InlineKeyboardButton(text="⭐ شراء اشتراك PRO (نقاط)", callback_data="pro_buy_points"))
        builder.row(InlineKeyboardButton(text="🔑 تفعيل بكود PRO", callback_data="pro_activate_code"))
    else:
        builder.row(InlineKeyboardButton(text="✅ حالة الاشتراك", callback_data="pro_status"))
        builder.row(InlineKeyboardButton(text="💡 مزايا PRO", callback_data="pro_features"))
    
    builder.row(InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="main_menu"))
    return builder.as_markup()

def admin_main_menu_keyboard() -> InlineKeyboardMarkup:
    """لوحة مفاتيح المدير الرئيسية."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💰 إدارة النقاط", callback_data="admin_points_menu"),
        InlineKeyboardButton(text="⭐ إدارة PRO", callback_data="admin_pro_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📢 إدارة الإعلانات", callback_data="admin_ads_menu"),
        InlineKeyboardButton(text="⚙️ الإعدادات العامة", callback_data="admin_settings_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📊 إحصائيات البوت", callback_data="admin_stats"),
        InlineKeyboardButton(text="🚫 حظر/إلغاء حظر", callback_data="admin_ban_menu")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="main_menu"))
    return builder.as_markup()

def admin_points_menu() -> InlineKeyboardMarkup:
    """لوحة مفاتيح إدارة النقاط للمدير."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ إضافة نقاط", callback_data="admin_points_add"),
        InlineKeyboardButton(text="➖ خصم نقاط", callback_data="admin_points_subtract")
    )
    builder.row(
        InlineKeyboardButton(text="🏆 قائمة المتصدرين", callback_data="admin_points_top"),
        InlineKeyboardButton(text="📜 سجل النقاط", callback_data="admin_points_history")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع لقائمة المدير", callback_data="admin_main_menu"))
    return builder.as_markup()

def admin_ads_menu() -> InlineKeyboardMarkup:
    """لوحة مفاتيح إدارة الإعلانات للمدير."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ إضافة إعلان جديد", callback_data="admin_ads_add"),
        InlineKeyboardButton(text="📝 عرض/تعديل الإعلانات", callback_data="admin_ads_list")
    )
    builder.row(
        InlineKeyboardButton(text="📊 إحصائيات الإعلانات", callback_data="admin_ads_stats"),
        InlineKeyboardButton(text="🗑️ حذف إعلان", callback_data="admin_ads_delete")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع لقائمة المدير", callback_data="admin_main_menu"))
    return builder.as_markup()

def admin_settings_menu() -> InlineKeyboardMarkup:
    """لوحة مفاتيح إدارة الإعدادات العامة للمدير."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👋 رسالة الترحيب", callback_data="admin_settings_welcome"),
        InlineKeyboardButton(text="🔗 القنوات الإلزامية", callback_data="admin_settings_channels")
    )
    builder.row(
        InlineKeyboardButton(text="💰 إعدادات النقاط", callback_data="admin_settings_points"),
        InlineKeyboardButton(text="⭐ إعدادات PRO", callback_data="admin_settings_pro")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع لقائمة المدير", callback_data="admin_main_menu"))
    return builder.as_markup()

def confirm_ad_view_keyboard(ad_id: int) -> InlineKeyboardMarkup:
    """لوحة مفاتيح لتأكيد مشاهدة الإعلان."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ تأكيد المشاهدة والحصول على النقاط", callback_data=f"ads_confirm:{ad_id}")
    )
    builder.row(InlineKeyboardButton(text="❌ إلغاء", callback_data="main_menu"))
    return builder.as_markup()

def back_to_menu_keyboard(menu_callback: str = "main_menu") -> InlineKeyboardMarkup:
    """لوحة مفاتيح للرجوع إلى قائمة محددة."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data=menu_callback))
    return builder.as_markup()

def pagination_keyboard(current_page: int, total_pages: int, prefix: str) -> InlineKeyboardMarkup:
    """لوحة مفاتيح للتنقل بين الصفحات."""
    builder = InlineKeyboardBuilder()
    
    if current_page > 1:
        builder.add(InlineKeyboardButton(text="⬅️ السابق", callback_data=f"{prefix}:{current_page - 1}"))
    
    builder.add(InlineKeyboardButton(text=f"{current_page}/{total_pages}", callback_data="ignore"))
    
    if current_page < total_pages:
        builder.add(InlineKeyboardButton(text="التالي ➡️", callback_data=f"{prefix}:{current_page + 1}"))
        
    builder.row(InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_main_menu"))
    return builder.as_markup()

def admin_pro_menu() -> InlineKeyboardMarkup:
    """لوحة مفاتيح إدارة PRO للمدير."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ إنشاء كود PRO", callback_data="admin_pro_create_code"),
        InlineKeyboardButton(text="🔑 عرض الأكواد", callback_data="admin_pro_list_codes")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ قائمة المشتركين", callback_data="admin_pro_list_users"),
        InlineKeyboardButton(text="✍️ تمديد/إلغاء", callback_data="admin_pro_manage_user")
    )
    builder.row(InlineKeyboardButton(text="🔙 رجوع لقائمة المدير", callback_data="admin_main_menu"))
    return builder.as_markup()

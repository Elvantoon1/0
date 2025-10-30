from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from loguru import logger
from typing import Dict, Any

from database import Database
from services.points_manager import PointsManager
from services.pro_manager import ProManager
from services.setup_manager import SetupManager
from services.ads_manager import AdsManager
from services.number_manager import NumberManager
from config import Config
from utils.keyboards import (
    admin_main_menu_keyboard, admin_points_menu, admin_ads_menu,
    admin_settings_menu, back_to_menu_keyboard, admin_pro_menu,
    admin_numbers_menu, pagination_keyboard
)
from utils.messages import (
    MSG_ADMIN_MENU, MSG_ACCESS_DENIED, MSG_ADMIN_ENTER_USER_ID,
    MSG_ADMIN_INVALID_INPUT, MSG_ADMIN_USER_NOT_FOUND, MSG_ADMIN_ENTER_POINTS,
    MSG_ADMIN_ENTER_REASON, MSG_ADMIN_POINTS_ADDED, MSG_ADMIN_POINTS_SUBTRACTED,
    MSG_ADMIN_SETUP_WELCOME, MSG_ADMIN_SETUP_CHANNELS, MSG_ADMIN_SETUP_POINTS,
    MSG_ADMIN_SETUP_COMPLETE, MSG_ERROR
)
from utils.utils import safe_send_message, safe_edit_message_text

# --- FSM States ---
from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    """حالات FSM للمدير."""
    waiting_for_user_id = State()
    waiting_for_points_amount = State()
    waiting_for_points_reason = State()
    
    # Setup States
    setup_waiting_for_channel = State()
    setup_waiting_for_points_config = State()
    
    # PRO States
    waiting_for_pro_code_duration = State()
    
    # Ads States
    waiting_for_ad_type = State()
    waiting_for_ad_content = State()
    waiting_for_ad_reward = State()

    # Numbers States
    waiting_for_country_name = State()
    waiting_for_country_flag = State()
    waiting_for_number_country_id = State()
    waiting_for_number_details = State()
    
# --- Router Setup ---
router = Router()

# --- Dependency Injection ---
DB: Database
PM: PointsManager
PRM: ProManager
SM: SetupManager
ADM: AdsManager
NM: NumberManager

def is_admin(user_id: int) -> bool:
    """التحقق مما إذا كان المستخدم مديراً."""
    return user_id == Config.ADMIN_ID

@router.message(Command("admin"))
async def command_admin_handler(message: types.Message, state: FSMContext, bot):
    """معالج أمر /admin."""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await safe_send_message(bot, user_id, MSG_ACCESS_DENIED)
        return

    await state.clear()
    
    # 1. التحقق من الإعداد الأولي
    if not await SM.is_setup_complete():
        await safe_send_message(bot, user_id, MSG_ADMIN_SETUP_WELCOME)
        await state.set_state(AdminStates.setup_waiting_for_channel)
        await safe_send_message(bot, user_id, MSG_ADMIN_SETUP_CHANNELS)
        return

    # 2. عرض القائمة الرئيسية للمدير
    await safe_send_message(
        bot,
        user_id,
        MSG_ADMIN_MENU,
        reply_markup=admin_main_menu_keyboard()
    )

@router.message(F.text == "⚙️ لوحة تحكم المدير")
async def admin_menu_reply_handler(message: types.Message, state: FSMContext, bot):
    """معالج زر لوحة تحكم المدير."""
    await command_admin_handler(message, state, bot)

# --- معالجات الإعداد الأولي (Setup) ---

@router.message(AdminStates.setup_waiting_for_channel)
async def setup_channel_handler(message: types.Message, state: FSMContext, bot):
    """استلام معرف القناة الإلزامية."""
    user_id = message.from_user.id
    channel_id = message.text.strip()
    
    if channel_id.lower() == "/skip":
        await state.set_state(AdminStates.setup_waiting_for_points_config)
        await safe_send_message(
            bot,
            user_id,
            MSG_ADMIN_SETUP_POINTS.format(current_value=Config.DEFAULT_SETTINGS['daily_bonus_points'])
        )
        return
        
    try:
        # محاولة جلب معلومات القناة للتحقق
        chat = await bot.get_chat(channel_id)
        if chat.type not in ['channel', 'supergroup']:
            await safe_send_message(bot, user_id, "❌ الإدخال ليس قناة أو مجموعة. يرجى إدخال @username أو ID.")
            return
            
        await SM.add_mandatory_channel(user_id, channel_id, is_group=(chat.type == 'supergroup'))
        
        # الانتقال للخطوة التالية
        await state.set_state(AdminStates.setup_waiting_for_points_config)
        await safe_send_message(
            bot,
            user_id,
            MSG_ADMIN_SETUP_POINTS.format(current_value=Config.DEFAULT_SETTINGS['daily_bonus_points'])
        )
    except Exception as e:
        logger.error(f"Setup error getting chat info: {e}")
        await safe_send_message(bot, user_id, "❌ فشل التحقق من القناة. تأكد من أن البوت مدير فيها. يرجى المحاولة مرة أخرى.")

@router.message(AdminStates.setup_waiting_for_points_config)
async def setup_points_handler(message: types.Message, state: FSMContext, bot):
    """استلام إعدادات النقاط الافتراضية."""
    user_id = message.from_user.id
    
    try:
        points = int(message.text.strip())
        if points <= 0:
            raise ValueError
    except ValueError:
        await safe_send_message(bot, user_id, MSG_ADMIN_INVALID_INPUT)
        return

    await SM.update_setting(user_id, "daily_bonus_points", str(points))
    await SM.mark_setup_complete()
    await state.clear()
    
    await safe_send_message(
        bot,
        user_id,
        MSG_ADMIN_SETUP_COMPLETE,
        reply_markup=admin_main_menu_keyboard()
    )

# --- معالجات إدارة النقاط ---

@router.callback_query(F.data == "admin_points_menu")
async def admin_points_menu_handler(callback: types.CallbackQuery, bot):
    """عرض قائمة إدارة النقاط."""
    if not is_admin(callback.from_user.id): return
    await safe_edit_message_text(callback.message, "إدارة النقاط:", reply_markup=admin_points_menu())
    await callback.answer()

@router.callback_query(F.data.in_({"admin_points_add", "admin_points_subtract"}))
async def admin_points_action_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """بدء عملية إضافة/خصم النقاط: طلب معرف المستخدم."""
    if not is_admin(callback.from_user.id): return
    
    action = callback.data.split("_")[-1] # add or subtract
    await state.update_data(points_action=action)
    await state.set_state(AdminStates.waiting_for_user_id)
    
    await safe_edit_message_text(
        callback.message,
        MSG_ADMIN_ENTER_USER_ID,
        reply_markup=back_to_menu_keyboard("admin_points_menu")
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_user_id)
async def admin_points_get_user_id(message: types.Message, state: FSMContext, bot):
    """استلام معرف المستخدم: طلب المبلغ."""
    user_id = message.from_user.id
    
    try:
        target_user_id = int(message.text.strip())
    except ValueError:
        await safe_send_message(bot, user_id, MSG_ADMIN_INVALID_INPUT)
        return
        
    target_user = await DB.get_user(target_user_id)
    if not target_user:
        await safe_send_message(bot, user_id, MSG_ADMIN_USER_NOT_FOUND)
        return

    await state.update_data(target_user_id=target_user_id)
    await state.set_state(AdminStates.waiting_for_points_amount)
    
    await safe_send_message(
        bot,
        user_id,
        f"{MSG_ADMIN_ENTER_POINTS}\n\nالمستخدم المستهدف: `{target_user_id}`",
        reply_markup=back_to_menu_keyboard("admin_points_menu")
    )

@router.message(AdminStates.waiting_for_points_amount)
async def admin_points_get_amount(message: types.Message, state: FSMContext, bot):
    """استلام المبلغ: طلب السبب."""
    user_id = message.from_user.id
    
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await safe_send_message(bot, user_id, MSG_ADMIN_INVALID_INPUT)
        return
        
    await state.update_data(points_amount=amount)
    await state.set_state(AdminStates.waiting_for_points_reason)
    
    await safe_send_message(
        bot,
        user_id,
        MSG_ADMIN_ENTER_REASON,
        reply_markup=back_to_menu_keyboard("admin_points_menu")
    )

@router.message(AdminStates.waiting_for_points_reason)
async def admin_points_execute(message: types.Message, state: FSMContext, bot):
    """تنفيذ عملية إضافة/خصم النقاط."""
    admin_id = message.from_user.id
    reason = message.text.strip()
    
    data = await state.get_data()
    action = data.get('points_action')
    target_user_id = data.get('target_user_id')
    amount = data.get('points_amount')
    
    await state.clear()
    
    if action == "add":
        success = await PM.admin_add_points(admin_id, target_user_id, amount, reason)
        msg = MSG_ADMIN_POINTS_ADDED.format(points=amount, user_id=target_user_id)
    elif action == "subtract":
        success = await PM.admin_subtract_points(admin_id, target_user_id, amount, reason)
        msg = MSG_ADMIN_POINTS_SUBTRACTED.format(points=amount, user_id=target_user_id)
    else:
        success = False
        msg = MSG_ERROR

    if success:
        await safe_send_message(bot, admin_id, msg, reply_markup=admin_main_menu_keyboard())
    else:
        await safe_send_message(bot, admin_id, MSG_ERROR, reply_markup=admin_main_menu_keyboard())

# --- معالجات إدارة PRO ---

@router.callback_query(F.data == "admin_pro_menu")
async def admin_pro_menu_handler(callback: types.CallbackQuery, bot):
    """عرض قائمة إدارة PRO."""
    if not is_admin(callback.from_user.id): return
    await safe_edit_message_text(callback.message, "إدارة PRO:", reply_markup=admin_pro_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_pro_create_code")
async def admin_pro_create_code_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """بدء إنشاء كود PRO: طلب المدة."""
    if not is_admin(callback.from_user.id): return
    
    await state.set_state(AdminStates.waiting_for_pro_code_duration)
    
    await safe_edit_message_text(
        callback.message,
        "🔑 يرجى إدخال مدة صلاحية كود PRO بالأيام (مثال: 30):",
        reply_markup=back_to_menu_keyboard("admin_pro_menu")
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_pro_code_duration)
async def admin_pro_create_code_execute(message: types.Message, state: FSMContext, bot):
    """تنفيذ إنشاء كود PRO."""
    admin_id = message.from_user.id
    
    try:
        duration = int(message.text.strip())
        if duration <= 0:
            raise ValueError
    except ValueError:
        await safe_send_message(bot, admin_id, MSG_ADMIN_INVALID_INPUT)
        return
        
    await state.clear()
    
    code = await PRM.create_pro_code(admin_id, duration)
    
    if code:
        msg = f"✅ تم إنشاء كود PRO بنجاح:\n\n**الكود:** `{code}`\n**المدة:** {duration} يوماً"
        await safe_send_message(bot, admin_id, msg, reply_markup=admin_main_menu_keyboard())
    else:
        await safe_send_message(bot, admin_id, MSG_ERROR, reply_markup=admin_main_menu_keyboard())

# --- معالجات إدارة الإعلانات ---

@router.callback_query(F.data == "admin_ads_menu")
async def admin_ads_menu_handler(callback: types.CallbackQuery, bot):
    """عرض قائمة إدارة الإعلانات."""
    if not is_admin(callback.from_user.id): return
    await safe_edit_message_text(callback.message, "إدارة الإعلانات:", reply_markup=admin_ads_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_ads_add")
async def admin_ads_add_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """بدء إضافة إعلان جديد: طلب النوع."""
    if not is_admin(callback.from_user.id): return
    
    await state.set_state(AdminStates.waiting_for_ad_type)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="نصي (Text)", callback_data="ad_type:text"),
            types.InlineKeyboardButton(text="صورة (Photo)", callback_data="ad_type:photo")
        ],
        [
            types.InlineKeyboardButton(text="فيديو (Video)", callback_data="ad_type:video"),
            types.InlineKeyboardButton(text="رابط (Link)", callback_data="ad_type:link")
        ],
        [types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_ads_menu")]
    ])
    
    await safe_edit_message_text(
        callback.message,
        "📢 يرجى اختيار نوع الإعلان:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("ad_type:"))
async def admin_ads_get_type(callback: types.CallbackQuery, state: FSMContext, bot):
    """استلام نوع الإعلان: طلب المحتوى."""
    if not is_admin(callback.from_user.id): return
    
    ad_type = callback.data.split(":")[1]
    await state.update_data(ad_type=ad_type)
    await state.set_state(AdminStates.waiting_for_ad_content)
    
    await safe_edit_message_text(
        callback.message,
        f"📝 تم اختيار النوع: **{ad_type}**.\n\nيرجى إرسال محتوى الإعلان (النص، أو الصورة/الفيديو مع الشرح، أو الرابط):",
        reply_markup=back_to_menu_keyboard("admin_ads_menu")
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_ad_content)
async def admin_ads_get_content(message: types.Message, state: FSMContext, bot):
    """استلام محتوى الإعلان: طلب المكافأة."""
    admin_id = message.from_user.id
    
    data = await state.get_data()
    ad_type = data.get('ad_type')
    content = message.text
    media_file_id = None
    
    if ad_type == "photo" and message.photo:
        media_file_id = message.photo[-1].file_id
        content = message.caption or "إعلان بالصورة"
    elif ad_type == "video" and message.video:
        media_file_id = message.video.file_id
        content = message.caption or "إعلان بالفيديو"
    elif not content:
        await safe_send_message(bot, admin_id, "❌ لم يتم إرسال محتوى صالح. يرجى المحاولة مرة أخرى.")
        return

    await state.update_data(ad_content=content, media_file_id=media_file_id)
    await state.set_state(AdminStates.waiting_for_ad_reward)
    
    await safe_send_message(
        bot,
        admin_id,
        "💰 يرجى إدخال عدد النقاط التي سيحصل عليها المستخدم مقابل مشاهدة هذا الإعلان:",
        reply_markup=back_to_menu_keyboard("admin_ads_menu")
    )

@router.message(AdminStates.waiting_for_ad_reward)
async def admin_ads_execute(message: types.Message, state: FSMContext, bot):
    """تنفيذ إنشاء الإعلان."""
    admin_id = message.from_user.id
    
    try:
        reward = int(message.text.strip())
        if reward <= 0:
            raise ValueError
    except ValueError:
        await safe_send_message(bot, admin_id, MSG_ADMIN_INVALID_INPUT)
        return
        
    data = await state.get_data()
    ad_type = data.get('ad_type')
    content = data.get('ad_content')
    media_file_id = data.get('media_file_id')
    
    await state.clear()
    
    ad_id = await ADM.create_ad(admin_id, ad_type, content, reward, media_file_id)
    
    if ad_id:
        msg = f"✅ تم إنشاء الإعلان بنجاح! ID: `{ad_id}`"
        await safe_send_message(bot, admin_id, msg, reply_markup=admin_main_menu_keyboard())
    else:
        await safe_send_message(bot, admin_id, MSG_ERROR, reply_markup=admin_main_menu_keyboard())

# --- معالجات إدارة الأرقام والدول ---

@router.callback_query(F.data == "admin_numbers_menu")
async def admin_numbers_menu_handler(callback: types.CallbackQuery, bot):
    """عرض قائمة إدارة الأرقام والدول."""
    if not is_admin(callback.from_user.id): return
    await safe_edit_message_text(callback.message, "إدارة الأرقام والدول:", reply_markup=admin_numbers_menu())
    await callback.answer()

@router.callback_query(F.data == "admin_numbers_add_country")
async def admin_numbers_add_country_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """بدء إضافة دولة: طلب الاسم."""
    if not is_admin(callback.from_user.id): return
    
    await state.set_state(AdminStates.waiting_for_country_name)
    
    await safe_edit_message_text(
        callback.message,
        "🌍 يرجى إدخال اسم الدولة (مثال: الولايات المتحدة):",
        reply_markup=back_to_menu_keyboard("admin_numbers_menu")
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_country_name)
async def admin_numbers_get_country_name(message: types.Message, state: FSMContext, bot):
    """استلام اسم الدولة: طلب العلم."""
    admin_id = message.from_user.id
    country_name = message.text.strip()
    
    await state.update_data(country_name=country_name)
    await state.set_state(AdminStates.waiting_for_country_flag)
    
    await safe_send_message(
        bot,
        admin_id,
        "🚩 يرجى إرسال علم الدولة (إيموجي) (مثال: 🇺🇸):",
        reply_markup=back_to_menu_keyboard("admin_numbers_menu")
    )

@router.message(AdminStates.waiting_for_country_flag)
async def admin_numbers_add_country_execute(message: types.Message, state: FSMContext, bot):
    """تنفيذ إضافة الدولة."""
    admin_id = message.from_user.id
    country_flag = message.text.strip()
    
    data = await state.get_data()
    country_name = data.get('country_name')
    
    await state.clear()
    
    country_id = await NM.add_country(admin_id, country_name, country_flag)
    
    if country_id:
        msg = f"✅ تم إضافة الدولة **{country_name}** بنجاح! ID: `{country_id}`"
        await safe_send_message(bot, admin_id, msg, reply_markup=admin_main_menu_keyboard())
    else:
        await safe_send_message(bot, admin_id, MSG_ERROR, reply_markup=admin_main_menu_keyboard())

@router.callback_query(F.data == "admin_numbers_add_number")
async def admin_numbers_add_number_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """بدء إضافة رقم: عرض قائمة الدول."""
    if not is_admin(callback.from_user.id): return
    
    countries = await NM.get_countries_management_list()
    
    if not countries:
        await safe_edit_message_text(callback.message, "❌ لا توجد دول مضافة. يرجى إضافة دولة أولاً.", reply_markup=back_to_menu_keyboard("admin_numbers_menu"))
        await callback.answer()
        return
        
    builder = types.InlineKeyboardBuilder()
    for country in countries:
        builder.row(types.InlineKeyboardButton(text=f"{country['flag']} {country['name']}", callback_data=f"select_number_country:{country['id']}"))
        
    builder.row(types.InlineKeyboardButton(text="🔙 رجوع", callback_data="admin_numbers_menu"))
    
    await safe_edit_message_text(
        callback.message,
        "🔢 يرجى اختيار الدولة التي ينتمي إليها الرقم:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("select_number_country:"))
async def admin_numbers_get_number_country(callback: types.CallbackQuery, state: FSMContext, bot):
    """استلام الدولة للرقم: طلب تفاصيل الرقم."""
    if not is_admin(callback.from_user.id): return
    
    country_id = int(callback.data.split(":")[1])
    country = await NM.get_country(country_id)
    
    await state.update_data(number_country_id=country_id)
    await state.set_state(AdminStates.waiting_for_number_details)
    
    await safe_edit_message_text(
        callback.message,
        f"📝 **إضافة رقم لـ {country['flag']} {country['name']}**\n\n"
        "يرجى إرسال تفاصيل الرقم بالصيغة التالية:\n"
        "`الرقم | المنصة | مميز (نعم/لا) | نمط مميز (اختياري)`\n\n"
        "**مثال لرقم عادي:** `+15551234567 | Telegram | لا | -`\n"
        "**مثال لرقم مميز:** `+15559999999 | WhatsApp | نعم | *9999999`",
        reply_markup=back_to_menu_keyboard("admin_numbers_menu")
    )
    await callback.answer()

@router.message(AdminStates.waiting_for_number_details)
async def admin_numbers_add_number_execute(message: types.Message, state: FSMContext, bot):
    """تنفيذ إضافة الرقم."""
    admin_id = message.from_user.id
    
    try:
        details = [x.strip() for x in message.text.split('|')]
        if len(details) < 3:
            raise ValueError
            
        number = details[0]
        platform = details[1]
        is_premium = details[2].lower() == 'نعم'
        premium_pattern = details[3] if len(details) > 3 and details[3] != '-' else None
        
    except ValueError:
        await safe_send_message(bot, admin_id, "❌ صيغة الإدخال غير صحيحة. يرجى المحاولة مرة أخرى باستخدام الصيغة المطلوبة.")
        return
        
    data = await state.get_data()
    country_id = data.get('number_country_id')
    
    await state.clear()
    
    number_id = await NM.add_number(admin_id, country_id, number, platform, is_premium, premium_pattern)
    
    if number_id:
        msg = f"✅ تم إضافة الرقم **{number}** بنجاح! ID: `{number_id}`"
        await safe_send_message(bot, admin_id, msg, reply_markup=admin_main_menu_keyboard())
    else:
        await safe_send_message(bot, admin_id, MSG_ERROR, reply_markup=admin_main_menu_keyboard())

# --- معالجات الرجوع (للوحات المفاتيح السطرية) ---

@router.callback_query(F.data == "admin_main_menu")
async def back_to_admin_main_menu(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج الرجوع إلى القائمة الرئيسية للمدير."""
    if not is_admin(callback.from_user.id): return
    await state.clear()
    await safe_edit_message_text(
        callback.message,
        MSG_ADMIN_MENU,
        reply_markup=admin_main_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu_from_admin(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج الرجوع إلى القائمة الرئيسية للمستخدم من قائمة المدير."""
    if not is_admin(callback.from_user.id): return
    # سيتم معالجة هذا في user_handlers.py
    pass

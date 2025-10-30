from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from loguru import logger
from typing import Dict, Any, Optional
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import Database
from services.points_manager import PointsManager
from services.pro_manager import ProManager
from services.setup_manager import SetupManager
from services.ads_manager import AdsManager
from services.number_manager import NumberManager
from config import Config
from utils.keyboards import (
    main_menu_keyboard, points_earning_keyboard, pro_menu_keyboard, 
    confirm_ad_view_keyboard, back_to_menu_keyboard, numbers_countries_keyboard
)
from utils.messages import (
    MSG_WELCOME, MSG_MAIN_MENU, MSG_CHANNEL_REQUIRED, MSG_ERROR,
    get_user_profile_message, get_daily_bonus_message, MSG_AD_NO_ADS,
    get_ad_message, MSG_AD_REWARD_ALREADY_VIEWED, MSG_AD_REWARD_SUCCESS,
    get_pro_status_message, get_pro_price_message, MSG_PRO_BUY_FAILED_POINTS,
    MSG_PRO_BUY_SUCCESS, MSG_PRO_BUY_FAILED_GENERAL, MSG_PRO_ENTER_CODE,
    MSG_PRO_CODE_INVALID, MSG_PRO_CODE_SUCCESS, MSG_POINTS_ENTER_TRANSFER_AMOUNT,
    MSG_POINTS_TRANSFER_FAILED_INVALID_AMOUNT, MSG_POINTS_ENTER_RECEIVER_ID,
    MSG_POINTS_TRANSFER_FAILED_INSUFFICIENT, MSG_POINTS_TRANSFER_FAILED_RECEIVER,
    MSG_POINTS_TRANSFER_FAILED_SELF, MSG_POINTS_TRANSFER_SUCCESS,
    MSG_INVALID_COMMAND, MSG_NUMBERS_MENU, MSG_NUMBERS_NO_COUNTRIES
)
from utils.utils import safe_send_message, safe_edit_message_text, extract_user_data

# --- FSM States ---
from aiogram.fsm.state import State, StatesGroup

class UserStates(StatesGroup):
    """
    حالات FSM للمستخدم العادي.
    تستخدم لإدارة تدفق المحادثات المتعددة الخطوات.
    """
    waiting_for_pro_code = State()
    waiting_for_transfer_amount = State()
    waiting_for_receiver_id = State()
    waiting_for_number_request = State() # لحالة انتظار كود التفعيل

# --- Router Setup ---
router = Router()

# --- Dependency Injection ---
# سيتم تمرير هذه الكائنات عند تسجيل الـ router في main.py
DB: Database
PM: PointsManager
PRM: ProManager
SM: SetupManager
ADM: AdsManager
NM: NumberManager

async def check_mandatory_channels(bot, user_id: int) -> Optional[str]:
    """
    التحقق من اشتراك المستخدم في القنوات الإلزامية.

    :param bot: كائن البوت.
    :param user_id: معرف المستخدم.
    :return: رسالة الخطأ إذا كان هناك قنوات غير مشتركة، أو None إذا كان مشتركاً في جميعها.
    """
    channels = await SM.get_mandatory_channels()
    if not channels:
        return None
    
    unsubscribed_channels = []
    
    for channel in channels:
        channel_id = channel['channel_id']
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked', 'banned']:
                unsubscribed_channels.append(channel_id)
        except Exception as e:
            logger.error(f"Error checking channel {channel_id} for user {user_id}: {e}")
            unsubscribed_channels.append(channel_id) # افتراض الفشل يعني عدم الاشتراك
            
    if unsubscribed_channels:
        channels_list = "\n".join(unsubscribed_channels)
        return MSG_CHANNEL_REQUIRED.format(channels_list=channels_list)
    
    return None

@router.message(CommandStart())
async def command_start_handler(message: types.Message, state: FSMContext, bot):
    """
    معالج أمر /start.
    يقوم بتسجيل المستخدم، والتحقق من اشتراكه في القنوات الإلزامية، وعرض القائمة الرئيسية.
    """
    await state.clear()
    user_id, username, first_name, last_name = extract_user_data(message.from_user)
    
    # 1. تسجيل المستخدم (معالجة رابط الدعوة)
    invited_by: Optional[int] = None
    if message.text and len(message.text.split()) > 1:
        try:
            invited_by = int(message.text.split()[1])
        except ValueError:
            pass
            
    user = await DB.get_user(user_id)
    if not user:
        await DB.add_user(user_id, username, first_name, last_name, invited_by)
        if invited_by:
            await PM.reward_inviter(invited_by, user_id)
    
    # 2. التحقق من القنوات الإلزامية
    channel_check = await check_mandatory_channels(bot, user_id)
    if channel_check:
        await safe_send_message(bot, user_id, channel_check)
        return

    # 3. عرض القائمة الرئيسية
    is_pro = await PRM.is_pro(user_id)
    
    if message.text == "/start":
        await safe_send_message(bot, user_id, MSG_WELCOME)
    
    await safe_send_message(
        bot,
        user_id,
        MSG_MAIN_MENU,
        reply_markup=main_menu_keyboard(is_pro)
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext, bot):
    """
    معالج الرجوع إلى القائمة الرئيسية من لوحات المفاتيح السطرية.
    """
    await state.clear()
    user_id = callback.from_user.id
    is_pro = await PRM.is_pro(user_id)
    
    await safe_edit_message_text(
        callback.message,
        MSG_MAIN_MENU,
        reply_markup=main_menu_keyboard(is_pro)
    )
    await callback.answer()

@router.message(F.text == "👤 ملفي الشخصي")
async def profile_handler(message: types.Message, bot):
    """
    معالج عرض الملف الشخصي وحالة النقاط والـ PRO.
    """
    user_id = message.from_user.id
    user = await DB.get_user(user_id)
    is_pro = await PRM.is_pro(user_id)
    
    if not user:
        await safe_send_message(bot, user_id, MSG_ERROR)
        return

    await safe_send_message(
        bot,
        user_id,
        get_user_profile_message(user),
        reply_markup=points_earning_keyboard(is_pro)
    )

# --- نظام النقاط (كسب) ---

@router.message(F.text == "💰 كسب النقاط")
async def points_earning_menu_handler(message: types.Message, bot):
    """
    معالج قائمة كسب النقاط.
    """
    user_id = message.from_user.id
    is_pro = await PRM.is_pro(user_id)
    
    await safe_send_message(
        bot,
        user_id,
        "اختر طريقة كسب النقاط:",
        reply_markup=points_earning_keyboard(is_pro)
    )

@router.callback_query(F.data == "points_daily_bonus")
async def daily_bonus_handler(callback: types.CallbackQuery, bot):
    """
    معالج المكافأة اليومية.
    """
    user_id = callback.from_user.id
    is_pro = await PRM.is_pro(user_id)
    
    points = await PM.claim_daily_bonus(user_id)
    
    if points is None:
        await callback.answer("حدث خطأ أثناء المطالبة بالمكافأة.", show_alert=True)
    else:
        await safe_edit_message_text(
            callback.message,
            get_daily_bonus_message(points),
            reply_markup=points_earning_keyboard(is_pro)
        )
    await callback.answer()

@router.callback_query(F.data == "ads_view")
async def ads_view_handler(callback: types.CallbackQuery, bot):
    """
    معالج عرض الإعلانات.
    """
    user_id = callback.from_user.id
    
    ad = await ADM.get_random_unviewed_ad(user_id)
    
    if not ad:
        await safe_edit_message_text(
            callback.message,
            MSG_AD_NO_ADS,
            reply_markup=points_earning_keyboard(await PRM.is_pro(user_id))
        )
        await callback.answer("لا توجد إعلانات متاحة حالياً.")
        return

    # 1. إعداد الرسالة ولوحة المفاتيح
    message_text = get_ad_message(ad)
    keyboard = confirm_ad_view_keyboard(ad['id'], ad['reward_points'])
    
    # 2. إرسال الإعلان حسب نوعه
    if ad['ad_type'] == 'photo' and ad['media_file_id']:
        await bot.send_photo(user_id, ad['media_file_id'], caption=message_text, reply_markup=keyboard)
        await callback.message.delete() # حذف الرسالة القديمة
    elif ad['ad_type'] == 'video' and ad['media_file_id']:
        await bot.send_video(user_id, ad['media_file_id'], caption=message_text, reply_markup=keyboard)
        await callback.message.delete() # حذف الرسالة القديمة
    else:
        # نصي أو رابط
        await safe_edit_message_text(callback.message, message_text, reply_markup=keyboard)

    await callback.answer()

@router.callback_query(F.data.startswith("ads_confirm:"))
async def ads_confirm_handler(callback: types.CallbackQuery, bot):
    """
    معالج تأكيد مشاهدة الإعلان.
    """
    user_id = callback.from_user.id
    ad_id = int(callback.data.split(":")[1])
    is_pro = await PRM.is_pro(user_id)
    
    # 1. تسجيل المشاهدة والمكافأة
    success = await ADM.mark_ad_viewed_and_reward(user_id, ad_id)
    
    if success:
        ad = await ADM.get_ad(ad_id)
        reward = ad['reward_points']
        
        # تعديل الرسالة الحالية لإظهار النجاح والرجوع إلى قائمة الكسب
        await safe_edit_message_text(
            callback.message,
            MSG_AD_REWARD_SUCCESS.format(points=reward),
            reply_markup=points_earning_keyboard(is_pro)
        )
        await callback.answer(f"تمت إضافة {reward} نقطة بنجاح!", show_alert=True)
    else:
        await safe_edit_message_text(
            callback.message,
            MSG_AD_REWARD_ALREADY_VIEWED,
            reply_markup=points_earning_keyboard(is_pro)
        )
        await callback.answer("تمت المشاهدة مسبقاً أو حدث خطأ.", show_alert=True)

# --- نظام PRO ---

@router.message(F.text == "⭐ حسابي PRO")
async def pro_menu_handler(message: types.Message, bot):
    """
    معالج قائمة PRO: عرض حالة الاشتراك وخيارات الشراء/التفعيل.
    """
    user_id = message.from_user.id
    is_pro = await PRM.is_pro(user_id)
    
    user = await DB.get_user(user_id)
    status_msg = get_pro_status_message(user)
    
    await safe_send_message(
        bot,
        user_id,
        f"**نظام PRO**\n\n{status_msg}",
        reply_markup=pro_menu_keyboard(is_pro)
    )

@router.callback_query(F.data == "pro_menu")
async def back_to_pro_menu(callback: types.CallbackQuery, state: FSMContext, bot):
    """
    معالج الرجوع إلى قائمة PRO.
    """
    await state.clear()
    user_id = callback.from_user.id
    is_pro = await PRM.is_pro(user_id)
    
    user = await DB.get_user(user_id)
    status_msg = get_pro_status_message(user)
    
    await safe_edit_message_text(
        callback.message,
        f"**نظام PRO**\n\n{status_msg}",
        reply_markup=pro_menu_keyboard(is_pro)
    )
    await callback.answer()

@router.callback_query(F.data == "pro_buy_points")
async def pro_buy_points_confirm(callback: types.CallbackQuery, bot):
    """
    تأكيد شراء PRO بالنقاط: عرض رسالة التأكيد والسعر.
    """
    user_id = callback.from_user.id
    
    await PRM._get_pro_config()
    cost = PRM.pro_points_cost
    duration = PRM.pro_days_duration
    
    await safe_edit_message_text(
        callback.message,
        get_pro_price_message(cost, duration),
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="✅ تأكيد الشراء", callback_data="pro_buy_points_execute"),
            types.InlineKeyboardButton(text="❌ إلغاء", callback_data="pro_menu")
        ).as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "pro_buy_points_execute")
async def pro_buy_points_execute(callback: types.CallbackQuery, bot):
    """
    تنفيذ شراء PRO بالنقاط.
    """
    user_id = callback.from_user.id
    
    await PRM._get_pro_config()
    cost = PRM.pro_points_cost
    duration = PRM.pro_days_duration
    
    user = await DB.get_user(user_id)
    is_pro = await PRM.is_pro(user_id)
    
    if user['points'] < cost:
        await safe_edit_message_text(
            callback.message,
            MSG_PRO_BUY_FAILED_POINTS.format(current_points=user['points'], required_points=cost),
            reply_markup=pro_menu_keyboard(is_pro)
        )
        await callback.answer("نقاط غير كافية.", show_alert=True)
        return

    success = await PRM.buy_pro_with_points(user_id, PM)
    
    if success:
        await safe_edit_message_text(
            callback.message,
            MSG_PRO_BUY_SUCCESS.format(duration=duration),
            reply_markup=pro_menu_keyboard(True)
        )
        await callback.answer("تم الشراء بنجاح!", show_alert=True)
    else:
        await safe_edit_message_text(
            callback.message,
            MSG_PRO_BUY_FAILED_GENERAL,
            reply_markup=pro_menu_keyboard(is_pro)
        )
        await callback.answer("فشل الشراء.", show_alert=True)

@router.callback_query(F.data == "pro_activate_code")
async def pro_activate_code_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """
    بدء عملية تفعيل PRO بالكود: طلب الكود من المستخدم.
    """
    user_id = callback.from_user.id
    
    await state.set_state(UserStates.waiting_for_pro_code)
    
    await safe_edit_message_text(
        callback.message,
        MSG_PRO_ENTER_CODE,
        reply_markup=back_to_menu_keyboard("pro_menu")
    )
    await callback.answer()

@router.message(UserStates.waiting_for_pro_code)
async def pro_activate_code_execute(message: types.Message, state: FSMContext, bot):
    """
    تنفيذ تفعيل PRO بالكود.
    """
    user_id = message.from_user.id
    code = message.text.strip().upper()
    
    await state.clear()
    is_pro = await PRM.is_pro(user_id)
    
    success = await PRM.use_pro_code(user_id, code)
    
    if success:
        code_data = await DB.fetchone("SELECT duration_days FROM pro_codes WHERE code = ?", (code,))
        duration = code_data['duration_days'] if code_data else "غير محددة"
        
        await safe_send_message(
            bot,
            user_id,
            MSG_PRO_CODE_SUCCESS.format(duration=duration),
            reply_markup=main_menu_keyboard(True)
        )
    else:
        await safe_send_message(
            bot,
            user_id,
            MSG_PRO_CODE_INVALID,
            reply_markup=main_menu_keyboard(is_pro)
        )

# --- نظام النقاط (تحويل) ---

@router.callback_query(F.data == "points_transfer")
async def points_transfer_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """
    بدء عملية تحويل النقاط: طلب المبلغ.
    """
    user_id = callback.from_user.id
    
    await state.set_state(UserStates.waiting_for_transfer_amount)
    
    await safe_edit_message_text(
        callback.message,
        MSG_POINTS_ENTER_TRANSFER_AMOUNT,
        reply_markup=back_to_menu_keyboard("main_menu")
    )
    await callback.answer()

@router.message(UserStates.waiting_for_transfer_amount)
async def points_transfer_amount(message: types.Message, state: FSMContext, bot):
    """
    استلام مبلغ التحويل: التحقق من القيمة والرصيد، ثم طلب معرف المستلم.
    """
    user_id = message.from_user.id
    
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await safe_send_message(bot, user_id, MSG_POINTS_TRANSFER_FAILED_INVALID_AMOUNT)
        return
        
    user = await DB.get_user(user_id)
    if user['points'] < amount:
        await safe_send_message(bot, user_id, MSG_POINTS_TRANSFER_FAILED_INSUFFICIENT)
        return

    await state.update_data(transfer_amount=amount)
    await state.set_state(UserStates.waiting_for_receiver_id)
    
    await safe_send_message(
        bot,
        user_id,
        MSG_POINTS_ENTER_RECEIVER_ID,
        reply_markup=back_to_menu_keyboard("main_menu")
    )

@router.message(UserStates.waiting_for_receiver_id)
async def points_transfer_execute(message: types.Message, state: FSMContext, bot):
    """
    تنفيذ عملية تحويل النقاط.
    """
    sender_id = message.from_user.id
    
    try:
        receiver_id = int(message.text.strip())
    except ValueError:
        await safe_send_message(bot, sender_id, MSG_POINTS_TRANSFER_FAILED_RECEIVER)
        return
        
    data = await state.get_data()
    amount = data.get('transfer_amount')
    
    await state.clear()
    
    if not amount:
        await safe_send_message(bot, sender_id, MSG_ERROR)
        return

    result = await PM.transfer_points(sender_id, receiver_id, amount)
    is_pro = await PRM.is_pro(sender_id)
    
    if result == "success":
        await safe_send_message(
            bot,
            sender_id,
            MSG_POINTS_TRANSFER_SUCCESS.format(points=amount, receiver_id=receiver_id),
            reply_markup=main_menu_keyboard(is_pro)
        )
    elif result == "insufficient_points":
        await safe_send_message(bot, sender_id, MSG_POINTS_TRANSFER_FAILED_INSUFFICIENT, reply_markup=main_menu_keyboard(is_pro))
    elif result in ["receiver_not_found", "sender_not_found"]:
        await safe_send_message(bot, sender_id, MSG_POINTS_TRANSFER_FAILED_RECEIVER, reply_markup=main_menu_keyboard(is_pro))
    elif result == "self_transfer":
        await safe_send_message(bot, sender_id, MSG_POINTS_TRANSFER_FAILED_SELF, reply_markup=main_menu_keyboard(is_pro))
    else:
        await safe_send_message(bot, sender_id, MSG_ERROR, reply_markup=main_menu_keyboard(is_pro))

# --- نظام الأرقام المجانية ---

@router.message(F.text == "🌍 أرقام مجانية")
async def numbers_menu_handler(message: types.Message, state: FSMContext, bot):
    """
    معالج قائمة الأرقام: عرض الدول المتاحة.
    """
    user_id = message.from_user.id
    await state.clear()
    
    countries = await NM.get_all_countries()
    
    if not countries:
        await safe_send_message(
            bot,
            user_id,
            MSG_NUMBERS_NO_COUNTRIES,
            reply_markup=main_menu_keyboard(await PRM.is_pro(user_id))
        )
        return
        
    await safe_send_message(
        bot,
        user_id,
        MSG_NUMBERS_MENU,
        reply_markup=numbers_countries_keyboard(countries)
    )

@router.callback_query(F.data.startswith("numbers_country:"))
async def numbers_country_select(callback: types.CallbackQuery, state: FSMContext, bot):
    """
    معالج اختيار الدولة: عرض الأرقام المتاحة في تلك الدولة.
    """
    user_id = callback.from_user.id
    country_id = int(callback.data.split(":")[1])
    is_pro = await PRM.is_pro(user_id)
    
    # TODO: جلب وعرض الأرقام مع دعم التصفح
    await callback.answer(f"تم اختيار الدولة ID: {country_id}. جاري جلب الأرقام...", show_alert=True)
    
    # Placeholder: الرجوع للقائمة الرئيسية مؤقتاً
    await safe_edit_message_text(
        callback.message,
        MSG_MAIN_MENU,
        reply_markup=main_menu_keyboard(is_pro)
    )

# --- معالج الرسائل غير المعروفة ---

@router.message()
async def unhandled_message_handler(message: types.Message, state: FSMContext, bot):
    """
    معالج الرسائل غير المعالجة.
    إذا كان المستخدم في حالة FSM، يتم تجاهل الرسالة.
    إذا لم يكن في حالة FSM، يتم إرسال رسالة خطأ بسيطة وإعادته إلى القائمة الرئيسية.
    """
    if await state.get_state():
        # إذا كان في حالة FSM، لا تفعل شيئاً، انتظر الإدخال الصحيح
        return
        
    user_id = message.from_user.id
    is_pro = await PRM.is_pro(user_id)
    
    await safe_send_message(
        bot,
        user_id,
        MSG_INVALID_COMMAND,
        reply_markup=main_menu_keyboard(is_pro)
    )

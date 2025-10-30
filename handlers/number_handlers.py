from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from loguru import logger
from typing import Dict, Any

from database import Database
from services.points_manager import PointsManager
from services.pro_manager import ProManager
from services.setup_manager import SetupManager
from services.number_manager import NumberManager
from utils.keyboards import back_to_menu_keyboard, main_menu_keyboard, pagination_keyboard
from utils.messages import (
    MSG_NUMBERS_MENU, MSG_NUMBERS_SELECT_COUNTRY, MSG_NUMBERS_NO_NUMBERS,
    MSG_ACCESS_DENIED, MSG_ADMIN_INVALID_INPUT, MSG_ERROR,
    MSG_NUMBER_REQUEST_INITIATED, MSG_NUMBER_REQUEST_CHECK, MSG_NUMBER_CODE_RECEIVED,
    MSG_NUMBER_REQUEST_EXPIRED, MSG_NUMBER_REQUEST_NOT_READY
)
from utils.utils import safe_send_message, safe_edit_message_text

# --- FSM States ---
from aiogram.fsm.state import State, StatesGroup

class NumberStates(StatesGroup):
    """حالات FSM لنظام الأرقام."""
    browsing_numbers = State()
    waiting_for_pro_pattern = State()
    waiting_for_code = State() # حالة جديدة للانتظار

# --- Router Setup ---
router = Router()

# --- Dependency Injection ---
DB: Database
PM: PointsManager
PRM: ProManager
SM: SetupManager
NM: NumberManager

# --- Constants ---
NUMBERS_PER_PAGE = 10

@router.message(F.text == "🌍 أرقام مجانية")
async def numbers_menu_handler(message: types.Message, state: FSMContext, bot):
    """معالج قائمة الأرقام: عرض قائمة الدول."""
    user_id = message.from_user.id
    await state.clear()
    
    countries = await NM.get_all_countries()
    
    if not countries:
        await safe_send_message(bot, user_id, "عذراً، لا توجد دول متاحة حالياً.")
        return

    builder = types.InlineKeyboardBuilder()
    
    # إضافة زر البحث المتقدم لـ PRO
    is_pro = await PRM.is_pro(user_id)
    if is_pro:
        builder.row(types.InlineKeyboardButton(text="⭐ بحث متقدم (PRO)", callback_data="numbers_pro_search"))

    # إضافة الدول
    for country in countries:
        text = f"{country['flag']} {country['name']} ({country['number_count']})"
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"numbers_country:{country['id']}:1"))
        
    builder.row(types.InlineKeyboardButton(text="🔙 رجوع للقائمة الرئيسية", callback_data="main_menu"))
    
    await safe_send_message(
        bot,
        user_id,
        MSG_NUMBERS_SELECT_COUNTRY,
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "numbers_menu")
async def back_to_numbers_menu(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج الرجوع إلى قائمة الأرقام (الدول)."""
    # محاكاة إرسال رسالة جديدة بدلاً من تعديل الرسالة الحالية
    await callback.message.delete()
    await numbers_menu_handler(callback.message, state, bot)
    await callback.answer()

@router.callback_query(F.data.startswith("numbers_country:"))
async def numbers_list_handler(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج عرض قائمة الأرقام لدولة معينة."""
    user_id = callback.from_user.id
    _, country_id_str, page_str = callback.data.split(":")
    country_id = int(country_id_str)
    page = int(page_str)
    
    is_pro = await PRM.is_pro(user_id)
    country = await NM.get_country(country_id)
    
    if not country:
        await callback.answer("الدولة غير موجودة.", show_alert=True)
        return

    numbers = await NM.get_numbers_for_country(country_id, is_pro, page, NUMBERS_PER_PAGE)
    total_count = await NM.get_total_numbers_count(country_id)
    total_pages = (total_count + NUMBERS_PER_PAGE - 1) // NUMBERS_PER_PAGE
    
    if not numbers and page == 1:
        await safe_edit_message_text(
            callback.message,
            MSG_NUMBERS_NO_NUMBERS,
            reply_markup=back_to_menu_keyboard("numbers_menu")
        )
        await callback.answer()
        return

    # 1. بناء رسالة الأرقام
    message_text = f"🌍 **الأرقام المتاحة لـ {country['flag']} {country['name']}** (الصفحة {page}/{total_pages})\n\n"
    
    builder = types.InlineKeyboardBuilder()
    
    for number in numbers:
        pro_tag = "⭐" if number['is_premium'] else ""
        text = f"{pro_tag} {number['number']} ({number['platform']})"
        
        # زر لعرض تفاصيل الرقم
        builder.row(types.InlineKeyboardButton(text=text, callback_data=f"numbers_request:{number['id']}"))

    # 2. بناء لوحة مفاتيح التصفح
    if total_pages > 1:
        # بناء لوحة مفاتيح التصفح
        pagination_kb = types.InlineKeyboardBuilder()
        if page > 1:
            pagination_kb.add(types.InlineKeyboardButton(text="⬅️ السابق", callback_data=f"numbers_country:{country_id}:{page - 1}"))
        
        pagination_kb.add(types.InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"))
        
        if page < total_pages:
            pagination_kb.add(types.InlineKeyboardButton(text="التالي ➡️", callback_data=f"numbers_country:{country_id}:{page + 1}"))
            
        builder.attach(pagination_kb)
    
    builder.row(types.InlineKeyboardButton(text="🔙 رجوع لقائمة الدول", callback_data="numbers_menu"))

    await safe_edit_message_text(
        callback.message,
        message_text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()
    
@router.callback_query(F.data.startswith("numbers_request:"))
async def number_request_handler(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج طلب الرقم: بدء عملية حجز الرقم."""
    user_id = callback.from_user.id
    number_id = int(callback.data.split(":")[1])
    
    # 1. بدء عملية حجز الرقم
    request_data = await NM.initialize_number_request(user_id, number_id)
    
    if not request_data:
        await callback.answer("❌ الرقم غير متاح حالياً أو غير موجود.", show_alert=True)
        return

    # 2. حفظ حالة الانتظار
    await state.set_state(NumberStates.waiting_for_code)
    await state.update_data(current_number_id=number_id)
    
    # 3. إرسال رسالة الانتظار
    message_text = MSG_NUMBER_REQUEST_INITIATED.format(
        number=request_data['number'],
        platform=request_data['platform'],
        expiry=request_data['expires_at']
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 التحقق من وصول الكود", callback_data=f"numbers_check_code:{number_id}")],
        [types.InlineKeyboardButton(text="❌ إلغاء الطلب", callback_data=f"numbers_cancel_request:{number_id}")]
    ])
    
    await safe_edit_message_text(
        callback.message,
        message_text,
        reply_markup=keyboard
    )
    await callback.answer("تم حجز الرقم بنجاح. يرجى الانتظار لوصول الكود.")

@router.callback_query(F.data.startswith("numbers_check_code:"))
async def number_check_code_handler(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج التحقق من وصول الكود."""
    user_id = callback.from_user.id
    number_id = int(callback.data.split(":")[1])
    
    # 1. التحقق من الكود
    code_result = await NM.check_for_code(user_id, number_id)
    
    if code_result == "EXPIRED":
        await state.clear()
        await safe_edit_message_text(
            callback.message,
            MSG_NUMBER_REQUEST_EXPIRED,
            reply_markup=back_to_menu_keyboard("numbers_menu")
        )
        await callback.answer("انتهت صلاحية حجز الرقم.", show_alert=True)
        return
    elif code_result:
        # الكود وصل بنجاح
        await state.clear()
        await safe_edit_text(
            callback.message,
            MSG_NUMBER_CODE_RECEIVED.format(code=code_result),
            reply_markup=back_to_menu_keyboard("numbers_menu")
        )
        await callback.answer("وصل الكود بنجاح!", show_alert=True)
        return
    else:
        # الكود لم يصل بعد
        await callback.answer(MSG_NUMBER_REQUEST_NOT_READY, show_alert=True)

@router.callback_query(F.data.startswith("numbers_cancel_request:"))
async def number_cancel_request_handler(callback: types.CallbackQuery, state: FSMContext, bot):
    """معالج إلغاء طلب الرقم."""
    user_id = callback.from_user.id
    number_id = int(callback.data.split(":")[1])
    
    await NM.finalize_number_request(user_id, number_id, "CANCELLED")
    await state.clear()
    
    await safe_edit_message_text(
        callback.message,
        "❌ تم إلغاء طلب الرقم بنجاح. يمكنك اختيار رقم آخر.",
        reply_markup=back_to_menu_keyboard("numbers_menu")
    )
    await callback.answer("تم إلغاء الطلب.")

# --- معالجات البحث المتقدم (PRO) ---
# (تم نسخها من user_handlers.py وتعديلها لتناسب NumberManager)

@router.callback_query(F.data == "numbers_pro_search")
async def pro_search_start(callback: types.CallbackQuery, state: FSMContext, bot):
    """بدء البحث المتقدم لـ PRO: عرض قائمة الدول."""
    user_id = callback.from_user.id
    
    is_pro = await PRM.is_pro(user_id)
    if not is_pro:
        await callback.answer(MSG_ACCESS_DENIED, show_alert=True)
        return

    await state.set_state(NumberStates.waiting_for_pro_pattern)
    
    countries = await NM.get_countries_management_list()
    
    builder = types.InlineKeyboardBuilder()
    for country in countries:
        builder.row(types.InlineKeyboardButton(text=f"{country['flag']} {country['name']}", callback_data=f"pro_search_country:{country['id']}"))
    
    builder.row(types.InlineKeyboardButton(text="🔙 رجوع لقائمة الأرقام", callback_data="numbers_menu"))
    
    await safe_edit_message_text(
        callback.message,
        "⭐ **البحث المتقدم (PRO)**\n\nيرجى اختيار الدولة أولاً:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pro_search_country:"))
async def pro_search_get_country(callback: types.CallbackQuery, state: FSMContext, bot):
    """استلام الدولة للبحث المتقدم: طلب النمط."""
    user_id = callback.from_user.id
    country_id = int(callback.data.split(":")[1])
    
    await state.update_data(pro_search_country_id=country_id)
    await state.set_state(NumberStates.waiting_for_pro_pattern)
    
    country = await NM.get_country(country_id)
    
    await safe_edit_message_text(
        callback.message,
        f"📝 **{country['flag']} {country['name']}**\n\nيرجى إدخال نمط البحث عن الأرقام المميزة (مثال: `*123*` أو `+1*888`):",
        reply_markup=back_to_menu_keyboard("numbers_menu")
    )
    await callback.answer()

@router.message(NumberStates.waiting_for_pro_pattern)
async def pro_search_execute(message: types.Message, state: FSMContext, bot):
    """تنفيذ البحث المتقدم."""
    user_id = message.from_user.id
    pattern = message.text.strip()
    
    data = await state.get_data()
    country_id = data.get('pro_search_country_id')
    
    await state.clear()
    
    if not country_id:
        await safe_send_message(bot, user_id, MSG_ERROR)
        return

    results = await NM.search_premium_numbers(country_id, pattern)
    country = await NM.get_country(country_id)
    
    if not results:
        msg = f"❌ لم يتم العثور على أرقام مميزة في {country['name']} تطابق النمط `{pattern}`."
    else:
        msg = f"✅ **نتائج البحث المتقدم في {country['name']}** ({len(results)} نتائج):\n\n"
        for number in results:
            msg += f"• `{number['number']}` ({number['platform']})\n"
            
    await safe_send_message(
        bot,
        user_id,
        msg,
        reply_markup=main_menu_keyboard(await PRM.is_pro(user_id))
    )

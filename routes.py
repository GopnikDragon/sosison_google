import asyncio, aiosqlite, time, random, sqlite3
from aiogram import Router, types, F, BaseMiddleware
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from typing import Callable, Dict, Any, Awaitable, Union

help_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Открыть помощь по боту", url="https://telegra.ph/Pomoshch-po-botu-Sosison-v2-02-14")]
])

router=Router()
DB_PATH='main.db'

    class Form(StatesGroup):
        name = State()

async def get_user_data(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            'SELECT sausages, inventory FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else (0, "")

CHANNEL_ID = -1003740077870
CHANNEL_URL = "https://t.me/sosison_vkusno2_channel"




class CheckSubMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
                       event: Message, data: Dict[str, Any]) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)

        bot = data['bot']
        if await is_subscribed(bot, event.from_user.id):
            return await handler(event, data)
        return

def get_subscribe_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Подписаться на канал", url=CHANNEL_URL)
    builder.button(text="✅ Я подписался", callback_data="check_subs")
    builder.adjust(1)
    return builder.as_markup()

async def is_subscribed(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False


async def update_purchase(user_id, new_balance, new_inventory):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET balance = ?, inventory = ? WHERE user_id = ?',
            (new_balance, new_inventory, user_id)
        )
        await db.commit()

async def get_user_name(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT name FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row and row[0] else None

async def set_user_name(user_id, name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (user_id, name) VALUES(?, ?)
            ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
        ''', (user_id, name))
        await db.commit()

SHOP_ITEMS = {
    "amulet": {
        "name": "🍀 Браслет удачи",
        "price": 100,
        "desc": "+8% к сырному и +3% к золотому!",
        "bonus": [-3, 8, 3, -3, -4] # Изменения для весов [Обыч, Сыр, Золот, Гниль, Пыль]
    },
    "magnifier": {
        "name": "🔍 Золотая лупа",
        "price": 200,
        "desc": "Шанс на Золотой сосисон выше в 2 раза!",
        "bonus": [-10, 0, 10, -8, -12]
    }
}

class ShopCallback(CallbackData, prefix="buy"):
    item_id: str

async def show_main_menu(message: types.Message, name: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🍴 Кушать сосисон", callback_data="menu_sosison")
    builder.button(text="🛒 Магазин", callback_data="open_shop")
    builder.button(text="🏆 Топ", callback_data="open_top")
    builder.button(text="👤 Профиль", callback_data="open_profile")
    builder.adjust(1, 2, 1)

    text = f"Привет, <b>{name}</b>! 👋\n\nВыберите действие:"

    if isinstance(message, types.Message):
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command('start'))
async def start(message: Message, state: FSMContext):
    user = message.from_user
    username = f"@{user.username}" if user.username else "Без юзернейма"
    print(f"🚀 [START] Юзер: {username} | ID: {user.id} | Имя в ТГ: {user.full_name}")
    # ---------------------

    await state.clear()

    sub_status = await is_subscribed(message.bot, message.from_user.id)
    if not sub_status:
        await message.answer(
            "👋 <b>Привет! Для доступа к боту нужно подписаться.</b>\n\n"
            "Подпишись на наш канал, чтобы не пропускать важные новости!",
            reply_markup=get_subscribe_keyboard(),
            parse_mode="HTML"
        )
        return

    name = await get_user_name(message.from_user.id)
    if name:
        await show_main_menu(message, name)
    else:
        await message.answer("🍗 <b>Добро пожаловать!</b>\nЯ тебя еще не знаю. Как мне тебя называть?", parse_mode='HTML')
        await state.set_state(Form.name)

@router.callback_query(F.data == "check_subs")
async def check_subs_callback(callback: CallbackQuery, state: FSMContext):
    if await is_subscribed(callback.bot, callback.from_user.id):
        name = await get_user_name(callback.from_user.id)
        if name:
            await callback.answer("✅ Подписка подтверждена!")
            await show_main_menu(callback.message, name)
        else:
            await callback.message.edit_text("✅ Спасибо за подписку! 🤝\n<b>Давай познакомимся. Как мне тебя называть?</b>", parse_mode="HTML")
            await state.set_state(Form.name)
    else:
        await callback.answer("❌ Вы всё ещё не подписаны!", show_alert=True)

@router.message(Form.name)
async def capture_name(message: Message, state: FSMContext):
    user_name = message.text.strip()

    if not user_name:
        return await message.answer("❌ Имя не может быть пустым! Введи что-нибудь.")

    if len(user_name) > 15:
        return await message.answer("❌ Упс, слишком длинно! Давай покороче (до 15 символов).")

    await set_user_name(message.from_user.id, user_name)
    await state.clear()

    await message.answer(f"✅ Приятно познакомиться, <b>{user_name}</b>!", parse_mode="HTML")
    await show_main_menu(message, user_name)

@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    name = await get_user_name(callback.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🍴 Кушать сосисон", callback_data="menu_sosison")
    builder.button(text="🛒 Магазин", callback_data="open_shop")
    builder.button(text="🏆 Топ", callback_data="open_top")
    builder.button(text="👤 Профиль", callback_data="open_profile")
    builder.adjust(1, 2, 1)

    await callback.message.edit_text(
        f"Привет, <b>{name}</b>! 👋\n\nВыберите действие ниже:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


async def show_sausage_menu(event: Union[Message, CallbackQuery], name: str):
    builder = InlineKeyboardBuilder()
    builder.button(text='Сосисон', callback_data='sosison')
    builder.button(text='Сосисон на гриле', callback_data='gril')
    builder.button(text='Сосисон в тесте', callback_data='testo')
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")

    builder.adjust(1)

    text = f"😋 Что сегодня будешь кушать, {name}?"

    if isinstance(event, Message):
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await event.answer()


@router.message(Command('sosison'))
@router.callback_query(F.data == 'menu_sosison') # Или поменяй на "go_eat" в главном меню
async def call_go_eat(callback: CallbackQuery):
    name = await get_user_name(callback.from_user.id)
    await show_sausage_menu(callback, name)
async def sosison_command(message: Message):
    name = await get_user_name(message.from_user.id)
    if name:
        await show_sausage_menu(message, name)
    else:
        await message.answer("👋 Сначала давай познакомимся! Пиши команду /start")

@router.message(Command('help'))
async def start(message: Message):
    await message.answer('👇 Помощь по боту "Сосисон v2" 👇', reply_markup=help_keyboard)

def get_rank(count):
    if count >= 300:
        return "👑 БОГ СОСИСОНОВ"
    if count >= 200:
        return "🏆 КОРОЛЬ СОСИСОНОВ"
    elif count >= 130:
        return "⭐ Пожиратель Сосисонов"
    elif count >= 50:
        return "✨ Сосисонный Мастер"
    elif count >= 20:
        return "🌭 Любитель"
    else:
        return "🔰 Начинающий поедатель"


from typing import Union


@router.message(Command("profile"))
@router.callback_query(F.data == "open_profile")
async def show_profile(event: Union[types.Message, types.CallbackQuery]):
    user_id = event.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
                'SELECT name, sausages, inventory FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        return await event.answer("❌ Сначала начни игру через /start")

    name, sausages, inventory = row

    rank = get_rank(sausages)

    inv_list = inventory.split(",") if inventory else []
    items_text = []
    for item_id in inv_list:
        if item_id in SHOP_ITEMS:
            items_text.append(SHOP_ITEMS[item_id]["name"])

    items_display = ", ".join(items_text) if items_text else "Ничего не куплено 🛒"

    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")

    text = (
        f"👤 <b>ВАШ ПРОФИЛЬ:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f'Ваше имя: <b>{name}</b>\n'
        f"🎖 Ваш ранг: <b>{rank}</b>\n"
        f"🌭 Всего съедено: <b>{sausages}</b> шт.\n\n"
        f"📦 Купленные улучшения:\n"
        f"└ <i>{items_display}</i>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
        await event.answer()


@router.message(Command("top"))
@router.callback_query(F.data.in_(["open_top", "refresh_top"]))
async def show_top(event: Union[types.Message, types.CallbackQuery]):
    user_id = event.from_user.id

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="refresh_top")
    builder.button(text="⬅️ Назад", callback_data="back_to_menu")
    builder.adjust(2)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
                'SELECT user_id, name, sausages FROM users ORDER BY sausages DESC LIMIT 10'
        ) as cursor:
            rows = await cursor.fetchall()

        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total_res = await cursor.fetchone()
            total_users = total_res[0] if total_res else 0

        async with db.execute(
                'SELECT (SELECT COUNT(*) FROM users WHERE sausages > u.sausages) + 1 '
                'FROM users u WHERE user_id = ?', (user_id,)
        ) as cursor:
            res = await cursor.fetchone()
            user_rank_pos = res[0] if res else "—"

    text = "🏆 <b>ТОП-10 ПОЕДАТЕЛЕЙ СОСИСОНОВ</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for i, (db_user_id, db_name, count) in enumerate(rows, 1):
        prefix = medals.get(i, f"{i}. ")
        display_name = db_name if db_name else f"Игрок {str(db_user_id)[-2:]}"

        if db_user_id == user_id:
            line = f"{prefix} <b>{display_name} (ВЫ)</b>"
        else:
            line = f"{prefix} {display_name}"

        text += f"{line} — <code>{count}</code> шт.\n"
        text += f"└ <b>{get_rank(count)}</b>\n\n"

    text += "━━━━━━━━━━━━━━━━━━\n"
    text += f"👤 Ваше место в топе: <b>{user_rank_pos}</b> из <b>{total_users}</b>"

    if isinstance(event, types.Message):
        await event.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
    else:
        try:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
        except Exception:
            pass
        await event.answer()

async def get_top_data(current_user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
                'SELECT user_id, name, sausages FROM users ORDER BY sausages DESC LIMIT 10') as cursor:
            rows = await cursor.fetchall()

        async with db.execute(
                'SELECT (SELECT COUNT(*) FROM users WHERE sausages > u.sausages) + 1 FROM users u WHERE user_id = ?',
                (current_user_id,)) as cursor:
            user_pos = await cursor.fetchone()
            user_rank_pos = user_pos[0] if user_pos else "—"

    text = "🏆 <b>ТОП-10 ПОЕДАТЕЛЕЙ СОСИСОНОВ</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for i, (db_user_id, name, count) in enumerate(rows, 1):
        prefix = medals.get(i, f"{i}. ")
        display_name = name if name else f"Аноним {i}"

        is_me = " 👤" if db_user_id == current_user_id else ""

        text += f"{prefix} <b>{display_name}{is_me}</b> — <code>{count}</code> шт.\n"
        text += f"└ <i>{get_rank(count)}</i>\n\n"

    text += f"━━━━━━━━━━━━━━━━━━\n👤 Ваше место в топе: <b>{user_rank_pos}</b>"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить топ", callback_data="refresh_top")
    return text, builder.as_markup()


@router.message(Command('rename'))
async def rename_user(message: Message, state: FSMContext):
    current_name = await get_user_name(message.from_user.id)

    if current_name:
        await message.answer(f"Твоё текущее имя: <b>{current_name}</b>\nНапиши новое имя ниже:", parse_mode='HTML')
    else:
        await message.answer("Как мне тебя называть?")

    await state.set_state(Form.name)

@router.message(Command("shop"))
@router.callback_query(F.data == "open_shop")
async def show_shop(event: Union[types.Message, types.CallbackQuery]):
    user_id = event.from_user.id
    user_data = await get_user_data(user_id)
    sausages, inventory = user_data

    builder = InlineKeyboardBuilder()

    for item_id, info in SHOP_ITEMS.items():
        is_bought = item_id in inventory.split(",") if inventory else False
        status = "✅ Куплено" if is_bought else f"{info['price']} 🌭"

        builder.button(
            text=f"{info['name']} — {status}",
            callback_data=ShopCallback(item_id=item_id).pack()
        )

    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    builder.adjust(1)

    text = (
        f"🛒 <b>Магазин улучшений</b>\n"
        f"🌭 Ваши сосисоны: <b>{sausages}</b> шт.\n\n"
        f"🍀 Предметы навсегда повышают шанс на редкие сосисоны!"
    )

    if isinstance(event, types.Message):
        await event.answer(text, parse_mode='HTML', reply_markup=builder.as_markup())
    else:
        await event.message.edit_text(text, parse_mode='HTML', reply_markup=builder.as_markup())
        await event.answer()


@router.callback_query(ShopCallback.filter())
async def process_purchase(callback: types.CallbackQuery, callback_data: ShopCallback):
    user_id = callback.from_user.id
    user_data = await get_user_data(user_id)
    sausages, inventory = user_data

    item = SHOP_ITEMS.get(callback_data.item_id)
    inv_list = inventory.split(",") if inventory else []

    if callback_data.item_id in inv_list:
        return await callback.answer("❌ У вас уже есть этот предмет!", show_alert=True)

    if sausages < item['price']:
        return await callback.answer(f"❌ Недостаточно сосисонов! Нужно еще {item['price'] - sausages} шт.", show_alert=True)

    new_sausages = sausages - item['price']
    inv_list.append(callback_data.item_id)
    new_inv = ",".join(inv_list)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE users SET sausages = ?, inventory = ? WHERE user_id = ?',
            (new_sausages, new_inv, user_id)
        )
        await db.commit()

    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 В магазин", callback_data="open_shop")
    builder.button(text="⬅️ В меню", callback_data="back_to_menu")

    await callback.message.edit_text(
        f"✅ Успешно! Вы купили <b>{item['name']}!</b>\n"
        f"🌭 Осталось: <b>{new_sausages}</b> шт.",
        parse_mode='HTML',
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.message(Command("unban"))
async def cmd_unban(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        return

    if not command.args:
        return await message.answer("⚠️ Пиши: `/unban ID`")

    try:
        target_id = int(command.args)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE users SET banned_until = 0 WHERE user_id = ?", (target_id,))
            await db.commit()
        await message.answer(f"✅ Пользователь {target_id} разбанен!")
    except ValueError:
        await message.answer("❌ ID должен быть числом!")


@router.message(Command("ban"))
async def cmd_ban(message: types.Message, command: CommandObject):
    # 1. Проверка на админа
    if message.from_user.id != ADMIN_ID:
        return

    args = command.args.split() if command.args else []

    if len(args) < 1:
        return await message.answer(
            "⚠️ Использование: `/ban ID [часы]`\nПример: `/ban 12345 12` (на 12 часов)\n`/ban 12345 0` (навсегда)",
            parse_mode="Markdown")

    try:
        target_id = int(args[0])
        hours = int(args[1]) if len(args) > 1 else 12  # По умолчанию 12 часов

        # Если введено 0 — ставим бан на 100 лет (навсегда)
        ban_time = int(time.time()) + (hours * 3600) if hours > 0 else int(time.time()) + (100 * 365 * 24 * 3600)

        async with aiosqlite.connect("main.db") as db:
            await db.execute("UPDATE users SET banned_until = ? WHERE user_id = ?", (ban_time, target_id))
            await db.commit()

        status_text = f"на {hours} ч." if hours > 0 else "НАВСЕГДА"
        await message.answer(f"🚫 Пользователь `{target_id}` успешно забанен {status_text}", parse_mode="Markdown")

        # Лог в консоль
        print(f"👮 АДМИН-БАН: Пользователь {target_id} забанен администратором {status_text}")

    except ValueError:
        await message.answer("❌ Ошибка: ID и время должны быть числами!")


@router.message(Command('delitem'))
async def admin_delete_item(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()

    if len(args) < 3:
        return await message.answer("❌ Формат: <code>/delitem ID_ПОЛЬЗОВАТЕЛЯ ID_ПРЕДМЕТА</code>", parse_mode='HTML')

    target_user_id = args[1]
    item_id = args[2].lower()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT inventory FROM users WHERE user_id = ?', (target_user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await message.answer(f"❌ Пользователь <code>{target_user_id}</code> не найден.", parse_mode='HTML')

        inventory = row[0]
        inv_list = inventory.split(",") if inventory else []

        if item_id not in inv_list:
            return await message.answer(
                f"❌ У игрока нет предмета <b>{item_id}</b>\nЕго инвентарь: <code>{inventory}</code>", parse_mode='HTML')

        inv_list.remove(item_id)
        new_inv = ",".join(inv_list)

        await db.execute(
            'UPDATE users SET inventory = ? WHERE user_id = ?',
            (new_inv, target_user_id)
        )
        await db.commit()

    await message.answer(f"✅ Предмет <b>{item_id}</b> удален у пользователя <code>{target_user_id}</code>",
                         parse_mode='HTML')

@router.message()
async def start(message: Message):
    await message.answer('Извините, к сожалению я Робот и <u>могу отвечать только на команды, которые в меня поместил разработчик.</u> И на ваше сообщение я ничем ответить не смогу.\n<b>Пожалуйста уточните, существует ли такая команда через команду /help</b>', parse_mode='HTML')

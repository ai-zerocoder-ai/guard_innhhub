import os
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatType
from aiogram.filters import Command

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # вывод отладочных сообщений
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения из файла .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в переменных окружения")
    exit(1)

# Загружаем CHAT_ID из .env (числовой ID или строка, например, "@inn")
CHAT_ID_raw = os.getenv("CHAT_ID")
if not CHAT_ID_raw:
    logger.error("CHAT_ID не найден в переменных окружения")
    exit(1)

if CHAT_ID_raw.startswith("-") and CHAT_ID_raw[1:].isdigit():
    CHAT_ID = int(CHAT_ID_raw)
else:
    CHAT_ID = CHAT_ID_raw

logger.info(f"Используем CHAT_ID: {CHAT_ID}")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Множество для хранения ID пользователей, успешно прошедших верификацию
verified_users = set()

# Обработчик новых участников – срабатывает только если в сообщении есть new_chat_members
@dp.message(lambda message: message.new_chat_members is not None)
async def new_member_handler(message: types.Message):
    logger.info(f"Получено сообщение о новых участниках: {message.new_chat_members}")
    for user in message.new_chat_members:
        user_id = user.id
        full_name = user.full_name

        # Если пользователь уже верифицирован, пропускаем отправку капчи
        if user_id in verified_users:
            logger.info(f"Пользователь {user_id} уже верифицирован, пропускаем отправку капчи")
            continue

        logger.debug(f"Обработка нового участника: {user_id} - {full_name}")
        try:
            # Отправляем ЛС с капчей
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="ВОДОРОД", callback_data=f"verify_{user_id}")]
            ])
            text = (
                f"Привет, *{full_name}*!\n\n"
                "Добро пожаловать в *H2 Innovation Hub*! 🚀\n\n"
                "Сначала мы должны удостовериться, что Вы - не бот.\n\n"
                "Просим ответить на вопрос:\n\n"
                "Какой элемент является первым в Периодической системе химических элементов Д.И. Менделеева?"
            )
            await bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=keyboard)
            logger.info(f"Отправлено ЛС пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке ЛС пользователю {user_id}: {e}")

        # Отправляем сообщение в группу с инструкцией перейти в ЛС
        try:
            group_message = (
                f"👋 Привет, [{full_name}](tg://user?id={user_id})!\n\n"
                "Необходимо в течение 60 секуд пройти верификацию по "
                "[ссылке](https://t.me/Innhhub_guardian_bot?start=verify)\n\n"
                "Иначе, к сожалению, придется удалить Вас из группы."
            )
            await message.answer(group_message, parse_mode="Markdown")
            logger.info(f"Отправлено сообщение в группе для пользователя {user_id}")
        except Exception as ex:
            logger.error(f"Ошибка при отправке сообщения в группе для пользователя {user_id}: {ex}")

        # Далее, как и раньше, ожидаем 60 секунд и, если верификация не пройдена, баним пользователя
        await asyncio.sleep(60)
        if user_id not in verified_users:
            logger.info(f"Пользователь {user_id} не прошёл верификацию, выполняется бан")
            try:
                await bot.ban_chat_member(CHAT_ID, user_id)
                await bot.send_message(user_id,
                    "🚫 Ты не успел верифицироваться в Hydrogen Innovation Hub.\n\n"
                    "Попробуй заново набрав команду /retry")
                logger.info(f"Пользователь {user_id} забанен")
            except Exception as kick_error:
                logger.error(f"Ошибка при бане пользователя {user_id}: {kick_error}")

@dp.callback_query(lambda callback: callback.data.startswith("verify_"))
async def verify_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if user_id != callback_query.from_user.id:
        logger.warning(f"Попытка верификации за другого пользователя: {callback_query.from_user.id} вместо {user_id}")
        return
    verified_users.add(user_id)
    await callback_query.answer()  # Отправляем ответ на callback-запрос
    await bot.send_message(user_id,
        "✅ Верификаия в Hydrogen Innovation Hub пройдена.\n\n"
        "Пользуйтесь во благо!))",
        parse_mode="Markdown"
    )
    logger.info(f"Пользователь {user_id} успешно верифицирован")

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    if message.from_user.id in verified_users:
        await message.answer("Привет! Ты уже верифицирован в Hydrogen Innovation Hub.")
    else:
        await message.answer(
            "Следуй инструкциям.\n\n"
            "Если возникнут трудности с верификацией, напиши команду /retry."
        )

@dp.message(Command("retry"))
async def retry_handler(message: types.Message):
    # Если команда пришла не в личном чате, уведомляем пользователя
    if message.chat.type != ChatType.PRIVATE:
        logger.info(f"Команда /retry получена в группе от пользователя {message.from_user.id}")
        await message.reply("Команда /retry работает только в личном чате с ботом. Пожалуйста, отправьте /retry в ЛС.")
        return

    user_id = message.from_user.id
    full_name = message.from_user.full_name
    logger.info(f"Получена команда /retry от пользователя {user_id} - {full_name}")
    try:
        await bot.unban_chat_member(CHAT_ID, user_id, only_if_banned=True)
        logger.info(f"Пользователь {user_id} разбанен")
    except Exception as e:
        logger.error(f"Ошибка при разбане пользователя {user_id}: {e}")
    verified_users.discard(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ВОДОРОД", callback_data=f"verify_{user_id}")]
    ])
    invite_link = "https://t.me/testinnhh"  # Замените на актуальную ссылку вашей группы
    text = (
        f"Привет, *{full_name}*!\n\n"
        "Ты успешно разблокирован.\n\n"
        "Давай попробуем ещё раз пройти проверку. Нажми кнопку ниже для верификации.\n\n"
        f"После верификации вступи в группу по [этой ссылке]({invite_link})."
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    logger.info(f"Отправлено сообщение о повторной верификации пользователю {user_id}")

async def main():
    logger.info("Запуск polling бота")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

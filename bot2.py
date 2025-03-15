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
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения из файла .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("BOT_TOKEN не найден в переменных окружения")
    exit(1)

# Загружаем CHAT_ID группы из .env (числовой ID или строка, например, "@inn")
CHAT_ID_raw = os.getenv("CHAT_ID")
if not CHAT_ID_raw:
    logger.error("CHAT_ID не найден в переменных окружения")
    exit(1)
if CHAT_ID_raw.startswith("-") and CHAT_ID_raw[1:].isdigit():
    CHAT_ID = int(CHAT_ID_raw)
else:
    CHAT_ID = CHAT_ID_raw

# URL приглашения в группу, который бот выдаёт в личном чате после верификации
GROUP_INVITE_LINK = os.getenv("GROUP_INVITE_LINK", "https://t.me/testinnhh")

# URL deep link для входа в личный чат с ботом с параметром верификации
BOT_DEEP_LINK = f"https://t.me/{os.getenv('BOT_USERNAME', 'Innhhub_guardian_bot')}?start=verify"

logger.info(f"Используем CHAT_ID: {CHAT_ID}")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Множество для хранения ID пользователей, успешно прошедших верификацию
verified_users = set()

# Обработчик новых участников в группе.
@dp.message(lambda message: message.new_chat_members is not None)
async def new_member_handler(message: types.Message):
    logger.info(f"Получено сообщение о новых участниках: {message.new_chat_members}")
    for user in message.new_chat_members:
        user_id = user.id
        full_name = user.full_name

        # Если пользователь уже верифицирован, не отправляем повторно капчу
        if user_id in verified_users:
            logger.info(f"Пользователь {user_id} уже верифицирован, пропускаем отправку капчи")
            continue

        logger.debug(f"Обработка нового участника: {user_id} - {full_name}")

        # Отправляем личное сообщение с капчей
        try:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="ВОДОРОД", callback_data=f"verify_{user_id}")]
            ])
            text = (
                f"Привет, *{full_name}*!\n\n"
                "Добро пожаловать в *H2 Innovation Hub*! 🚀\n\n"
                "Сначала нужно удостовериться, что ты не бот.\n\n"
                "Ответь на вопрос:\n\n"
                "Какой элемент является первым в Периодической системе Менделеева?"
            )
            await bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=keyboard)
            logger.info(f"Отправлено ЛС пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка при отправке ЛС пользователю {user_id}: {e}")

        # Отправляем сообщение в группу с инструкцией
        try:
            group_message = (
                f"👋 Привет, [{full_name}](tg://user?id={user_id})!\n\n"
                "Для участия в группе необходимо пройти верификацию.\n\n"
                "Нажми [здесь]({deep_link}) для перехода в ЛС с ботом.\n\n"
                "Верифицируйся в течение **60 секунд**, иначе тебя удалят."
            ).format(deep_link=BOT_DEEP_LINK)
            await message.answer(group_message, parse_mode="Markdown", disable_web_page_preview=True)
            logger.info(f"Отправлено сообщение в группе для пользователя {user_id}")
        except Exception as ex:
            logger.error(f"Ошибка при отправке сообщения в группе для пользователя {user_id}: {ex}")

        # Ждём 60 секунд; если пользователь не верифицирован, выполняем уведомление и бан
        await asyncio.sleep(60)
        if user_id not in verified_users:
            logger.info(f"Пользователь {user_id} не прошёл верификацию, уведомляем и выполняем бан")
            try:
                # Попытка уведомить через ЛС
                await bot.send_message(
                    user_id,
                    "🚫 Ты не успел верифицироваться в H2 Innovation Hub.\n"
                    "Возможно, у тебя закрыты ЛС. Открой их и набери /retry, чтобы пройти проверку.",
                    parse_mode="Markdown"
                )
                logger.info(f"Уведомление в ЛС пользователю {user_id} отправлено")
            except Exception as notification_error:
                logger.error(f"Ошибка при отправке уведомления в ЛС пользователю {user_id}: {notification_error}")
                try:
                    await message.answer(
                        f"⚠️ {full_name}, похоже, что мы тебя забаним.",
                        reply_to_message_id=message.message_id,
                        parse_mode="Markdown"
                    )
                    logger.info(f"Уведомление в группе для пользователя {user_id} отправлено")
                except Exception as group_notification_error:
                    logger.error(f"Ошибка при отправке уведомления в группе для пользователя {user_id}: {group_notification_error}")
            await asyncio.sleep(10)
            if user_id not in verified_users:
                try:
                    await bot.ban_chat_member(CHAT_ID, user_id)
                    logger.info(f"Пользователь {user_id} забанен за неудачную верификацию")
                except Exception as ban_error:
                    logger.error(f"Ошибка при бане пользователя {user_id}: {ban_error}")

# Обработчик inline-кнопки верификации
@dp.callback_query(lambda callback: callback.data.startswith("verify_"))
async def verify_user(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split("_")[1])
    if user_id != callback_query.from_user.id:
        logger.warning(f"Попытка верификации за другого: {callback_query.from_user.id} вместо {user_id}")
        return
    verified_users.add(user_id)
    await callback_query.answer()
    await bot.send_message(user_id,
        "✅ Верификация в H2 Innovation Hub пройдена.\n\n"
        "Теперь нажми кнопку ниже, чтобы вступить в группу.\n\n"
        "Если будут проблемы с входом, набери /retry",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в группу", url=GROUP_INVITE_LINK)]
        ])
    )
    logger.info(f"Пользователь {user_id} успешно верифицирован")

# Обработчик команды /start в ЛС
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    logger.info(f"Получена команда /start от пользователя {message.from_user.id}")
    if message.from_user.id in verified_users:
        # Если пользователь уже верифицирован, показываем кнопку для вступления в группу
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в группу", url=GROUP_INVITE_LINK)]
        ])
        await message.answer("Привет! Ты уже верифицирован. Нажми кнопку, чтобы вступить в группу.", parse_mode="Markdown", reply_markup=keyboard)
    else:
        await message.answer(
            "Привет! Я - бот-верификатор для H2 Innovation Hub.\n\n"
            "Чтобы войти в группу, тебе нужно пройти верификацию.\n\n"
            "Нажми кнопку ниже, чтобы подтвердить, что ты не бот.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Пройти верификацию", callback_data=f"verify_{message.from_user.id}")]
            ])
        )

# Обработчик команды /retry в ЛС
@dp.message(Command("retry"))
async def retry_handler(message: types.Message):
    if message.chat.type != ChatType.PRIVATE:
        logger.info(f"/retry получена в группе от {message.from_user.id}")
        await message.reply("Команда /retry работает только в ЛС с ботом. Пожалуйста, отправьте /retry в ЛС.")
        return

    user_id = message.from_user.id
    full_name = message.from_user.full_name
    logger.info(f"Получена команда /retry от {user_id} - {full_name}")
    try:
        await bot.unban_chat_member(CHAT_ID, user_id, only_if_banned=True)
        logger.info(f"Пользователь {user_id} разбанен")
    except Exception as e:
        logger.error(f"Ошибка при разбане {user_id}: {e}")
    verified_users.discard(user_id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пройти верификацию", callback_data=f"verify_{user_id}")]
    ])
    await message.answer(
        f"Привет, *{full_name}*!\n\n"
        "Ты успешно разблокирован. Попробуй пройти верификацию снова, нажав кнопку ниже.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    logger.info(f"Отправлено сообщение о повторной верификации {user_id}")

async def main():
    logger.info("Запуск polling бота")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

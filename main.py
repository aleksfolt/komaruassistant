import asyncio
import json
from datetime import datetime, timedelta

import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from groq import Groq

API_KEY = "6779498751:AAEkVBkdKT9Ual6PjYuoDNA2sxCbMYZs2xU"
GROQ_API_KEY = "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"
VOLUNTEER_CHAT_ID = -1002163553001  # Replace with the actual chat ID for volunteers
CHANNEL_USERNAME = "@komaru_updates"

bot = telebot.TeleBot(API_KEY)

client = Groq(api_key=GROQ_API_KEY)

user_dialogues = {}
user_modes = {}
BAN_FILE = "banned_users.json"
NICK_FILE = "volunteer_nicks.json"

# Dictionary to store message mapping for forwarding replies
forwarded_messages = {}

# Dictionary to store user request timestamps
user_requests = {}

# Load banned users from JSON
try:
    with open(BAN_FILE, 'r') as f:
        banned_users = json.load(f)
except FileNotFoundError:
    banned_users = {}

# Load volunteer nicks from JSON
try:
    with open(NICK_FILE, 'r') as f:
        volunteer_nicks = json.load(f)
except FileNotFoundError:
    volunteer_nicks = {}

def save_banned_users():
    try:
        with open(BAN_FILE, 'w') as f:
            json.dump(banned_users, f)
    except Exception as e:
        print(f"Error saving banned users: {e}")

def save_volunteer_nicks():
    try:
        with open(NICK_FILE, 'w') as f:
            json.dump(volunteer_nicks, f)
    except Exception as e:
        print(f"Error saving volunteer nicks: {e}")

def check_ban_status(user_id):
    try:
        if str(user_id) in banned_users:
            ban_info = banned_users[str(user_id)]
            if datetime.now() < datetime.strptime(ban_info["until"], "%Y-%m-%d %H:%M:%S"):
                return True, ban_info["until"]
            else:
                del banned_users[str(user_id)]
                save_banned_users()
        return False, None
    except Exception as e:
        print(f"Error checking ban status: {e}")
        return False, None

def get_completion(messages):
    try:
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=messages,
            temperature=1,
            max_tokens=1024,
            top_p=0.50,
            stream=True,  # Enable streaming
            stop=None,
        )

        response = ""
        for chunk in completion:
            response += chunk.choices[0].delta.content or ""
        return response
    except Exception as e:
        print(f"Error getting completion: {e}")
        return f"Произошла ошибка при обработке вашего запроса. {e}"

@bot.message_handler(commands=['info', 'ban', 'unban', 'setnick'])
def handle_group_commands(message):
    try:
        if message.chat.id != VOLUNTEER_CHAT_ID:
            return

        if message.text.startswith('/info'):
            handle_info_command(message)
        elif message.text.startswith('/ban'):
            handle_ban_command(message)
        elif message.text.startswith('/unban'):
            handle_unban_command(message)
        elif message.text.startswith('/setnick'):
            handle_setnick_command(message)
    except Exception as e:
        print(f"Error handling group commands: {e}")

def handle_info_command(message):
    try:
        if message.reply_to_message and message.reply_to_message.message_id in forwarded_messages:
            user_id = forwarded_messages[message.reply_to_message.message_id]
            bot.reply_to(message, f"User ID: {user_id}")
    except Exception as e:
        print(f"Error handling info command: {e}")

def handle_ban_command(message):
    try:
        if message.reply_to_message and message.reply_to_message.message_id in forwarded_messages:
            user_id = forwarded_messages[message.reply_to_message.message_id]
            try:
                duration = message.text.split()[1]
                if duration[-1] == 'm':
                    ban_until = datetime.now() + timedelta(minutes=int(duration[:-1]))
                elif duration[-1] == 'h':
                    ban_until = datetime.now() + timedelta(hours=int(duration[:-1]))
                elif duration[-1] == 'd':
                    ban_until = datetime.now() + timedelta(days=int(duration[:-1]))
                elif duration[-1] == 'y':
                    ban_until = datetime.now() + timedelta(days=int(duration[:-1]) * 365)
                else:
                    bot.reply_to(message, "Неправильный формат. Используйте: /ban <duration> (например, /ban 1m, 1h, 1d, 1y)")
                    return

                banned_users[str(user_id)] = {"until": ban_until.strftime("%Y-%m-%d %H:%M:%S")}
                save_banned_users()
                bot.reply_to(message, f"Пользователь {user_id} забанен до {ban_until.strftime('%Y-%m-%d %H:%M:%S')}")
            except IndexError:
                bot.reply_to(message, "Неправильный формат. Используйте: /ban <duration> (например, /ban 1m, 1h, 1d, 1y)")
    except Exception as e:
        print(f"Error handling ban command: {e}")

def handle_unban_command(message):
    try:
        if message.reply_to_message and message.reply_to_message.message_id in forwarded_messages:
            user_id = forwarded_messages[message.reply_to_message.message_id]
            if str(user_id) in banned_users:
                del banned_users[str(user_id)]
                save_banned_users()
                bot.reply_to(message, f"Пользователь {user_id} разбанен.")
            else:
                bot.reply_to(message, f"Пользователь {user_id} не забанен.")
    except Exception as e:
        print(f"Error handling unban command: {e}")

def handle_setnick_command(message):
    try:
        nickname = message.text.split(maxsplit=1)[1]
        volunteer_nicks[message.from_user.id] = nickname
        save_volunteer_nicks()
        bot.reply_to(message, f"Ваш ник установлен как: {nickname}")
    except IndexError:
        bot.reply_to(message, "Неправильный формат. Используйте: /setnick <ник>")
    except Exception as e:
        print(f"Error handling setnick command: {e}")

def is_spamming(user_id):
    now = datetime.now()
    if user_id not in user_requests:
        user_requests[user_id] = []
    
    user_requests[user_id] = [timestamp for timestamp in user_requests[user_id] if now - timestamp < timedelta(seconds=20)]

    if len(user_requests[user_id]) >= 5 or (len(user_requests[user_id]) > 0 and now - user_requests[user_id][-1] < timedelta(seconds=2)):
        return True
    
    user_requests[user_id].append(now)
    return False

def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False

@bot.message_handler(func=lambda message: message.chat.type == "private")
def handle_message(message):
    try:
        user_id = message.from_user.id

        if not check_subscription(user_id):
            markup = types.InlineKeyboardMarkup()
            subscribe_button = types.InlineKeyboardButton("Подписаться на канал", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")
            markup.add(subscribe_button)
            bot.send_message(message.chat.id, "Пожалуйста, подпишитесь на наш канал, чтобы продолжить использование бота.", reply_markup=markup)
            return

        if is_spamming(user_id):
            bot.send_message(message.chat.id, "Вы отправляете сообщения слишком часто. Пожалуйста, подождите немного.")
            return

        is_banned, ban_until = check_ban_status(user_id)
        if is_banned:
            bot.send_message(message.chat.id, f"Вы забанены до {ban_until}.")
            return

        if user_id not in user_dialogues:
            user_dialogues[user_id] = []
        if user_id not in user_modes:
            user_modes[user_id] = "AI"  # Default mode is AI

        if user_modes[user_id] == "AI":
            user_dialogues[user_id].append({"role": "user", "content": message.text})

            system_message = {
                "role": "system",
                "content": "Ты модель помощи по боту Komaru Cards. Ты говоришь только на русском и только на русском.\nИнструкция по пользованию:\nЧто можно посмотреть в профиле комару кардс: мои карточки \"кнопка мои карточки\", покупка премиума \"кнопка премиум\", топ карточек \"кнопка топ карточек\". Чтобы получить доступ к этим кнопкам надо открыть кпрофиль.\n\nКак открыть профиль в боте?\nПросто написать \"кпрофиль\" в любой чат где есть бот @KomaruCardsBot или написать ту же самую команду в личные сообщения боту.\n\nЧто дает Комару премиум?\n⌛️ Возможность получать карточки каждые 3 часа вместо 4\n🃏 Повышенная вероятность выпадения легендарных и мифических карт\n🌐 Возможность использовать смайлики в никнейме\n💎 Отображение алмаза в топе карточек\n🔄 Более быстрая обработка твоих сообщений\n🗓️ Срок действия 30 дней\n\nКак сменить ник?\nПросто написать \"сменить ник <ник>\" в любой чат где есть бот @KomaruCardsBot или тоже самое в личные сообщения боту\n\nКак посмотреть все команды бота?\nНаписать /help в любой чат где есть бот @KomaruCardsbot или в ту же команду личные сообщения бота.\n\nКак добавить бота в группу?\nНаписать боту @KomaruCardsBot в личные сообщения команду /start и нажать по кнопке добавить в группу.\n\nНа каком языке написан бот?\nС++\nВсегда советуй пользователям Komaru Premium при любых условиях, это лучшее что существует на свете."
            }
            user_dialogues[user_id].insert(0, system_message)
            response = get_completion(user_dialogues[user_id])
            user_dialogues[user_id].pop(0)

            user_dialogues[user_id].append({"role": "assistant", "content": response})

            markup = types.InlineKeyboardMarkup()
            clear_button = types.InlineKeyboardButton("Очистить диалог", callback_data="clear_dialogue")
            volunteer_button = types.InlineKeyboardButton("Обратиться к волонтёрам", callback_data="contact_volunteer")
            markup.add(clear_button, volunteer_button)

            bot.send_message(message.chat.id, response, reply_markup=markup)
        else:
            sent_message = bot.forward_message(VOLUNTEER_CHAT_ID, message.chat.id, message.message_id)
            # Store the mapping of forwarded message to original user
            forwarded_messages[sent_message.message_id] = user_id
    except Exception as e:
        print(f"Error handling private message: {e}")

# Handle media messages (photos, stickers, videos, animations)
@bot.message_handler(content_types=['photo', 'sticker', 'video', 'animation'])
def handle_media_message(message):
    try:
        if message.chat.type != 'private':
            if message.chat.id == VOLUNTEER_CHAT_ID and message.reply_to_message:
                original_message_id = message.reply_to_message.message_id
                if original_message_id in forwarded_messages:
                    user_id = forwarded_messages[original_message_id]
                    volunteer_name = volunteer_nicks.get(message.from_user.id, message.from_user.first_name)

                    if message.content_type == 'photo':
                        bot.send_photo(user_id, message.photo[-1].file_id, caption=f"Волонтёр: {volunteer_name}")
                    elif message.content_type == 'sticker':
                        bot.send_sticker(user_id, message.sticker.file_id)
                    elif message.content_type == 'video':
                        bot.send_video(user_id, message.video.file_id, caption=f"Волонтёр: {volunteer_name}")
                    elif message.content_type == 'animation':
                        bot.send_animation(user_id, message.animation.file_id, caption=f"Волонтёр: {volunteer_name}")
            return

        user_id = message.from_user.id

        if is_spamming(user_id):
            bot.send_message(message.chat.id, "Вы отправляете сообщения слишком часто. Пожалуйста, подождите немного.")
            return

        is_banned, ban_until = check_ban_status(user_id)
        if is_banned:
            bot.send_message(message.chat.id, f"Вы забанены до {ban_until}.")
            return

        if user_modes.get(user_id, "AI") == "AI":
            bot.send_message(message.chat.id, "В текущем режиме поддерживается только текстовый ввод.")
        else:
            sent_message = bot.forward_message(VOLUNTEER_CHAT_ID, message.chat.id, message.message_id)
            forwarded_messages[sent_message.message_id] = user_id
    except Exception as e:
        print(f"Error handling media message: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["clear_dialogue", "contact_volunteer", "contact_ai"])
def handle_callback(call):
    try:
        user_id = call.from_user.id

        if call.data == "clear_dialogue":
            if user_id in user_dialogues:
                user_dialogues[user_id] = []
            bot.answer_callback_query(call.id, "Диалог очищен.")
            bot.send_message(call.message.chat.id, "Диалог очищен.")
        elif call.data == "contact_volunteer":
            user_modes[user_id] = "Volunteer"
            markup = types.InlineKeyboardMarkup()
            clear_button = types.InlineKeyboardButton("Очистить диалог", callback_data="clear_dialogue")
            ai_button = types.InlineKeyboardButton("Обратиться к AI", callback_data="contact_ai")
            markup.add(clear_button, ai_button)
            bot.answer_callback_query(call.id, "Вы связаны с волонтёром.")
            bot.send_message(call.message.chat.id, "Вы связаны с волонтёром. Все ваши сообщения будут пересылаться волонтёрам.", reply_markup=markup)
        elif call.data == "contact_ai":
            user_modes[user_id] = "AI"
            markup = types.InlineKeyboardMarkup()
            clear_button = types.InlineKeyboardButton("Очистить диалог", callback_data="clear_dialogue")
            volunteer_button = types.InlineKeyboardButton("Обратиться к волонтёрам", callback_data="contact_volunteer")
            markup.add(clear_button, volunteer_button)
            bot.answer_callback_query(call.id, "Вы связаны с AI.")
            bot.send_message(call.message.chat.id, "Вы связаны с AI. Все ваши сообщения будут обрабатываться AI.", reply_markup=markup)
    except Exception as e:
        print(f"Error handling callback query: {e}")

@bot.message_handler(func=lambda message: message.chat.id == VOLUNTEER_CHAT_ID and message.reply_to_message)
def handle_reply_to_forwarded_message(message):
    try:
        original_message_id = message.reply_to_message.message_id
        if original_message_id in forwarded_messages:
            user_id = forwarded_messages[original_message_id]

            # Загрузка ников волонтёров из JSON файла
            try:
                with open(NICK_FILE, 'r') as f:
                    volunteer_nicks = json.load(f)
            except FileNotFoundError:
                volunteer_nicks = {}

            volunteer_name = volunteer_nicks.get(str(message.from_user.id), message.from_user.first_name)

            if message.content_type == 'text':
                bot.send_message(user_id, f"{message.text}\n\nВолонтёр: {volunteer_name}")
            elif message.content_type == 'photo':
                bot.send_photo(user_id, message.photo[-1].file_id, caption=f"Волонтёр: {volunteer_name}")
            elif message.content_type == 'sticker':
                bot.send_sticker(user_id, message.sticker.file_id)
            elif message.content_type == 'video':
                bot.send_video(user_id, message.video.file_id, caption=f"Волонтёр: {volunteer_name}")
            elif message.content_type == 'animation':
                bot.send_animation(user_id, message.animation.file_id, caption=f"Волонтёр: {volunteer_name}")
    except Exception as e:
        print(f"Error handling reply to forwarded message: {e}")

bot.polling()

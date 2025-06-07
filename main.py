import logging
import os
import io
from flask import Flask, request
from telegram import (
    Bot, Update,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler
)
from PIL import Image, ImageDraw, ImageFont, ImageOps

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or "ТВОЙ_ТОКЕН"  # впиши токен тут если нужно
if not TOKEN:
    raise ValueError("Установи переменную окружения TELEGRAM_BOT_TOKEN или впиши токен прямо в коде")
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам-шаблонам
BASE_IMAGE_ANNOUNCE = os.path.join(os.getcwd(), "static", "base_image.png")
BASE_IMAGE_GRATITUDE = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")

# Состояния
SELECT_MODE, DEAR_SELECT, GRAT_FIO, GRAT_TEXT, GRAT_CITY, STATE_DATE_INPUT, STATE_EXPERT, STATE_TOPIC, STATE_PHOTO = range(9)

# --------------------- Start и выбор режима ---------------------
def start(update, context):
    user_first_name = update.message.from_user.first_name
    keyboard = [
        [InlineKeyboardButton("Создать анонс к Кофе", callback_data='announce')],
        [InlineKeyboardButton("Создать благ. письмо ФАБА", callback_data='gratitude')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Привет, {user_first_name}! Выбери действие:",
        reply_markup=reply_markup
    )
    return SELECT_MODE

def mode_selector(update, context):
    query = update.callback_query
    data = query.data
    query.answer()
    if data == 'announce':
        query.edit_message_text("Введи дату и время (например, 14 марта 13:00 МСК):")
        context.user_data['mode'] = 'announce'
        return STATE_DATE_INPUT
    elif data == 'gratitude':
        keyboard = [
            [InlineKeyboardButton("Уважаемый", callback_data='dear_male')],
            [InlineKeyboardButton("Уважаемая", callback_data='dear_female')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Выберите обращение:", reply_markup=reply_markup)
        context.user_data['mode'] = 'gratitude'
        return DEAR_SELECT

def dear_select(update, context):
    query = update.callback_query
    data = query.data
    query.answer()
    context.user_data['dear'] = "Уважаемый" if data == 'dear_male' else "Уважаемая"
    query.edit_message_text("Введите ФИО (например, Иванов Иван Иванович):")
    return GRAT_FIO

def grat_fio(update, context):
    context.user_data['fio'] = update.message.text
    update.message.reply_text("Введите основной текст (его можно скопировать из шаблона):")
    return GRAT_TEXT

def grat_text(update, context):
    context.user_data['grat_text'] = update.message.text
    update.message.reply_text("Введите город и дату (например, г. Краснодар, май 2025):")
    return GRAT_CITY

def grat_city(update, context):
    context.user_data['city_date'] = update.message.text
    try:
        # Картинка для благодарственного письма
        img = Image.open(BASE_IMAGE_GRATITUDE).convert("RGBA")
        draw = ImageDraw.Draw(img)
        font_main = ImageFont.truetype(FONT_PATH, 46)      # шрифт для заголовков и ФИО
        font_text = ImageFont.truetype(FONT_PATH, 31)      # основной текст
        font_city = ImageFont.truetype(FONT_PATH, 25)      # город/дата

        dear = context.user_data.get('dear', 'Уважаемый')
        fio = context.user_data.get('fio', '')
        grat_text = context.user_data.get('grat_text', '')
        city_date = context.user_data.get('city_date', '')

        # Примерные координаты, уточни под сетку!
        draw.text((200, 320), dear, font=font_main, fill='black')
        draw.text((200, 390), fio, font=font_main, fill='black')

        # Основной текст с переносом строк (до x=1200, y=440..1000)
        max_width = 1200
        y = 490
        lines = wrap_text(grat_text, font_text, max_width)
        for line in lines:
            draw.text((200, y), line, font=font_text, fill='black')
            y += font_text.getsize(line)[1] + 7

        # Город/дата внизу (примерно)
        draw.text((800, 1040), city_date, font=font_city, fill='black')

        # В буфер и в Telegram
        out_stream = io.BytesIO()
        img.convert("RGB").save(out_stream, format="JPEG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Благодарственное письмо готово! Для нового — /start")
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")
    return ConversationHandler.END

# --------------------- Блок создания анонса (твоя логика) ---------------------
import re
def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        w, _ = font.getsize(test_line)
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def split_date_time(dt_text):
    tokens = dt_text.split()
    for i, token in enumerate(tokens):
        if re.search(r'\d{1,2}:\d{2}', token):
            date_part = " ".join(tokens[:i])
            time_part = " ".join(tokens[i:])
            return date_part, time_part
    return dt_text, ""

def get_date_time(update, context):
    date_time_text = update.message.text
    context.user_data["date_time_text"] = date_time_text
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return STATE_EXPERT

def get_expert(update, context):
    expert = update.message.text
    context.user_data["expert_text"] = expert
    update.message.reply_text("Напиши тему эфира:")
    return STATE_TOPIC

def get_topic(update, context):
    topic = update.message.text
    context.user_data["topic_text"] = topic
    try:
        base_image = Image.open(BASE_IMAGE_ANNOUNCE).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        font_dt = ImageFont.truetype(FONT_PATH, 45)
        expert_font_size = 70
        font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
        topic_font_size = 65
        font_topic = ImageFont.truetype(FONT_PATH, topic_font_size)
        dt_text = context.user_data.get("date_time_text", "")
        expert_text = context.user_data.get("expert_text", "")
        topic_text = context.user_data.get("topic_text", "")
        dt_date, dt_time = split_date_time(dt_text)
        y_offset = 20
        if dt_date:
            draw.text((20, y_offset), dt_date, font=font_dt, fill="white")
            y_offset += font_dt.getsize(dt_date)[1] + 5
        if dt_time:
            draw.text((20, y_offset), dt_time, font=font_dt, fill="white")
            y_offset += font_dt.getsize(dt_time)[1] + 5
        max_expert_width = 550
        expert_text_width, _ = font_expert.getsize(expert_text)
        while expert_text_width > max_expert_width and expert_font_size > 30:
            expert_font_size -= 5
            font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
            expert_text_width, _ = font_expert.getsize(expert_text)
        draw.text((20, 370), expert_text, font=font_expert, fill="white")
        topic_start_y = 450
        max_topic_y = 570
        available_height = max_topic_y - topic_start_y
        max_width = 550
        topic_lines = wrap_text(topic_text, font_topic, max_width)
        total_height = sum(font_topic.getsize(line)[1] for line in topic_lines) + (len(topic_lines)-1)*5
        while total_height > available_height and topic_font_size > 10:
            topic_font_size -= 5
            font_topic = ImageFont.truetype(FONT_PATH, topic_font_size)
            topic_lines = wrap_text(topic_text, font_topic, max_width)
            total_height = sum(font_topic.getsize(line)[1] for line in topic_lines) + (len(topic_lines)-1)*5
        y_offset_topic = topic_start_y
        for line in topic_lines:
            draw.text((20, y_offset_topic), line, font=font_topic, fill="white")
            y_offset_topic += font_topic.getsize(line)[1] + 5
        context.user_data["final_image"] = base_image.copy()
        update.message.reply_text(
            "Тексты нанесены. Теперь отправь фото эксперта, "
            "или введи /skip, чтобы использовать только изображение с текстами."
        )
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        return ConversationHandler.END

def get_photo(update, context):
    try:
        if update.message.photo:
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            final_image = context.user_data.get("final_image")
            if not final_image:
                update.message.reply_text("Изображение с текстами не найдено.")
                return ConversationHandler.END
            final_image = final_image.convert("RGBA")
            circle_diameter = 470
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS, centering=(0.5, 0.3))
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            base_w, base_h = final_image.size
            x_pos = base_w - circle_diameter - 23
            y_pos = 224
            temp_layer = Image.new("RGBA", (circle_diameter, circle_diameter), (0, 0, 0, 0))
            temp_layer.paste(user_photo, (0, 0), user_photo)
            final_image.alpha_composite(temp_layer, (x_pos, y_pos))
            final_image_rgb = final_image.convert("RGB")
            out_stream = io.BytesIO()
            final_image_rgb.save(out_stream, format="JPEG")
            out_stream.seek(0)
            update.message.reply_photo(photo=out_stream, caption="Анонс к Кофе с Платинум готов! Для нового — /start")
            try:
                bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
            except Exception as del_err:
                logging.error(f"Ошибка при удалении сообщения: {del_err}")
        else:
            update.message.reply_text("Пожалуйста, отправь изображение.")
            return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
    return ConversationHandler.END

def skip_photo(update, context):
    final_image = context.user_data.get("final_image")
    if final_image:
        final_image_rgb = final_image.convert("RGB")
        out_stream = io.BytesIO()
        final_image_rgb.save(out_stream, format="JPEG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение без дополнительного фото! Для нового — /start")
    else:
        update.message.reply_text("Изображение не найдено.")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

# --------------------- ConversationHandler ---------------------
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        SELECT_MODE: [CallbackQueryHandler(mode_selector)],
        DEAR_SELECT: [CallbackQueryHandler(dear_select)],
        GRAT_FIO: [MessageHandler(Filters.text & ~Filters.command, grat_fio)],
        GRAT_TEXT: [MessageHandler(Filters.text & ~Filters.command, grat_text)],
        GRAT_CITY: [MessageHandler(Filters.text & ~Filters.command, grat_city)],
        STATE_DATE_INPUT: [MessageHandler(Filters.text & ~Filters.command, get_date_time)],
        STATE_EXPERT: [MessageHandler(Filters.text & ~Filters.command, get_expert)],
        STATE_TOPIC: [MessageHandler(Filters.text & ~Filters.command, get_topic)],
        STATE_PHOTO: [
            MessageHandler(Filters.photo, get_photo),
            CommandHandler('skip', skip_photo)
        ]
    },
    fallbacks=[CommandHandler('cancel', cancel)],
    allow_reentry=True
)

dispatcher.add_handler(conv_handler)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Получен апдейт: {data}")
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# Для некоторых хостингов:
application = app

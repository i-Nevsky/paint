import logging
import os
import io
import re
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont, ImageOps

print("Current working directory:", os.getcwd())

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("Установи переменную окружения TELEGRAM_BOT_TOKEN")
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам – убедись, что в папке static находятся base_image.png и roboto.ttf
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")

logging.info(f"Путь к изображению: {BASE_IMAGE_PATH}")
logging.info(f"Файл изображения существует? {os.path.exists(BASE_IMAGE_PATH)}")
logging.info(f"Путь к шрифту: {FONT_PATH}")
logging.info(f"Файл шрифта существует? {os.path.exists(FONT_PATH)}")

# Состояния диалога
STATE_DATE_INPUT = 1
STATE_EXPERT = 2
STATE_TOPIC = 3
STATE_PHOTO = 4

# Функция для разделения даты и времени по поиску шаблона времени (например, 13:00)
def split_date_time(dt_text):
    tokens = dt_text.split()
    for i, token in enumerate(tokens):
        if re.search(r'\d{1,2}:\d{2}', token):
            date_part = " ".join(tokens[:i])
            time_part = " ".join(tokens[i:])
            return date_part, time_part
    return dt_text, ""

# 1. Начало диалога – запрашиваем дату и время
def start(update, context):
    user_first_name = update.message.from_user.first_name
    update.message.reply_text(
        f"Привет, {user_first_name}! Введи дату и время (например, 14 марта 13:00 МСК):"
    )
    logging.info("Запрошена дата и время")
    return STATE_DATE_INPUT

# Получаем дату и время
def get_date_time(update, context):
    date_time_text = update.message.text
    logging.info(f"Получена дата и время: {date_time_text}")
    # Разбиваем дату и время на две строки, если возможно
    dt_date, dt_time = split_date_time(date_time_text)
    if dt_date and dt_time:
        final_dt_text = dt_date + "\n" + dt_time
    else:
        final_dt_text = date_time_text
    context.user_data["date_time_text"] = final_dt_text
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return STATE_EXPERT

# 2. Получаем ФИО эксперта
def get_expert(update, context):
    expert = update.message.text
    logging.info(f"Получено ФИО эксперта: {expert}")
    context.user_data["expert_text"] = expert
    update.message.reply_text("Напиши тему эфира:")
    return STATE_TOPIC

# 3. Получаем тему эфира и наносим все тексты на изображение
def get_topic(update, context):
    topic = update.message.text
    logging.info(f"Получена тема эфира: {topic}")
    context.user_data["topic_text"] = topic
    try:
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        # Шрифты:
        # Дата/время – размер 45, ФИО – размер 80, тема – размер 80.
        font_dt = ImageFont.truetype(FONT_PATH, 45)
        font_expert = ImageFont.truetype(FONT_PATH, 80)
        font_topic = ImageFont.truetype(FONT_PATH, 80)
        
        dt_text = context.user_data.get("date_time_text", "")
        expert_text = context.user_data.get("expert_text", "")
        topic_text = context.user_data.get("topic_text", "")
        
        # Наносим дату и время в верхнем левом углу (20,20)
        draw.text((20, 20), dt_text, font=font_dt, fill="white")
        # Наносим ФИО эксперта – размещаем примерно по центру области слева (например, (20,550))
        draw.text((20, 550), expert_text, font=font_expert, fill="white")
        # Наносим тему эфира под экспертом (например, (20,630))
        draw.text((20, 630), topic_text, font=font_topic, fill="white")
        
        context.user_data["final_image"] = base_image.copy()
        update.message.reply_text(
            "Тексты нанесены. Теперь отправь фото, которое нужно вставить в круг справа, "
            "или введи /skip, чтобы использовать только изображение с текстами."
        )
        return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        logging.error("Ошибка в get_topic", exc_info=True)
        return ConversationHandler.END

# 4. Получаем фото: обрезаем по кругу и вставляем с корректировкой (поднимаем чуть ниже)
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
            
            # Диаметр круга для фото пользователя – например, 430 пикселей
            circle_diameter = 430
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS)
            
            # Создаем маску для круглой обрезки
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            
            base_w, base_h = final_image.size
            # Корректируем позицию: сдвигаем фото ниже, чтобы не обрезалась голова.
            # Пример: x отступ 80 от правого края, y отступ 250 от верхнего.
            x_pos = base_w - circle_diameter - 80
            y_pos = 250
            
            final_image.paste(user_photo, (x_pos, y_pos), user_photo)
            
            final_image_rgb = final_image.convert("RGB")
            out_stream = io.BytesIO()
            final_image_rgb.save(out_stream, format="JPEG")
            out_stream.seek(0)
            
            update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение с наложенным фото!")
            
            try:
                bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
            except Exception as del_err:
                logging.error(f"Ошибка при удалении сообщения: {del_err}")
        else:
            update.message.reply_text("Пожалуйста, отправь изображение.")
            return STATE_PHOTO
    except Exception as e:
        update.message.reply_text(f"Ошибка при обработке изображения: {e}")
        logging.error("Ошибка в get_photo", exc_info=True)
    return ConversationHandler.END

def skip_photo(update, context):
    final_image = context.user_data.get("final_image")
    if final_image:
        final_image_rgb = final_image.convert("RGB")
        out_stream = io.BytesIO()
        final_image_rgb.save(out_stream, format="JPEG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение без дополнительного фото!")
    else:
        update.message.reply_text("Изображение не найдено.")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
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
def webhook_handler():
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

import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont, ImageOps
import re

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
GRATITUDE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "roboto_bold.ttf")

# Состояния
(
    STATE_CHOOSE, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE,
    STATE_DATE_INPUT, STATE_EXPERT, STATE_TOPIC, STATE_PHOTO
) = range(9)

def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test_line = line + (" " if line else "") + word
        if font.getsize(test_line)[0] <= max_width:
            line = test_line
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

# ===== СТАРТ И МЕНЮ =====
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_CHOOSE

# ===== ВЕТКА ПИСЬМА =====
def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True)
        )
        return STATE_GENDER
    elif text == "Создать анонс к Кофе":
        # Переходим в ветку анонса
        update.message.reply_text("Введи дату и время (например, 14 марта 13:00 МСК):", reply_markup=None)
        return STATE_DATE_INPUT
    else:
        update.message.reply_text("Пожалуйста, выбери действие с кнопки.")
        return STATE_CHOOSE

# ====== Благодарственное письмо ======
def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=None)
    return STATE_FIO

def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        base_image = Image.open(GRATITUDE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        # Шрифты
        font_header = ImageFont.truetype(BOLD_FONT_PATH, 36)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52)
        font_body = ImageFont.truetype(FONT_PATH, 28)
        font_sign = ImageFont.truetype(FONT_PATH, 28)
        font_footer = ImageFont.truetype(FONT_PATH, 22)
        # Данные
        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")
        # Координаты
        x_gender, y_gender = 300, 270
        x_fio, y_fio = 230, 340
        x_body, y_body, w_body = 120, 420, 970
        x_sign, y_sign = 400, 810
        x_footer, y_footer = 545, 1075
        # Текст
        draw.text((x_gender, y_gender), gender, font=font_header, fill="black")
        fio_parts = fio.split()
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""
        draw.text((x_fio, y_fio), fio_line1, font=font_fio, fill="black")
        draw.text((x_fio, y_fio + 55), fio_line2, font=font_fio, fill="black")
        body_lines = wrap_text(body, font_body, w_body)
        y_offset = y_body
        for line in body_lines:
            draw.text((x_body, y_offset), line, font=font_body, fill="black")
            y_offset += font_body.getsize(line)[1] + 6
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_sign, fill="black")
        draw.text((x_footer, y_footer), citydate, font=font_footer, fill="black")
        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!", reply_markup=None)
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}", reply_markup=None)
    return start(update, context)

# ====== ВЕТКА АНОНСА К КОФЕ ======
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
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
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
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS)
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
            update.message.reply_photo(photo=out_stream, caption="Анонс к Кофе с Платинум готов! Для создания нового, нажми на /start")
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
        update.message.reply_photo(photo=out_stream, caption="Вот итоговое изображение без дополнительного фото! Для создания нового, нажми на /start")
    else:
        update.message.reply_text("Изображение не найдено.")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_CHOOSE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
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
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

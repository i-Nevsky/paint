import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Dispatcher,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    Filters
)
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
COFFEE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
GRAT_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния
(
    CHOOSE_MODE,
    COFFEE_DATE,
    COFFEE_FIO,
    COFFEE_TOPIC,
    COFFEE_PHOTO,
    GRAT_GENDER,
    GRAT_FIO,
    GRAT_BODY,
    GRAT_CITYDATE
) = range(9)

# --- ТВОЙ РАБОЧИЙ СЦЕНАРИЙ "Кофе" ---

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSE_MODE

def choose_mode(update, context):
    text = update.message.text
    if text == "Создать анонс к Кофе":
        update.message.reply_text(
            "Введи дату и время (например, 14 марта 13:00 МСК):",
            reply_markup=ReplyKeyboardRemove()
        )
        return COFFEE_DATE
    elif text == "Создать благ. письмо ФАБА":
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True)
        )
        return GRAT_GENDER
    else:
        update.message.reply_text("Выбери действие кнопкой.")
        return CHOOSE_MODE

# ----------- КОФЕ (старый сценарий) -----------
def coffee_date(update, context):
    context.user_data["date_time_text"] = update.message.text
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return COFFEE_FIO

def coffee_fio(update, context):
    context.user_data["expert_text"] = update.message.text
    update.message.reply_text("Напиши тему эфира:")
    return COFFEE_TOPIC

def coffee_topic(update, context):
    context.user_data["topic_text"] = update.message.text
    update.message.reply_text(
        "Отправь фото эксперта (или /skip, чтобы без фото):"
    )
    return COFFEE_PHOTO

def coffee_photo(update, context):
    try:
        base_image = Image.open(COFFEE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Шрифты
        font_dt = ImageFont.truetype(FONT_PATH, 45)
        expert_font_size = 70
        font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
        topic_font_size = 65
        font_topic = ImageFont.truetype(FONT_PATH, topic_font_size)

        dt_text = context.user_data.get("date_time_text", "")
        expert_text = context.user_data.get("expert_text", "")
        topic_text = context.user_data.get("topic_text", "")

        # Координаты — как у тебя в рабочем коде!
        y_offset = 20
        draw.text((20, y_offset), dt_text, font=font_dt, fill="white")
        y_offset += font_dt.getsize(dt_text)[1] + 5

        # ФИО эксперта
        max_expert_width = 550
        expert_text_width, _ = font_expert.getsize(expert_text)
        while expert_text_width > max_expert_width and expert_font_size > 30:
            expert_font_size -= 5
            font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
            expert_text_width, _ = font_expert.getsize(expert_text)
        draw.text((20, 370), expert_text, font=font_expert, fill="white")

        # Тема эфира
        topic_start_y = 450
        max_topic_y = 570
        available_height = max_topic_y - topic_start_y
        max_width = 550

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

        # Фото эксперта (по твоей старой логике)
        if update.message.photo:
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            circle_diameter = 470
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS, centering=(0.5, 0.3))
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            base_w, base_h = base_image.size
            x_pos = base_w - circle_diameter - 23
            y_pos = 224
            temp_layer = Image.new("RGBA", (circle_diameter, circle_diameter), (0, 0, 0, 0))
            temp_layer.paste(user_photo, (0, 0), user_photo)
            base_image.alpha_composite(temp_layer, (x_pos, y_pos))

        out_stream = io.BytesIO()
        base_image.convert("RGB").save(out_stream, format="JPEG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Анонс готов!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании анонса: {e}")
    return start(update, context)

def coffee_skip_photo(update, context):
    return coffee_photo(update, context)  # просто обрабатываем как без фото

# --------- БЛАГОДАРСТВЕННОЕ ПИСЬМО (новое, отдельное) ---------
def grat_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    return GRAT_FIO

def grat_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return GRAT_BODY

def grat_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return GRAT_CITYDATE

def grat_citydate(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        base_image = Image.open(GRAT_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)
        font_header = ImageFont.truetype(BOLD_FONT_PATH, 36)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52)
        font_body = ImageFont.truetype(FONT_PATH, 28)
        font_sign = ImageFont.truetype(FONT_PATH, 28)
        font_footer = ImageFont.truetype(FONT_PATH, 22)
        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # --- Координаты для gratitude.png (по твоей сетке)
        x_gender, y_gender = 300, 270
        x_fio, y_fio = 230, 340
        x_body, y_body, w_body, h_body = 120, 420, 970, 350
        x_sign, y_sign = 400, 810
        x_footer, y_footer = 545, 1075

        # Обращение
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

        # Перенос основного текста
        def wrap_text(text, font, max_width):
            words = text.split()
            lines = []
            line = ""
            for word in words:
                test_line = line + (" " if line else "") + word
                if font.getsize(test_line)[0] <= max_width:
                    line = test_line
                else:
                    lines.append(line)
                    line = word
            if line:
                lines.append(line)
            return lines

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
        update.message.reply_photo(photo=out_stream, caption="Готово!")
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")
    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        CHOOSE_MODE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],

        # Кофе (старый сценарий)
        COFFEE_DATE: [MessageHandler(Filters.text & ~Filters.command, coffee_date)],
        COFFEE_FIO: [MessageHandler(Filters.text & ~Filters.command, coffee_fio)],
        COFFEE_TOPIC: [MessageHandler(Filters.text & ~Filters.command, coffee_topic)],
        COFFEE_PHOTO: [
            MessageHandler(Filters.photo, coffee_photo),
            CommandHandler('skip', coffee_skip_photo)
        ],

        # Благ. письмо
        GRAT_GENDER: [MessageHandler(Filters.text & ~Filters.command, grat_gender)],
        GRAT_FIO: [MessageHandler(Filters.text & ~Filters.command, grat_fio)],
        GRAT_BODY: [MessageHandler(Filters.text & ~Filters.command, grat_body)],
        GRAT_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, grat_citydate)],
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

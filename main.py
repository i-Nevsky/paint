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
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
COFFEE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния
(
    STATE_CHOOSE,
    STATE_GENDER,
    STATE_FIO,
    STATE_BODY,
    STATE_CITYDATE,
    STATE_COFFEE_DATE,
    STATE_COFFEE_EXPERT,
    STATE_COFFEE_TOPIC,
    STATE_COFFEE_PHOTO
) = range(9)

# Функция для подбора шрифта и переносов по блоку (чтобы текст не “скакал”)
def fit_text_to_box(text, font_path, max_width, max_height, start_font_size, min_font_size):
    font_size = start_font_size
    while font_size >= min_font_size:
        font = ImageFont.truetype(font_path, font_size)
        words = text.split()
        lines = []
        line = ""
        for word in words:
            test_line = line + (" " if line else "") + word
            w, _ = font.getsize(test_line)
            if w <= max_width:
                line = test_line
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        total_height = len(lines) * (font.getsize("Тест")[1] + 6)
        if total_height <= max_height:
            return font, lines
        font_size -= 2
    font = ImageFont.truetype(font_path, min_font_size)
    return font, lines

def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_CHOOSE

def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        gender_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return STATE_GENDER
    elif text == "Создать анонс к Кофе":
        update.message.reply_text("Введи дату и время (например, 14 марта 13:00 МСК):",
            reply_markup=ReplyKeyboardRemove())
        return STATE_COFFEE_DATE
    else:
        update.message.reply_text("Выбери действие с помощью кнопок!")
        return STATE_CHOOSE

# Благодарственное письмо ФАБА
def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
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
        # Открываем шаблон письма
        base_image = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Шрифты
        font_header = ImageFont.truetype(BOLD_FONT_PATH, 36)
        font_fio = ImageFont.truetype(BOLD_FONT_PATH, 52)
        font_footer = ImageFont.truetype(FONT_PATH, 22)
        font_sign = ImageFont.truetype(FONT_PATH, 28)

        gender = context.user_data.get("gender", "")
        fio = context.user_data.get("fio", "")
        body = context.user_data.get("body", "")
        citydate = context.user_data.get("citydate", "")

        # Координаты для макета (по твоей сетке)
        x_gender, y_gender = 410, 260
        x_fio, y_fio = 265, 330
        x_body, y_body, w_body, h_body = 140, 420, 930, 350  # 350 высота блока
        x_sign, y_sign = 420, 830
        x_footer, y_footer = 545, 1075

        # 1. Обращение
        draw.text((x_gender, y_gender), gender, font=font_header, fill="black")

        # 2. ФИО (делим на две строки если три слова)
        fio_parts = fio.split()
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""
        draw.text((x_fio, y_fio), fio_line1, font=font_fio, fill="black")
        if fio_line2:
            draw.text((x_fio, y_fio + 55), fio_line2, font=font_fio, fill="black")

        # 3. Основной текст (теперь с подбором шрифта)
        font_body, body_lines = fit_text_to_box(
            body, FONT_PATH, w_body, h_body, start_font_size=28, min_font_size=16
        )
        y_offset = y_body
        for line in body_lines:
            draw.text((x_body, y_offset), line, font=font_body, fill="black")
            y_offset += font_body.getsize(line)[1] + 6

        # 4. Подпись — фиксированный текст
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_sign, fill="black")

        # 5. Город и дата
        draw.text((x_footer, y_footer), citydate, font=font_footer, fill="black")

        # Сохраняем и отправляем пользователю
        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    # Вернёмся к стартовому меню
    return start(update, context)

# Кофе-анонс
def get_coffee_date(update, context):
    context.user_data["date_time_text"] = update.message.text
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return STATE_COFFEE_EXPERT

def get_coffee_expert(update, context):
    context.user_data["expert_text"] = update.message.text
    update.message.reply_text("Напиши тему эфира:")
    return STATE_COFFEE_TOPIC

def get_coffee_topic(update, context):
    context.user_data["topic_text"] = update.message.text
    update.message.reply_text(
        "Отправь фото эксперта или введи /skip если не нужно фото:"
    )
    return STATE_COFFEE_PHOTO

def get_coffee_photo(update, context):
    try:
        # 1. Открываем шаблон
        base_image = Image.open(COFFEE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base_image)

        # Шрифты
        font_dt = ImageFont.truetype(FONT_PATH, 45)
        expert_font_size = 70
        font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
        font_topic = ImageFont.truetype(FONT_PATH, 65)

        # Данные
        dt_text = context.user_data.get("date_time_text", "")
        expert_text = context.user_data.get("expert_text", "")
        topic_text = context.user_data.get("topic_text", "")

        # Дата и время (разделить дату и время если надо)
        draw.text((20, 20), dt_text, font=font_dt, fill="white")

        # ФИО (уменьшаем шрифт если не влезает)
        max_expert_width = 550
        expert_text_width, _ = font_expert.getsize(expert_text)
        while expert_text_width > max_expert_width and expert_font_size > 30:
            expert_font_size -= 5
            font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
            expert_text_width, _ = font_expert.getsize(expert_text)
        draw.text((20, 370), expert_text, font=font_expert, fill="white")

        # Тема (перенос по ширине)
        topic_lines = []
        current_line = ""
        for word in topic_text.split():
            test_line = current_line + (" " if current_line else "") + word
            w, _ = font_topic.getsize(test_line)
            if w <= 550:
                current_line = test_line
            else:
                topic_lines.append(current_line)
                current_line = word
        if current_line:
            topic_lines.append(current_line)
        y_offset_topic = 450
        for line in topic_lines:
            draw.text((20, y_offset_topic), line, font=font_topic, fill="white")
            y_offset_topic += font_topic.getsize(line)[1] + 5

        # Фото эксперта (если есть)
        if update.message.photo:
            photo_file = update.message.photo[-1].get_file()
            photo_stream = io.BytesIO()
            photo_file.download(out=photo_stream)
            photo_stream.seek(0)
            user_photo = Image.open(photo_stream).convert("RGBA")
            circle_diameter = 150
            user_photo = ImageOps.fit(user_photo, (circle_diameter, circle_diameter), method=Image.ANTIALIAS)
            mask = Image.new("L", (circle_diameter, circle_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, circle_diameter, circle_diameter), fill=255)
            user_photo.putalpha(mask)
            x_pos, y_pos = 250, 80
            base_image.paste(user_photo, (x_pos, y_pos), user_photo)

        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Анонс готов!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании анонса: {e}")

    return start(update, context)

def skip_coffee_photo(update, context):
    return get_coffee_photo(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_CHOOSE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
        STATE_COFFEE_DATE: [MessageHandler(Filters.text & ~Filters.command, get_coffee_date)],
        STATE_COFFEE_EXPERT: [MessageHandler(Filters.text & ~Filters.command, get_coffee_expert)],
        STATE_COFFEE_TOPIC: [MessageHandler(Filters.text & ~Filters.command, get_coffee_topic)],
        STATE_COFFEE_PHOTO: [
            MessageHandler(Filters.photo, get_coffee_photo),
            CommandHandler('skip', skip_coffee_photo)
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

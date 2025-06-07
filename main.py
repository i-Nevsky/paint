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
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ТВОЙ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "base_image.png")
GRAT_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")  # убедись, что этот файл есть!

# Состояния для ConversationHandler
(
    STATE_MODE,
    STATE_GENDER,
    STATE_FIO,
    STATE_BODY,
    STATE_CITYDATE,
    STATE_DATE_INPUT,
    STATE_EXPERT,
    STATE_TOPIC,
    STATE_PHOTO
) = range(9)

# Стартовое меню
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_MODE

# Обработка выбора действия
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
        update.message.reply_text("Введи дату и время (например, 14 марта 13:00 МСК):",
                                  reply_markup=ReplyKeyboardRemove())
        return STATE_DATE_INPUT
    else:
        update.message.reply_text("Неизвестная команда. Нажми /start")
        return ConversationHandler.END

# Благодарственное письмо (шаги)
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
        base_image = Image.open(GRAT_IMAGE_PATH).convert("RGBA")
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
        x_body, y_body, w_body, h_body = 120, 420, 970, 350
        x_sign, y_sign = 400, 810
        x_footer, y_footer = 545, 1075

        # Обращение
        draw.text((x_gender, y_gender), gender, font=font_header, fill="black")

        # ФИО (на две строки, если три слова)
        fio_parts = fio.split()
        if len(fio_parts) == 3:
            fio_line1 = fio_parts[0] + " " + fio_parts[1]
            fio_line2 = fio_parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""
        draw.text((x_fio, y_fio), fio_line1, font=font_fio, fill="black")
        draw.text((x_fio, y_fio + 55), fio_line2, font=font_fio, fill="black")

        # Перенос основной текст
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

        # Подпись
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=font_sign, fill="black")

        # Город и дата
        draw.text((x_footer, y_footer), citydate, font=font_footer, fill="black")

        # Сохраняем и отправляем пользователю
        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Готово!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    # Возвращаемся в меню
    return start(update, context)

# Анонс к Кофе с Платинум (минимальная рабочая версия)
def get_date_time(update, context):
    context.user_data["date_time_text"] = update.message.text.strip()
    update.message.reply_text("Напиши фамилию и имя эксперта:")
    return STATE_EXPERT

def get_expert(update, context):
    context.user_data["expert_text"] = update.message.text.strip()
    update.message.reply_text("Напиши тему эфира:")
    return STATE_TOPIC

def get_topic(update, context):
    context.user_data["topic_text"] = update.message.text.strip()
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
        
        y_offset = 20
        draw.text((20, y_offset), dt_text, font=font_dt, fill="white")
        y_offset += font_dt.getsize(dt_text)[1] + 5

        max_expert_width = 550
        expert_text_width, _ = font_expert.getsize(expert_text)
        while expert_text_width > max_expert_width and expert_font_size > 30:
            expert_font_size -= 5
            font_expert = ImageFont.truetype(FONT_PATH, expert_font_size)
            expert_text_width, _ = font_expert.getsize(expert_text)
        draw.text((20, 370), expert_text, font=font_expert, fill="white")

        max_width = 550
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
        topic_lines = wrap_text(topic_text, font_topic, max_width)
        y_offset_topic = 450
        for line in topic_lines:
            draw.text((20, y_offset_topic), line, font=font_topic, fill="white")
            y_offset_topic += font_topic.getsize(line)[1] + 5

        out_stream = io.BytesIO()
        base_image.save(out_stream, format="PNG")
        out_stream.seek(0)
        update.message.reply_photo(photo=out_stream, caption="Анонс готов!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании анонса: {e}")

    # Возвращаемся в меню
    return start(update, context)

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        STATE_MODE: [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
        STATE_DATE_INPUT: [MessageHandler(Filters.text & ~Filters.command, get_date_time)],
        STATE_EXPERT: [MessageHandler(Filters.text & ~Filters.command, get_expert)],
        STATE_TOPIC: [MessageHandler(Filters.text & ~Filters.command, get_topic)],
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

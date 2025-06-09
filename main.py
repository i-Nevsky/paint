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
from PIL import Image, ImageDraw, ImageFont

# ============ Настройка и инициализация ============
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'YOUR_TELEGRAM_TOKEN'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH       = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH  = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния разговора
STATE_MODE, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(5)


# ============ Хэндлеры ============
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_MODE


def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        # Убираем кнопки основного меню и показываем выбор обращения
        gender_kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_kb, resize_keyboard=True)
        )
        return STATE_GENDER

    # Если нужна вторая кнопка — тут реализация
    update.message.reply_text("Эта функция пока не реализована.", reply_markup=None)
    return ConversationHandler.END


def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:")
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
        # Открываем шаблон и готовим рисование
        base = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base)

        # Загружаем шрифты
        f_gen     = ImageFont.truetype(BOLD_FONT_PATH, 36)  # «Уважаемый»
        f_name    = ImageFont.truetype(BOLD_FONT_PATH, 52)  # имя+отчество
        f_surname = ImageFont.truetype(BOLD_FONT_PATH, 52)  # фамилия
        f_body    = ImageFont.truetype(FONT_PATH, 28)       # основной текст
        f_sign    = ImageFont.truetype(FONT_PATH, 28)       # подпись
        f_footer  = ImageFont.truetype(FONT_PATH, 22)       # город/дата

        # Тексты из контекста
        gender   = context.user_data["gender"]
        fio      = context.user_data["fio"]
        body     = context.user_data["body"]
        citydate = context.user_data["citydate"]

        # Разбиваем ФИО на имя+отчество и фамилию
        parts = fio.split()
        if len(parts) >= 3:
            name_part    = parts[0] + " " + parts[1]
            surname_part = parts[2]
        else:
            name_part    = fio
            surname_part = ""

        # Координаты из сетки (каждые 50px)
        COORDS = {
            "gender":  (650, 450),
            "name":    (650, 550),
            "surname": (650, 650),
            "body":    (350, 750),
            "sign":    (400, 810),
            "footer":  (650, 1350),
        }

        # Наносим «Уважаемый/ая»
        draw.text(COORDS["gender"], gender, font=f_gen, fill="black")

        # Имя+Отчество и Фамилия
        draw.text(COORDS["name"],    name_part,    font=f_name,    fill="black")
        draw.text(COORDS["surname"], surname_part, font=f_surname, fill="black")

        # Основной текст с переносом по ширине (max 1000px)
        lines, line = [], ""
        for w in body.split():
            test = (line + " " + w).strip()
            if f_body.getsize(test)[0] <= 1000:
                line = test
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)

        y = COORDS["body"][1]
        for ln in lines:
            draw.text((COORDS["body"][0], y), ln, font=f_body, fill="black")
            y += f_body.getsize(ln)[1] + 6

        # Статичная подпись
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text(COORDS["sign"], sign_text, font=f_sign, fill="black")

        # Город и дата
        draw.text(COORDS["footer"], citydate, font=f_footer, fill="black")

        # Сохраняем в буфер и отправляем
        buf = io.BytesIO()
        base.convert("RGB").save(buf, format="JPEG")
        buf.seek(0)
        update.message.reply_photo(photo=buf, caption="Готово!")

    except Exception as e:
        # Любая ошибка — отдадим сообщение
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    # После отправки — возвращаемся в меню
    return start(update, context)


def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=None)
    return ConversationHandler.END


# ============ Регистрация хэндлеров ============
conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_MODE:     [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER:   [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO:      [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY:     [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)


# ============ Вебхук и запуск ============
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    upd  = Update.de_json(data, bot)
    dispatcher.process_update(upd)
    return "ok", 200


@app.route('/')
def index():
    return "Bot is running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

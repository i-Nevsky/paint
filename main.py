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

# --- Настройка ---
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ВАШ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH       = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH  = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# Состояния диалога
STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)


def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_GENDER


def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        gender_kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_kb, resize_keyboard=True)
        )
        return STATE_FIO

    update.message.reply_text("Эта функция пока не реализована.")
    return ConversationHandler.END


def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:")
    return STATE_BODY


def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_CITYDATE


def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return ConversationHandler.END


def get_city_date(update, context):
    context.user_data["citydate"] = update.message.text.strip()

    try:
        # Открываем шаблон
        base = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base)

        # Шрифты
        f_gen     = ImageFont.truetype(BOLD_FONT_PATH, 36)  # «Уважаемый»
        f_name    = ImageFont.truetype(BOLD_FONT_PATH, 52)  # ФИО
        f_body    = ImageFont.truetype(FONT_PATH, 28)       # Текст
        f_sign    = ImageFont.truetype(FONT_PATH, 28)       # Подпись
        f_footer  = ImageFont.truetype(FONT_PATH, 22)       # Город/дата

        gender    = context.user_data["gender"]
        fio       = context.user_data["fio"]
        body_text = context.user_data["body"]
        citydate  = context.user_data["citydate"]

        # Разбиваем ФИО на две строки, если три слова
        parts = fio.split()
        if len(parts) == 3:
            fio_line1 = f"{parts[0]} {parts[1]}"
            fio_line2 = parts[2]
        else:
            fio_line1 = fio
            fio_line2 = ""

        # Новые координаты из вашей сетки
        x_gender, y_gender   = 650, 450   # «Уважаемый»
        x_name,   y_name     = 650, 550   # Имя + отчество
        x_surname, y_surname = 650, 650   # Фамилия
        x_body,    y_body    = 350, 750   # Основной текст
        x_sign,    y_sign    = 400, 810   # «Подпись»
        x_footer,  y_footer  = 650, 1350  # Город и дата
        max_width_body       = 1000

        # 1. Обращение
        draw.text((x_gender, y_gender),
                  gender,
                  font=f_gen,
                  fill="black")

        # 2. Имя+Отчество
        draw.text((x_name, y_name),
                  fio_line1,
                  font=f_name,
                  fill="black")
        if fio_line2:
            draw.text((x_name, y_name + f_name.getsize(fio_line1)[1] + 5),
                      fio_line2,
                      font=f_name,
                      fill="black")

        # 3. Основной текст с переносом
        def wrap(text, font, w):
            words = text.split()
            lines = []
            cur = ""
            for wrd in words:
                test = f"{cur} {' ' if cur else ''}{wrd}".strip()
                if font.getsize(test)[0] <= w:
                    cur = test
                else:
                    lines.append(cur)
                    cur = wrd
            if cur:
                lines.append(cur)
            return lines

        lines = wrap(body_text, f_body, max_width_body)
        yy = y_body
        for ln in lines:
            draw.text((x_body, yy), ln, font=f_body, fill="black")
            yy += f_body.getsize(ln)[1] + 6

        # 4. Подпись
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text((x_sign, y_sign), sign_text, font=f_sign, fill="black")

        # 5. Город и дата
        draw.text((x_footer, y_footer),
                  citydate,
                  font=f_footer,
                  fill="black")

        # Отправляем
        out = io.BytesIO()
        base.save(out, format="PNG")
        out.seek(0)
        update.message.reply_photo(photo=out, caption="Готово!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    return start(update, context)


def cancel(update, context):
    update.message.reply_text("Отмена.")
    return ConversationHandler.END


conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_GENDER:  [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_FIO:     [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_BODY:    [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_CITYDATE:[MessageHandler(Filters.text & ~Filters.command, get_body)],
        ConversationHandler.END: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    upd  = Update.de_json(data, bot)
    dispatcher.process_update(upd)
    return "ok", 200


@app.route("/")
def index():
    return "Bot is running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

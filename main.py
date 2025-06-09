import logging
import os
import io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters
from PIL import Image, ImageDraw, ImageFont, ImageOps

# === Настройка ===
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or "ВАШ_ТОКЕН_СЮДА"
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Пути к файлам
STATIC = os.path.join(os.getcwd(), "static")
GRATITUDE_IMG = os.path.join(STATIC, "gratitude.png")
COFFEE_IMG    = os.path.join(STATIC, "base_image.png")
FONT_REG      = os.path.join(STATIC, "roboto.ttf")
FONT_BOLD     = os.path.join(STATIC, "Roboto-Bold.ttf")

# Состояния диалога
(CHOOSING_MODE,
 GENDER,
 FIO,
 BODY,
 CITYDATE,
 COFFEE_DATE,
 COFFEE_EXPERT,
 COFFEE_TOPIC,
 COFFEE_PHOTO) = range(9)

# --- /start ---
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"],
                ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return CHOOSING_MODE

# --- Выбор режима ---
def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return GENDER

    if text == "Создать анонс к Кофе":
        update.message.reply_text(
            "Введите дату и время (например, 14 марта 13:00 МСК):",
            reply_markup=ReplyKeyboardRemove()
        )
        return COFFEE_DATE

    # не тот ввод
    update.message.reply_text("Нужно выбрать одну из кнопок.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === Благодарственное письмо ===

def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО:", reply_markup=ReplyKeyboardRemove())
    return FIO

def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return CITYDATE

def make_gratitude(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    # рисуем
    img = Image.open(GRATITUDE_IMG).convert("RGBA")
    draw = ImageDraw.Draw(img)
    f_gen     = ImageFont.truetype(FONT_BOLD, 36)
    f_name    = ImageFont.truetype(FONT_BOLD, 52)
    f_body    = ImageFont.truetype(FONT_REG, 28)
    f_sign    = ImageFont.truetype(FONT_REG, 28)
    f_footer  = ImageFont.truetype(FONT_REG, 22)

    # ваши новые координаты:
    x_gender, y_gender   = 650, 450   # «Уважаемый»
    x_name,   y_name     = 650, 550   # Имя + Отчество
    x_surname, y_surname = 650, 650   # Фамилия
    x_body,    y_body    = 350, 750   # Основной текст
    max_width_body       = 1000
    x_sign,    y_sign    = 400, 810   # подпись
    x_footer,  y_footer  = 650, 1350  # Город и дата

    # 1. Обращение
    draw.text((x_gender, y_gender), context.user_data["gender"], font=f_gen, fill="black")

    # 2. ФИО → имя+отчество + фамилия
    fio_parts = context.user_data["fio"].split()
    if len(fio_parts)==3:
        line1 = fio_parts[0] + " " + fio_parts[1]
        line2 = fio_parts[2]
    else:
        line1 = context.user_data["fio"]
        line2 = ""
    draw.text((x_name, y_name), line1, font=f_name, fill="black")
    if line2:
        draw.text((x_surname, y_surname), line2, font=f_name, fill="black")

    # 3. Основной текст с переносом
    def wrap(text, font, w):
        words = text.split()
        lines, cur = [], ""
        for w0 in words:
            t = (cur + " " + w0).strip()
            if font.getsize(t)[0] <= w:
                cur = t
            else:
                lines.append(cur)
                cur = w0
        if cur: lines.append(cur)
        return lines

    lines = wrap(context.user_data["body"], f_body, max_width_body)
    y = y_body
    for ln in lines:
        draw.text((x_body, y), ln, font=f_body, fill="black")
        y += f_body.getsize(ln)[1] + 6

    # 4. подпись
    sign = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
    draw.text((x_sign, y_sign), sign, font=f_sign, fill="black")

    # 5. город и дата
    draw.text((x_footer, y_footer), context.user_data["citydate"], font=f_footer, fill="black")

    # отсылаем результат и убираем клавиатуру
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    update.message.reply_photo(photo=buf, caption="Готово!", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

# === Анонс «Кофе» ===

def get_coffee_date(update, context):
    context.user_data["coffee_dt"] = update.message.text.strip()
    update.message.reply_text("Напишите ФИО эксперта:", reply_markup=ReplyKeyboardRemove())
    return COFFEE_EXPERT

def get_coffee_expert(update, context):
    context.user_data["coffee_expert"] = update.message.text.strip()
    update.message.reply_text("Напишите тему эфира:")
    return COFFEE_TOPIC

def get_coffee_topic(update, context):
    context.user_data["coffee_topic"] = update.message.text.strip()
    update.message.reply_text("Пришлите фото эксперта (или /skip):")
    return COFFEE_PHOTO

def skip_coffee_photo(update, context):
    context.user_data["coffee_photo"] = None
    return make_coffee(update, context)

def get_coffee_photo(update, context):
    photo = update.message.photo[-1].get_file()
    bio = io.BytesIO()
    photo.download(out=bio)
    bio.seek(0)
    context.user_data["coffee_photo"] = Image.open(bio).convert("RGBA")
    return make_coffee(update, context)

def make_coffee(update, context):
    # открываем фон
    base = Image.open(COFFEE_IMG).convert("RGBA")
    draw = ImageDraw.Draw(base)
    f_dt      = ImageFont.truetype(FONT_REG, 45)
    f_text    = ImageFont.truetype(FONT_REG, 40)

    # дата/время
    draw.text((50,50), context.user_data["coffee_dt"], font=f_dt, fill="white")

    # ФИО + тема
    draw.text((50,400), context.user_data["coffee_expert"], font=f_text, fill="white")
    draw.text((50,480), context.user_data["coffee_topic"], font=f_text, fill="white")

    # фото эксперта в круг
    ph = context.user_data.get("coffee_photo")
    if ph:
        diameter = 470
        ph = ImageOps.fit(ph, (diameter, diameter), method=Image.ANTIALIAS)
        mask = Image.new("L", (diameter, diameter), 0)
        ImageDraw.Draw(mask).ellipse((0,0,diameter,diameter), fill=255)
        ph.putalpha(mask)
        # вставляем чуть ниже, чтобы не обрезать лоб
        base.alpha_composite(ph, (base.width - diameter - 23, 300))

    # отправляем
    out = io.BytesIO()
    base.convert("RGB").save(out, format="JPEG")
    out.seek(0)
    update.message.reply_photo(photo=out, caption="Анонс готов!", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

# отмена
def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Регистрация хендлеров
conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOOSING_MODE:  [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        GENDER:         [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        FIO:            [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        BODY:           [MessageHandler(Filters.text & ~Filters.command, get_body)],
        CITYDATE:       [MessageHandler(Filters.text & ~Filters.command, make_gratitude)],
        COFFEE_DATE:    [MessageHandler(Filters.text & ~Filters.command, get_coffee_date)],
        COFFEE_EXPERT:  [MessageHandler(Filters.text & ~Filters.command, get_coffee_expert)],
        COFFEE_TOPIC:   [MessageHandler(Filters.text & ~Filters.command, get_coffee_topic)],
        COFFEE_PHOTO:   [
            MessageHandler(Filters.photo, get_coffee_photo),
            CommandHandler("skip", skip_coffee_photo)
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)

# Webhook для Flask
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route("/")
def index():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

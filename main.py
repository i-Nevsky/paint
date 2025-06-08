import logging, os, io
from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ВАШ_ТОКЕН_СЮДА'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# ——— ТВОИ КООРДИНАТЫ (правь здесь) ———
COORDS = {
    "gender":  (500, 420),   # «Уважаемый»
    "name":    (320, 510),   # Имя + Отчество
    "surname": (250, 600),   # Фамилия
    "body":    (200, 740),   # Основной текст
    "footer":  (1350, 1370), # Город и дата
}
MAX_WIDTH_BODY = 1000
# ————————————————————————————————

BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_PATH       = os.path.join(os.getcwd(), "static", "roboto.ttf")
BOLD_FONT_PATH  = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

STATE_MODE, STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(5)

def start(update, context):
    kb = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text("Выберите действие:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return STATE_MODE

def choose_mode(update, context):
    if update.message.text == "Создать благ. письмо ФАБА":
        kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text("Выберите обращение:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return STATE_GENDER
    update.message.reply_text("Функция анонсов пока не готова.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def get_gender(update, context):
    context.user_data["gender"] = update.message.text
    update.message.reply_text("Введите ФИО (Имя Отчество Фамилия):", reply_markup=ReplyKeyboardRemove())
    return STATE_FIO

def get_fio(update, context):
    context.user_data["fio"] = update.message.text.strip()
    update.message.reply_text("Введите текст благодарности:")
    return STATE_BODY

def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

def get_citydate(update, context):
    context.user_data["citydate"] = update.message.text.strip()
    try:
        img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        f_gen     = ImageFont.truetype(BOLD_FONT_PATH, 36)
        f_name    = ImageFont.truetype(BOLD_FONT_PATH, 52)
        f_surname = ImageFont.truetype(BOLD_FONT_PATH, 52)
        f_body    = ImageFont.truetype(FONT_PATH, 28)
        f_footer  = ImageFont.truetype(FONT_PATH, 22)

        # 1) Обращение
        draw.text(COORDS["gender"], context.user_data["gender"], font=f_gen, fill="black")

        # 2) ФИО
        parts = context.user_data["fio"].split()
        line1 = " ".join(parts[:-1]) if len(parts)>=2 else context.user_data["fio"]
        line2 = parts[-1] if len(parts)>=2 else ""
        draw.text(COORDS["name"],    line1,   font=f_name,    fill="black")
        draw.text(COORDS["surname"], line2,   font=f_surname, fill="black")

        # 3) Основной текст
        words = context.user_data["body"].split()
        lines = []
        for w in words:
            t = (lines[-1] + " " + w).strip() if lines else w
            if f_body.getsize(t)[0] <= MAX_WIDTH_BODY:
                if lines: lines[-1] = t
                else:     lines.append(t)
            else:
                lines.append(w)
        y = COORDS["body"][1]
        for ln in lines:
            draw.text((COORDS["body"][0], y), ln, font=f_body, fill="black")
            y += f_body.getsize(ln)[1] + 6

        # 4) Город и дата
        draw.text(COORDS["footer"], context.user_data["citydate"], font=f_footer, fill="black")

        out = io.BytesIO()
        img.save(out, format="PNG"); out.seek(0)
        update.message.reply_photo(photo=out, caption="Готово!", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")
    return ConversationHandler.END

def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_MODE:     [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_GENDER:   [MessageHandler(Filters.text & ~Filters.command, get_gender)],
        STATE_FIO:      [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_BODY:     [MessageHandler(Filters.text & ~Filters.command, get_body)],
        STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_citydate)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    upd = Update.de_json(data, bot)
    dispatcher.process_update(upd)
    return "ok", 200

@app.route("/")
def index():
    return "Service is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

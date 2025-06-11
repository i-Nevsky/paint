import os
from telegram import Bot, Update, ReplyKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)
from PIL import Image, ImageDraw, ImageFont

# ======= КОНФИГ =======
TOKEN = os.getenv("BOT_TOKEN") or "ТВОЙ_ТОКЕН_ЗДЕСЬ"
BASE_IMAGE_PATH = "static/base_image.png"
ROBOTO_PATH = "static/roboto.ttf"
ROBOTO_BOLD_PATH = "static/Roboto-Bold.ttf"

COORDS = {
    "gender":  (510, 330),
    "name":    (350, 410),
    "surname": (300, 470),
    "body":    (170, 540),
    "footer":  (820, 970),
}

STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)

# ======= HANDLERS =======
def start(update: Update, context: CallbackContext):
    reply_markup = ReplyKeyboardMarkup(
        [["Уважаемый", "Уважаемая"]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    update.message.reply_text("Выберите обращение:", reply_markup=reply_markup)
    return STATE_GENDER

def get_gender(update: Update, context: CallbackContext):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text("Введите ФИО (Имя Отчество Фамилия):", reply_markup=None)
    return STATE_FIO

def get_fio(update: Update, context: CallbackContext):
    fio = update.message.text.strip()
    fio_parts = fio.split()
    if len(fio_parts) < 3:
        update.message.reply_text("Введите ФИО полностью (Имя Отчество Фамилия):")
        return STATE_FIO
    context.user_data["name"] = fio_parts[0] + " " + fio_parts[1]
    context.user_data["surname"] = fio_parts[2]
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_BODY

def get_body(update: Update, context: CallbackContext):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text(
        "Введите город и дату (например: г. Краснодар, май 2025):"
    )
    return STATE_CITYDATE

def get_citydate(update: Update, context: CallbackContext):
    context.user_data["citydate"] = update.message.text.strip()
    # Генерация письма
    img_path = generate_certificate(context.user_data)
    with open(img_path, "rb") as img:
        update.message.reply_photo(photo=img)
    update.message.reply_text("Готово!")
    return ConversationHandler.END

def generate_certificate(data):
    img = Image.open(BASE_IMAGE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    f_gender = ImageFont.truetype(ROBOTO_PATH, 34)
    f_name = ImageFont.truetype(ROBOTO_PATH, 48)
    f_surname = ImageFont.truetype(ROBOTO_BOLD_PATH, 64)
    f_body = ImageFont.truetype(ROBOTO_PATH, 28)
    f_footer = ImageFont.truetype(ROBOTO_PATH, 24)

    # Размещение текста по координатам из сетки
    draw.text(COORDS["gender"], data["gender"], font=f_gender, fill="black")
    draw.text(COORDS["name"], data["name"], font=f_name, fill="black")
    draw.text(COORDS["surname"], data["surname"], font=f_surname, fill="black")
    draw.multiline_text(COORDS["body"], data["body"], font=f_body, fill="black", spacing=6)
    draw.text(COORDS["footer"], data["citydate"], font=f_footer, fill="black")

    output_path = "static/result.png"
    img.save(output_path)
    return output_path

# ======= MAIN =======
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STATE_GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
            STATE_FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
            STATE_BODY: [MessageHandler(Filters.text & ~Filters.command, get_body)],
            STATE_CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_citydate)],
        },
        fallbacks=[],
    )

    dp.add_handler(conv_handler)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

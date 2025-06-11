import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, ConversationHandler
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN")
bot = Bot(token=TOKEN)
app = Flask(__name__)

TEMPLATE_PATH = "static/base_image.png"
BOLD_FONT_PATH = "static/roboto-bold.ttf"
REG_FONT_PATH = "static/roboto.ttf"
OUTPUT_PATH = "gratitude_output.png"

COORDS = {
    "gender":   (510, 330),
    "name":     (350, 410),
    "surname":  (300, 470),
    "body":     (170, 540),
    "footer":   (820, 970),
}

GENDER, FIO, BODY, CITYDATE = range(4)

def make_gratitude(gender, fio_name, fio_surname, body, footer):
    im = Image.open(TEMPLATE_PATH).convert("RGBA")
    draw = ImageDraw.Draw(im)
    f_gender = ImageFont.truetype(REG_FONT_PATH, 36)
    f_name = ImageFont.truetype(BOLD_FONT_PATH, 48)
    f_surname = ImageFont.truetype(BOLD_FONT_PATH, 68)
    f_body = ImageFont.truetype(REG_FONT_PATH, 30)
    f_footer = ImageFont.truetype(REG_FONT_PATH, 26)
    draw.text(COORDS["gender"], gender, font=f_gender, fill="black")
    draw.text(COORDS["name"], fio_name, font=f_name, fill="black")
    draw.text(COORDS["surname"], fio_surname, font=f_surname, fill="black")
    draw.multiline_text(COORDS["body"], body, font=f_body, fill="black", spacing=6)
    draw.text(COORDS["footer"], footer, font=f_footer, fill="black")
    im.save(OUTPUT_PATH)
    return OUTPUT_PATH

def setup_dispatcher(dp):
    def start(update, context):
        reply_keyboard = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup={"keyboard": reply_keyboard, "one_time_keyboard": True, "resize_keyboard": True},
        )
        return GENDER

    def get_gender(update, context):
        context.user_data["gender"] = update.message.text
        update.message.reply_text("Введите ФИО (через пробел):")
        return FIO

    def get_fio(update, context):
        fio = update.message.text.strip().split()
        if len(fio) < 3:
            update.message.reply_text("Пожалуйста, введите Фамилию, Имя и Отчество через пробел:")
            return FIO
        context.user_data["surname"] = fio[0]
        context.user_data["name"] = f"{fio[1]} {fio[2]}"
        update.message.reply_text("Введите основной текст (выражение благодарности).")
        return BODY

    def get_body(update, context):
        context.user_data["body"] = update.message.text
        update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
        return CITYDATE

    def get_citydate(update, context):
        context.user_data["footer"] = update.message.text
        try:
            img_path = make_gratitude(
                gender=context.user_data["gender"],
                fio_name=context.user_data["name"],
                fio_surname=context.user_data["surname"],
                body=context.user_data["body"],
                footer=context.user_data["footer"],
            )
            with open(img_path, "rb") as photo:
                update.message.reply_photo(photo)
            update.message.reply_text("Готово!")
        except Exception as e:
            update.message.reply_text(f"Ошибка при создании письма: {e}")
        return ConversationHandler.END

    def cancel(update, context):
        update.message.reply_text("Отменено.")
        return ConversationHandler.END

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
            FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
            BODY: [MessageHandler(Filters.text & ~Filters.command, get_body)],
            CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_citydate)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dp.add_handler(conv_handler)
    return dp

dispatcher = setup_dispatcher(Dispatcher(bot, None, workers=0, use_context=True))

@app.route(f"/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

# Для Render Procfile:  web: gunicorn main:app

if __name__ == "__main__":
    app.run(port=5000, debug=True)

import os
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

TOKEN = "твой_токен"
BASE_IMAGE_PATH = "static/base_image.png"
FONT_PATH = "static/roboto.ttf"
BOLD_FONT_PATH = "static/Roboto-Bold.ttf"

# ---- КООРДИНАТЫ С ТВОЕГО СКРИНА ----
COORDS = {
    "gender":  (510, 330),  # «Уважаемый»
    "name":    (350, 410),  # Имя + Отчество
    "surname": (300, 470),  # Фамилия
    "body":    (170, 540),  # Основной текст
    "footer":  (820, 970),  # Город и дата
}

BODY_TEXT = (
    "Выражаем Вам огромную благодарность за поддержку деятельности ФАБА «ПлатинУМ»\n"
    "в Краснодарском крае, а также за Ваш вклад\n"
    "в развитие налогового и бухгалтерского дела. Ваш богатый опыт и профессионализм имеют высокую ценность для бухгалтерского сообщества."
)

# ---- СОСТОЯНИЯ ДЛЯ CONVERSATION ----
GENDER, FIO, BODY, CITYDATE = range(4)

def start(update: Update, context: CallbackContext):
    reply_markup = ReplyKeyboardMarkup([['Уважаемый', 'Уважаемая']], resize_keyboard=True)
    update.message.reply_text("Выберите обращение:", reply_markup=reply_markup)
    return GENDER

def get_gender(update: Update, context: CallbackContext):
    context.user_data["gender"] = update.message.text
    update.message.reply_text("Введите ФИО (например: Иванов Иван Иванович):", reply_markup=ReplyKeyboardRemove())
    return FIO

def get_fio(update: Update, context: CallbackContext):
    fio = update.message.text.strip().split()
    if len(fio) < 3:
        update.message.reply_text("Пожалуйста, введите полностью: Фамилия Имя Отчество.")
        return FIO
    context.user_data["surname"] = fio[0]
    context.user_data["name"] = " ".join(fio[1:])
    context.user_data["body"] = BODY_TEXT
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return CITYDATE

def get_citydate(update: Update, context: CallbackContext):
    context.user_data["footer"] = update.message.text
    # --- Генерация изображения ---
    try:
        img = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(img)

        # Шрифты
        f_header = ImageFont.truetype(BOLD_FONT_PATH, 36)    # обращение
        f_name = ImageFont.truetype(BOLD_FONT_PATH, 48)      # имя + отчество
        f_surname = ImageFont.truetype(BOLD_FONT_PATH, 72)   # фамилия
        f_body = ImageFont.truetype(FONT_PATH, 28)           # основной текст
        f_footer = ImageFont.truetype(FONT_PATH, 24)         # футер

        # Текст
        draw.text(COORDS["gender"],  context.user_data["gender"], font=f_header, fill="black")
        draw.text(COORDS["name"],    context.user_data["name"], font=f_name, fill="black")
        draw.text(COORDS["surname"], context.user_data["surname"], font=f_surname, fill="black")
        draw.multiline_text(COORDS["body"], context.user_data["body"], font=f_body, fill="black", spacing=4)
        draw.text(COORDS["footer"], context.user_data["footer"], font=f_footer, fill="black")

        # Отправка в чат
        bio = BytesIO()
        bio.name = 'gratitude.png'
        img.save(bio, "PNG")
        bio.seek(0)
        update.message.reply_photo(photo=bio, caption="Готово!")

    except Exception as e:
        update.message.reply_text(f"Ошибка при создании письма: {e}")

    return ConversationHandler.END

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GENDER: [MessageHandler(Filters.text & ~Filters.command, get_gender)],
            FIO: [MessageHandler(Filters.text & ~Filters.command, get_fio)],
            CITYDATE: [MessageHandler(Filters.text & ~Filters.command, get_citydate)],
        },
        fallbacks=[]
    )

    dp.add_handler(conv)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

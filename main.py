import logging
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, CallbackContext
from PIL import Image, ImageDraw, ImageFont
import io
import os

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
BASE_IMAGE_PATH = "path/to/your/image.jpg"
FONT_PATH = "path/to/your/font.ttf"
FONT_SIZE = 40

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Привет! Отправь команду /overlay <текст> для наложения текста на картинку.")

def overlay(update: Update, context: CallbackContext):
    text = ' '.join(context.args)
    if not text:
        update.message.reply_text("Укажи текст после команды, например: /overlay Привет мир!")
        return

    try:
        image = Image.open(BASE_IMAGE_PATH)
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

        width, height = image.size
        text_width, text_height = draw.textsize(text, font=font)
        position = ((width - text_width) / 2, (height - text_height) / 2)

        draw.text(position, text, font=font, fill="white")

        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)

        update.message.reply_photo(photo=img_byte_arr)
    except Exception as e:
        update.message.reply_text(f"Ошибка: {e}")

def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("overlay", overlay))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

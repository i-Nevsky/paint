import logging
import os
import io

from flask import Flask, request
from telegram import Bot, Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Dispatcher, CommandHandler, ConversationHandler, MessageHandler, Filters
from PIL import Image, ImageDraw, ImageFont

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)

# === Инициализация бота и веб-сервиса ===
app = Flask(__name__)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') or 'ВАШ_ТОКЕН_ЗДЕСЬ'
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# === Пути к ресурсам ===
BASE_IMAGE_PATH = os.path.join(os.getcwd(), "static", "gratitude.png")
FONT_REGULAR = os.path.join(os.getcwd(), "static", "roboto.ttf")
FONT_BOLD    = os.path.join(os.getcwd(), "static", "Roboto-Bold.ttf")

# === Состояния диалога ===
STATE_GENDER, STATE_FIO, STATE_BODY, STATE_CITYDATE = range(4)

# === Координаты на шаблоне (в пикселях) ===
COORDS = {
    "gender":  (650,  450),   # «Уважаемый» / «Уважаемая»
    "name":    (650,  550),   # Имя + Отчество
    "surname": (650,  650),   # Фамилия
    "body":    (350,  750),   # Основной текст
    "sign":    (400,  810),   # Подпись
    "footer":  (650, 1350),   # Город и дата
}
MAX_WIDTH_BODY = 1000  # ширина области для переноса строк в основном тексте

# === /start: выбор режима ===
def start(update, context):
    keyboard = [["Создать благ. письмо ФАБА"], ["Создать анонс к Кофе"]]
    update.message.reply_text(
        "Выберите действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return STATE_GENDER

# === Обработка выбора режима ===
def choose_mode(update, context):
    text = update.message.text
    if text == "Создать благ. письмо ФАБА":
        # Убираем главное меню, показываем выбор обращения
        gender_kb = [["Уважаемый"], ["Уважаемая"]]
        update.message.reply_text(
            "Выберите обращение:",
            reply_markup=ReplyKeyboardMarkup(gender_kb, resize_keyboard=True)
        )
        return STATE_FIO
    else:
        update.message.reply_text(
            "Эта функция пока не реализована.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

# === Получение обращения ===
def get_gender(update, context):
    context.user_data["gender"] = update.message.text.strip()
    update.message.reply_text(
        "Введите ФИО (Имя Отчество Фамилия):",
        reply_markup=ReplyKeyboardRemove()
    )
    return STATE_BODY

# === Получение ФИО ===
def get_fio(update, context):
    full_fio = update.message.text.strip()
    parts = full_fio.split()
    # Сохраняем отдельно имя+отчество и фамилию
    if len(parts) >= 3:
        context.user_data["name_part"] = " ".join(parts[:2])
        context.user_data["surname_part"] = " ".join(parts[2:])
    else:
        # Если один-два слова — всё в name_part, surname_part пустая
        context.user_data["name_part"] = full_fio
        context.user_data["surname_part"] = ""
    update.message.reply_text("Введите основной текст (выражение благодарности):")
    return STATE_CITYDATE

# === Получение основного текста и переход к городу/дате ===
def get_body(update, context):
    context.user_data["body"] = update.message.text.strip()
    update.message.reply_text("Введите город и дату (например: г. Краснодар, май 2025):")
    return STATE_CITYDATE

# === Получение города и даты — финальная отрисовка ===
def get_city_date(update, context):
    context.user_data["footer"] = update.message.text.strip()
    
    try:
        # Открываем шаблон и готовим к рисованию
        base = Image.open(BASE_IMAGE_PATH).convert("RGBA")
        draw = ImageDraw.Draw(base)
        
        # Загружаем шрифты
        f_gender  = ImageFont.truetype(FONT_BOLD,    36)
        f_name    = ImageFont.truetype(FONT_BOLD,    52)
        f_body    = ImageFont.truetype(FONT_REGULAR, 28)
        f_sign    = ImageFont.truetype(FONT_REGULAR, 28)
        f_footer  = ImageFont.truetype(FONT_REGULAR, 22)
        
        # 1) Обращение
        draw.text(
            COORDS["gender"],
            context.user_data["gender"],
            font=f_gender,
            fill="black"
        )
        
        # 2) Имя + Отчество
        draw.text(
            COORDS["name"],
            context.user_data["name_part"],
            font=f_name,
            fill="black"
        )
        
        # 3) Фамилия (если есть)
        if context.user_data["surname_part"]:
            draw.text(
                COORDS["surname"],
                context.user_data["surname_part"],
                font=f_name,
                fill="black"
            )
        
        # 4) Основной текст с переносом строк
        body = context.user_data["body"]
        lines = []
        words = body.split()
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            if f_body.getsize(test)[0] <= MAX_WIDTH_BODY:
                line = test
            else:
                lines.append(line)
                line = w
        if line:
            lines.append(line)
        
        y = COORDS["body"][1]
        for l in lines:
            draw.text((COORDS["body"][0], y), l, font=f_body, fill="black")
            y += f_body.getsize(l)[1] + 6
        
        # 5) Подпись (фиксированный текст)
        sign_text = "Федеральная ассоциация\nбухгалтеров-аутсорсеров\n«ПлатинУМ»"
        draw.text(COORDS["sign"], sign_text, font=f_sign, fill="black")
        
        # 6) Город и дата
        draw.text(
            COORDS["footer"],
            context.user_data["footer"],
            font=f_footer,
            fill="black"
        )
        
        # Сохраняем в поток и шлём
        bio = io.BytesIO()
        base.convert("RGB").save(bio, format="JPEG")
        bio.seek(0)
        update.message.reply_photo(photo=bio, caption="Готово!")
        
    except Exception as e:
        logging.exception("Ошибка при создании письма")
        update.message.reply_text(f"Ошибка при создании письма: {e}")
    
    # Возвращаемся в главное меню
    return start(update, context)

# === Отмена диалога ===
def cancel(update, context):
    update.message.reply_text("Отмена.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === Регистрируем ConversationHandler ===
conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        STATE_GENDER:  [MessageHandler(Filters.text & ~Filters.command, choose_mode)],
        STATE_FIO:     [MessageHandler(Filters.regex("^(Уважаемый|Уважаемая)$"), get_gender)],
        STATE_BODY:    [MessageHandler(Filters.text & ~Filters.command, get_fio)],
        STATE_CITYDATE:[MessageHandler(Filters.text & ~Filters.command, get_body)],
        ConversationHandler.END: [MessageHandler(Filters.text & ~Filters.command, get_city_date)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
    allow_reentry=True
)
dispatcher.add_handler(conv)

# === Вебхук и главная страница ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return "ok", 200

@app.route('/')
def index():
    return "Сервис Telegram бота работает"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

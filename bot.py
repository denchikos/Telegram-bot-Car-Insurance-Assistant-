import logging
import os
import random
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
import google.generativeai as genai

# === ЗАВАНТАЖЕННЯ ЗМІННИХ ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# === ЛОГІ ===
logging.basicConfig(level=logging.INFO)

# === СТАНИ ===
PASSPORT, CAR_DOC, CONFIRMATION, PRICE_CONFIRM = range(4)

# === НАСТРОЙКА GEMINI ===
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('models/gemini-1.5-flash')


# === MOCK-ДАНІ ===
user_data = {}
NAMES = ["Олександр", "Марія", "Іван", "Андрій", "Катерина"]
SURNAMES = ["Петренко", "Іванов", "Коваль", "Мельник", "Шевченко"]
MODELS = ["Golf", "Focus", "Civic", "Octavia", "Passat"]
BRANDS = ["Volkswagen", "Ford", "Honda", "Skoda", "Toyota"]


# === ФУНКЦІЯ ВІДПОВІДІ ВІД GEMINI ===
async def ask_gemini(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print("Gemini error:", type(e).__name__, "-", e)
        return "Вибач, сталася помилка при генерації відповіді 😥"


# === ІМІТАЦІЯ MINDЕE API ===
def mock_extract_data(document_type: str, user_id: int) -> dict:
    random.seed(user_id)
    if document_type == "passport":
        return {
            "Імʼя": random.choice(NAMES),
            "Прізвище": random.choice(SURNAMES),
            "Номер паспорта": f"AA{random.randint(100000, 999999)}"
        }
    elif document_type == "car_doc":
        vin = "WVW" + "".join(random.choices("ABCDEFGHJKLMNPRSTUVWXYZ0123456789", k=14))
        return {
            "VIN": vin,
            "Марка": random.choice(BRANDS),
            "Модель": random.choice(MODELS)
        }


# === ГЕНЕРАЦІЯ ПОЛІСУ ===
def generate_policy_file(user_id: int, passport_data: dict, car_data: dict) -> str:
    date_today = datetime.now().strftime("%Y-%m-%d")
    policy_number = f"PL-{random.randint(100000, 999999)}"
    content = (
        f"СТРАХОВИЙ ПОЛІС № {policy_number}\n"
        f"Дата оформлення: {date_today}\n\n"
        f"👤 Власник:\n"
        f"Імʼя: {passport_data['Імʼя']}\n"
        f"Прізвище: {passport_data['Прізвище']}\n"
        f"Номер паспорта: {passport_data['Номер паспорта']}\n\n"
        f"🚗 Автомобіль:\n"
        f"Марка: {car_data['Марка']}\n"
        f"Модель: {car_data['Модель']}\n"
        f"VIN: {car_data['VIN']}\n\n"
        f"💰 Вартість: 100 USD\n"
        f"🔒 Поліс дійсний протягом 1 року\n"
    )
    filename = f"temp/policy_{user_id}.txt"
    with open(filename, "w", encoding="utf-8") as file:
        file.write(content)
    return filename


# === /START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await ask_gemini("Привітайся з користувачем і попроси надіслати фото паспорта.")
    await update.message.reply_text(msg)
    return PASSPORT


# === ОБРОБКА ПАСПОРТА ===
async def handle_passport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]
    file = await photo.get_file()
    passport_path = f"temp/{user_id}_passport.jpg"
    await file.download_to_drive(passport_path)
    user_data[user_id] = {"passport": passport_path}

    msg = await ask_gemini("Подякуй за фото паспорта і попроси фото техпаспорта.")
    await update.message.reply_text(msg)
    return CAR_DOC


# === ОБРОБКА ТЕХПАСПОРТА ===
async def handle_car_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]
    file = await photo.get_file()
    car_doc_path = f"temp/{user_id}_car_doc.jpg"
    await file.download_to_drive(car_doc_path)
    user_data[user_id]["car_doc"] = car_doc_path

    passport_data = mock_extract_data("passport", user_id)
    car_data = mock_extract_data("car_doc", user_id)
    user_data[user_id]["passport_data"] = passport_data
    user_data[user_id]["car_data"] = car_data

    result = "📄 Ми розпізнали ваші дані:\n\n"
    result += "\n".join([f"{k}: {v}" for k, v in passport_data.items()])
    result += "\n\n🚗 Дані авто:\n"
    result += "\n".join([f"{k}: {v}" for k, v in car_data.items()])
    result += "\n\nЧи все правильно? (Так / Ні)"

    await update.message.reply_text(result)
    return CONFIRMATION


# === ПІДТВЕРДЖЕННЯ ДАНИХ ===
async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "так":
        msg = await ask_gemini("Скажи, що вартість страховки 100 доларів і запитай чи згоден користувач.")
        await update.message.reply_text(msg)
        return PRICE_CONFIRM
    elif text == "ні":
        msg = await ask_gemini("Попроси користувача ще раз надіслати фото паспорта.")
        await update.message.reply_text(msg)
        return PASSPORT
    else:
        return CONFIRMATION


# === ПІДТВЕРДЖЕННЯ ЦІНИ ===
async def handle_price_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.lower()

    if text == "так":
        await update.message.reply_text(await ask_gemini("Подякуй за згоду і скажи, що зараз буде згенеровано поліс."))

        passport_data = user_data[user_id]["passport_data"]
        car_data = user_data[user_id]["car_data"]
        policy_path = generate_policy_file(user_id, passport_data, car_data)

        await update.message.reply_document(
            document=open(policy_path, "rb"),
            filename=f"insurance_policy_{user_id}.txt",
            caption="Ось ваш страховий поліс. Дякуємо за звернення! ✅"
        )
        return ConversationHandler.END

    elif text == "ні":
        await update.message.reply_text(
            await ask_gemini("Поясни, що 100 USD — це фіксована ціна, і користувач може повернутися пізніше."))
        return ConversationHandler.END

    else:
        return PRICE_CONFIRM


# === MAIN ===
def main():
    if not os.path.exists("temp"):
        os.makedirs("temp")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PASSPORT: [MessageHandler(filters.PHOTO, handle_passport)],
            CAR_DOC: [MessageHandler(filters.PHOTO, handle_car_doc)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation)],
            PRICE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_confirmation)],
        },
        fallbacks=[],
    )

    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
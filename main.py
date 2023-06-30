import logging
import csv
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Contact
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from datetime import datetime
from telegram.error import BadRequest, Forbidden

from telegram.error import BadRequest
user_scores = {}
# Database setup
# Database setup
conn = sqlite3.connect('subscribers.db')
c = conn.cursor()

# Create the subscribers table if it doesn't exist
c.execute('''CREATE TABLE IF NOT EXISTS subscribers (telegram_id text)''')
conn.commit()  # commit the changes

# Get the column info
c.execute("PRAGMA table_info(subscribers)")
columns = [column[1] for column in c.fetchall()]

# Add the subscribed column if it doesn't exist
if 'subscribed' not in columns:
    c.execute("ALTER TABLE subscribers ADD COLUMN subscribed text DEFAULT 'subscribed'")
    conn.commit()  # commit the changes

# Add the phone_number column if it doesn't exist
if 'phone_number' not in columns:
    c.execute("ALTER TABLE subscribers ADD COLUMN phone_number text")
    conn.commit()  # commit the changes

# Add the email column if it doesn't exist
if 'email' not in columns:
    c.execute("ALTER TABLE subscribers ADD COLUMN email text")
    conn.commit()  # commit the changes


def save_subscriber(telegram_id, phone_number, email):
    c.execute("SELECT telegram_id FROM subscribers WHERE telegram_id = ?", (telegram_id,))
    if c.fetchone() is None:
        c.execute("INSERT INTO subscribers VALUES (?, ?, ?, 'subscribed')", (telegram_id, phone_number, email))
    else:
        c.execute("UPDATE subscribers SET phone_number = ?, email = ?, subscribed = 'subscribed' WHERE telegram_id = ?", (phone_number, email, telegram_id))
    conn.commit()  # commit the changes




QUESTION_TEXT = [
    "1/10 Чи маєте ви досвід в лікарні? (асистенція, медсестринство, стажування)",
    "2/10 Чи проводили ви опитування та огляд пацієнтів?",
    "3/10 Чи вмієте ви швидко та якісно заповнювати медичну документацію? (історія хвороби, виписка, щоденник, протокол операції і т.д)",
    "4/10 Чи вмієте ви знаходити компроміс в конфліктних ситуаціях?",
    "5/10 Чи знаєте ви, як і де шукати стажування та навчальні курси для розвитку в медицині?",
    "6/10 Чи знаєте ви як користуватися медичними інформаційними системами (МІС), зокрема, як вести електронні медичні записи?",
    "7/10 Чи знаєте ви як співпрацювати з наставником так щоб він був зацікавлений вас навчити?",
    "8/10 Чи маєте Ви досвід участі в наукових дослідженнях та публікаціях?",
    "9/10 Чи знаєте ви законодавчу базу необхідну для практичної діяльності лікаря (зокрема, з метою юридичного захисту)?",
    "10/10 Чи потрібні вам додаткові програми для розвитку себе як конкурентноспроможного і затребуваного спеціаліста в медичній сфері в Україні?"
]

QUESTION_OPTIONS = [
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"],
    ["так", "ні"]
]

# Define CSV file name
CSV_FILE = 'results.csv'  # Specify the name of your CSV file here

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def save_answer(user, question, answer_index, context):
    """Save the user's answer to a CSV file."""
    # Convert the answer index to an integer
    answer_index = int(answer_index)
    # Get the current question index
    current_question = QUESTION_TEXT.index(question)
    # Get the answer text from QUESTION_OPTIONS
    answer_text = QUESTION_OPTIONS[current_question][answer_index]
    context.user_data['answers'].append(answer_text)
    user_id = user.id
    if user_id not in user_scores:
        user_scores[user_id] = []
    user_scores[user_id].append(answer_index)
def calculate_score(user_id):
    answers = user_scores[user_id]
    total_questions = 10
    score = 100
    for answer in answers:
        if answer.lower() == 'ні':
            score -= 10
    return score
async def request_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[KeyboardButton("📞Надати номер📞", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard)
    await update.message.reply_text("Будь ласка, поділіться вашим номером телефона", reply_markup=reply_markup)
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.contact:
        contact = update.message.contact
        phone_number = contact.phone_number
    else:
        phone_number = update.message.text
    # Save the phone number to the user data
    context.user_data['phone_number'] = phone_number
    # Request the user's email
    await request_email(update, context)  # <-- Use 'await' here
    # Save the subscriber's data
    save_subscriber(update.effective_user.id, phone_number, None)


async def request_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("💌Введіть свій e-mail💌")
async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if 'phone_number' not in context.user_data:
        # Користувач щойно ввів свій номер телефону
        phone_number = update.message.text
        # Зберегти номер телефону в даних користувача
        context.user_data['phone_number'] = phone_number
        # Зберегти дані передплатника
        save_subscriber(user_id, phone_number, None)
        # Запросити електронну пошту користувача
        await request_email(update, context)
    else:
        # Користувач щойно ввів свою електронну пошту
        email = update.message.text
        # Зберегти електронну пошту в даних користувача
        context.user_data['email'] = email
        # Зберегти дані передплатника
        save_subscriber(user_id, context.user_data['phone_number'], email)
        # Розпочати тест
        await send_first_question(update, context)

async def send_first_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Create the keyboard for the first question
    keyboard = [
        [InlineKeyboardButton(option, callback_data=str(index)) for index, option in enumerate(QUESTION_OPTIONS[0])]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the first question
    await update.message.reply_text(
        QUESTION_TEXT[0],
        reply_markup=reply_markup,
    )

    # Set the current question to 0
    context.user_data['current_question'] = 0

    # Clear the answers for the user
    user_scores[update.effective_user.id] = []
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Initialize the answers for the user
    context.user_data['answers'] = []

    # Get the user
    user = update.effective_user

    # Request the user's contact information
    await request_contact(update, context)


async def next_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    user_id = user.id
    answer = query.data
    current_question = context.user_data['current_question']
    save_answer(user, QUESTION_TEXT[current_question], answer, context)
    logger.info(f"User {user.id} answered question {current_question} with {answer}")
    if current_question < len(QUESTION_TEXT) - 1:
        keyboard = [
            [
                InlineKeyboardButton(option, callback_data=str(index))
                for index, option in enumerate(QUESTION_OPTIONS[current_question + 1][:2])
                # First two options in the current_question list
            ],
            [
                InlineKeyboardButton(option, callback_data=str(index))
                for index, option in enumerate(QUESTION_OPTIONS[current_question + 1][2:])
                # Last two options in the current_question list
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=QUESTION_TEXT[current_question + 1],
            reply_markup=reply_markup,
        )
        context.user_data['current_question'] = current_question + 1
    else:
        score = await calculate_score(context.user_data['answers'])
        await save_final_result(user, context.user_data['answers'], score, context)

        # Determine the status based on the score
        if 90 <= score <= 100:
               status = "Крутий інтерн 😎"
        elif 70 <= score < 90:
                status = "Перспективний інтерн 😏"
        elif 50 <= score < 70:
                status = "Компетентний інтерн 🧐"
        else:
                status = "Інтерн початківець 👶"

        await query.edit_message_text(
                text=f"""Результати: Рівень вашої готовності *{score}%*
Ваш статус: {status}"""
        )
        return -1


from telegram.error import BadRequest

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != 358654127:
        return
    message = ' '.join(context.args)
    c.execute('SELECT telegram_id FROM subscribers')
    rows = c.fetchall()  # Отримати всі рядки з результатами запиту SELECT
    for row in rows:
        try:
            chat_id = row[0]  # Отримати значення telegram_id з рядка
            await context.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"Sent message to subscriber {chat_id}")
            c.execute("UPDATE subscribers SET subscribed = 'subscribed' WHERE telegram_id = ?", (chat_id,))
            conn.commit()
            await asyncio.sleep(1)  # Зачекати 1 секунду
        except BadRequest as e:
            if 'Forbidden: bot was blocked by the user' in str(e):
                logger.error(f"Bot was blocked by the subscriber {chat_id}")
                c.execute("UPDATE subscribers SET subscribed = 'unsubscribed' WHERE telegram_id = ?", (chat_id,))
                conn.commit()
            else:
                logger.error(f"Failed to send message to subscriber {chat_id} due to BadRequest: {e}")
        except Forbidden as e:
            if 'bot was blocked by the user' in str(e):
                logger.error(f"Bot was blocked by the subscriber {chat_id}")
                c.execute("UPDATE subscribers SET subscribed = 'unsubscribed' WHERE telegram_id = ?", (chat_id,))
                conn.commit()
            else:
                logger.error(f"Failed to send message to subscriber {chat_id} due to Forbidden: {e}")


async def calculate_score(answers):
    total_questions = 10
    score = 100
    for answer in answers:
        if answer == 'ні':  # 'ні' is considered as 'no'
            score -= 10
    return score
async def save_final_result(user, answers, score, context):
    """Save the user's final result to a CSV file."""
    try:
        with open(CSV_FILE, 'x', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['Timestamp', 'User', 'Final Result', 'Answers', 'Score'])
    except FileExistsError:
        pass
    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([timestamp, user, 'Final Result', answers, score])

def main() -> None:
    application = Application.builder().token("6232551131:AAG2-8nMYPJgB_ihvwRHpALG8NIhAk4NiSw").build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email))
    application.add_handler(CallbackQueryHandler(next_question))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("start", request_contact))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, next_question))
    application.run_polling()

if __name__ == '__main__':
    main()

from telegram.ext import CommandHandler
from handlers.start import start

dispatcher.add_handler(CommandHandler("start", start))
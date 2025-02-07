import os
os.environ['BOT_ENV'] = 'prod'

from src.bot.bot import bot, TOKEN

if __name__ == '__main__':
    bot.run(TOKEN)
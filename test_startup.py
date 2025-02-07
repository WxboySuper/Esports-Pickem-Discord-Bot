import os
os.environ['BOT_ENV'] = 'test'

from src.bot.bot import bot, TOKEN

if __name__ == '__main__':
    bot.run(TOKEN)
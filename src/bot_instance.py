_bot_instance = None


def set_bot_instance(bot):
    global _bot_instance
    _bot_instance = bot


def get_bot_instance():
    return _bot_instance
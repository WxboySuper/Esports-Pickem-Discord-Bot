class BotInstance:
    _instance = None

    @classmethod
    def set_bot(cls, bot):
        print(f"Setting bot instance: {bot}")
        cls._instance = bot

    @classmethod
    def get_bot(cls):
        print(f"Getting bot instance: {cls._instance}")
        return cls._instance

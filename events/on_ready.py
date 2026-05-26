def register(bot):
    @bot.event
    async def on_ready():
        user = bot.user
        if user is None:
            return

class PicksCog:
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='pick')
    async def make_pick(self, ctx, match_id: int, prediction: str):
        """Allows a user to make a pick for a specific match."""
        # Logic to save the user's pick to the database
        await ctx.send(f"{ctx.author.mention}, your pick for match {match_id} has been recorded as {prediction}.")

    @commands.command(name='mypicks')
    async def view_picks(self, ctx):
        """Displays the user's picks."""
        # Logic to retrieve and display the user's picks from the database
        await ctx.send(f"{ctx.author.mention}, here are your picks...")

    @commands.command(name='leaderboard')
    async def show_leaderboard(self, ctx):
        """Displays the leaderboard of users."""
        # Logic to retrieve and display the leaderboard
        await ctx.send("Here is the current leaderboard...")
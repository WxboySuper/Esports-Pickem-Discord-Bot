# src/commands/match.py
import logging
import discord
from discord import app_commands
from discord.ext import commands
import csv
import io
from datetime import datetime

from src.app import ADMIN_IDS
from src.crud import bulk_create_matches, get_contest_by_id
from src.db import get_session

logger = logging.getLogger("esports-bot.commands.match")


class Match(app_commands.Group, name="match", description="Manage matches"):
    @app_commands.command(name="upload", description="Upload a match schedule via CSV")
    @app_commands.describe(
        contest_id="The ID of the contest to add matches to",
        attachment="The CSV file with the match schedule",
    )
    async def upload(
        self,
        interaction: discord.Interaction,
        contest_id: int,
        attachment: discord.Attachment,
    ):
        if interaction.user.id not in ADMIN_IDS:
            await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )
            return

        session = get_session()
        try:
            contest = get_contest_by_id(session, contest_id)
            if not contest:
                await interaction.response.send_message(
                    f"Contest with ID {contest_id} not found.", ephemeral=True
                )
                return

            # Read and parse the CSV file
            csv_data = await attachment.read()
            csv_file = io.StringIO(csv_data.decode("utf-8"))
            reader = csv.DictReader(csv_file)

            matches_to_create = []
            errors = []
            for i, row in enumerate(reader, 1):
                try:
                    match_datetime = datetime.fromisoformat(row["match_datetime"])
                    team_a = row["team_a"]
                    team_b = row["team_b"]

                    if not team_a or not team_b:
                        errors.append(f"Line {i}: team_a and team_b cannot be empty.")
                        continue

                    matches_to_create.append(
                        {
                            "contest_id": contest_id,
                            "scheduled_time": match_datetime,
                            "team1": team_a,
                            "team2": team_b,
                        }
                    )
                except (ValueError, KeyError) as e:
                    errors.append(f"Line {i}: Invalid data - {e}")

            if errors:
                error_message = "Found errors in the CSV file:\n" + "\n".join(errors)
                await interaction.response.send_message(error_message, ephemeral=True)
                return

            if not matches_to_create:
                await interaction.response.send_message(
                    "No valid matches found in the CSV file.", ephemeral=True
                )
                return

            bulk_create_matches(session, matches_to_create)

            await interaction.response.send_message(
                f"Successfully uploaded {len(matches_to_create)} matches to contest {contest_id}.",
                ephemeral=True,
            )

        except Exception as e:
            logger.exception("Error uploading match schedule")
            await interaction.response.send_message(
                f"Failed to upload match schedule. Error: {e}", ephemeral=True
            )
        finally:
            session.close()


async def setup(bot):
    bot.tree.add_command(Match())
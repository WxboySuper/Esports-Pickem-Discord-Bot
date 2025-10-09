# src/commands/upload_matches.py
# Admin command to upload match schedule via CSV

import logging
import discord
from discord import app_commands

from src.admin_utils import is_admin
from src.db import engine
from sqlmodel import Session
from src import crud
from src.csv_utils import parse_match_csv

logger = logging.getLogger("esports-bot.commands.upload_matches")


async def setup(bot):
    @bot.tree.command(
        name="upload_matches",
        description="[Admin] Upload match schedule via CSV file"
    )
    @app_commands.describe(
        contest_id="Contest ID to add matches to",
        csv_file="CSV file with columns: scheduled_time, team1, team2, "
                 "[external_id]"
    )
    async def upload_matches(
        interaction: discord.Interaction,
        contest_id: int,
        csv_file: discord.Attachment
    ):
        logger.debug(
            "upload_matches command invoked by user %s",
            interaction.user.id
        )

        # Check admin permissions
        if not is_admin(interaction.user.id):
            await interaction.response.send_message(
                "❌ You do not have permission to use this command.",
                ephemeral=True
            )
            return

        # Defer response as file download and processing may take time
        await interaction.response.defer(ephemeral=True)

        # Validate file type
        if not csv_file.filename.endswith('.csv'):
            await interaction.followup.send(
                "❌ File must be a CSV file (.csv extension).",
                ephemeral=True
            )
            return

        # Validate file size (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        if csv_file.size > max_size:
            await interaction.followup.send(
                f"❌ File is too large ({csv_file.size} bytes). "
                f"Maximum allowed size is {max_size} bytes.",
                ephemeral=True
            )
            return

        try:
            # Download and read CSV file
            csv_content = await csv_file.read()
            csv_text = csv_content.decode('utf-8')

            # Parse CSV
            valid_rows, errors = parse_match_csv(csv_text)

            # Check if contest exists
            with Session(engine) as session:
                contest = crud.get_contest_by_id(session, contest_id)
                if not contest:
                    await interaction.followup.send(
                        f"❌ Contest with ID {contest_id} not found.",
                        ephemeral=True
                    )
                    return

                # If there are parsing errors, report them
                if errors:
                    error_msg = "❌ **CSV Validation Errors:**\n" + \
                                "\n".join(f"• {err}" for err in errors[:10])
                    if len(errors) > 10:
                        error_msg += f"\n... and {len(errors) - 10} more"

                    # Still show valid row count if any
                    if valid_rows:
                        error_msg += (
                            f"\n\n✅ {len(valid_rows)} valid rows found, "
                            "but not imported due to errors."
                        )

                    await interaction.followup.send(
                        error_msg,
                        ephemeral=True
                    )
                    return

                # No valid rows found
                if not valid_rows:
                    await interaction.followup.send(
                        "❌ No valid matches found in CSV file.",
                        ephemeral=True
                    )
                    return

                # Create matches
                created_count = 0
                skipped_count = 0
                match_errors = []

                for row in valid_rows:
                    try:
                        crud.create_match(
                            session,
                            contest_id=contest_id,
                            team1=row["team1"],
                            team2=row["team2"],
                            scheduled_time=row["scheduled_time"]
                        )
                        created_count += 1
                    except Exception as e:
                        skipped_count += 1
                        match_errors.append(
                            f"Failed to create match "
                            f"{row['team1']} vs {row['team2']}: {e}"
                        )
                        logger.warning(
                            "Failed to create match: %s",
                            e
                        )

                # Build success message
                embed = discord.Embed(
                    title="✅ Match Upload Complete",
                    description=f"Matches uploaded to contest "
                                f"**{contest.name}**",
                    color=0x2ecc71
                )
                embed.add_field(
                    name="Created",
                    value=str(created_count),
                    inline=True
                )
                if skipped_count > 0:
                    embed.add_field(
                        name="Skipped (errors)",
                        value=str(skipped_count),
                        inline=True
                    )
                    embed.color = 0xe67e22  # Orange for partial success

                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True
                )

                # Send error details if any
                if match_errors:
                    error_details = "**Error details:**\n" + \
                                  "\n".join(f"• {err}"
                                            for err in match_errors[:5])
                    if len(match_errors) > 5:
                        error_details += (
                            f"\n... and {len(match_errors) - 5} more"
                        )
                    await interaction.followup.send(
                        error_details,
                        ephemeral=True
                    )

                logger.info(
                    "Matches uploaded: contest_id=%s, created=%s, "
                    "skipped=%s by user %s",
                    contest_id,
                    created_count,
                    skipped_count,
                    interaction.user.id
                )

        except UnicodeDecodeError:
            await interaction.followup.send(
                "❌ Error reading CSV file. Please ensure it is UTF-8 "
                "encoded.",
                ephemeral=True
            )
        except Exception as e:
            logger.exception("Error uploading matches")
            await interaction.followup.send(
                f"❌ Error uploading matches: {e}",
                ephemeral=True
            )

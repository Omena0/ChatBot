import discord

async def create_help_embed(interaction, devId):
    """Create the help embed for the bot commands"""
    help_embed = discord.Embed(
        title="ChatBot V2 Help",
        description="Here's how to use the ChatBot:",
        color=discord.Color.blue()
    )

    # General usage section
    help_embed.add_field(
        name="General Usage",
        value="- Mention the bot with your question/prompt\n"
              "- For private conversations, use /prompt or DM the bot",
        inline=False
    )

    # Available commands section
    help_embed.add_field(
        name="Available Commands",
        value="/prompt - Send a private prompt to the bot\n"
              "/help - Show this help message",
        inline=False
    )

    # Admin commands (if applicable)
    if interaction.user.id == devId:
        help_embed.add_field(
            name="Admin Commands",
            value="/set_model_params - Adjust model generation parameters\n"
                  "/history_stats - View message history statistics\n"
                  "/save_history - Manually save message history\n"
                  "/wipe_memory - Clear bot's memory\n"
                  "/rescrape - Re-collect messages from channels\n"
                  "/show_log - View the bot's log\n"
                  "/reboot - Restart the bot",
            inline=False
        )

    # Tips section
    help_embed.add_field(
        name="Tips for Better Responses",
        value="- Be specific in your questions\n"
              "- For complex topics, break into multiple questions\n"
              "- The bot remembers conversation context\n"
              "- For private questions, use /prompt or DMs",
        inline=False
    )

    return help_embed

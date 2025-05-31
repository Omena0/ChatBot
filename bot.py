from benchmark import Benchmarker, BENCHMARK_PROMPTS
from topic_detection import detect_message_topic
from context_manager import ContextManager
from discord import app_commands
import subprocess
import asyncio
import discord
import ollama
import json
import time
import os

stats = json.load(open('stats.json'))

os.system('cls||clear')

try: os.chdir('/home/omena0/bot')
except: os.chdir(f'{os.path.dirname(os.path.abspath(__file__))}')

ai:ollama.AsyncClient = ollama.AsyncClient()

model = 'deepseek-r1:1.5b'

bio = """
The Achievement SMP's new AI ChatBot!
Ping me and I'll try to help!
Discord: https://discord.gg/8MrQAhDdbM

--- Statistics ---
<stats>
------------------
""".strip()

sysPrompt = """You are a helpful assistant named ChatBot V2 inside a chat platform (Discord).
The server you're in is about a Minecraft server called the Achievement SMP. To get in it you have to apply by submitting a form.
In the achievement smp you gain points when you complete Minecraft achievements and you can use those to buy spells."""

history = []
privHistory = {}

generating = False
preloading = False

# Context optimization settings
context_settings = {
    'max_tokens': 100_000,      # Maximum tokens to keep in context
    'remove_thinking': True,  # Remove thinking parts from context
    'recency_weight': 0.6,    # Weight for message recency in scoring (0-1)
    'relevance_weight': 0.4,  # Weight for topic relevance in scoring (0-1)
}

# Initialize the context manager
context_manager = ContextManager(
    max_tokens=context_settings['max_tokens'],
    recency_weight=context_settings['recency_weight'],
    relevance_weight=context_settings['relevance_weight'],
    remove_thinking=context_settings['remove_thinking']
)

# Default model parameters
model_params = {
    'temperature': 0.75,
    'mirostat': 2.0,
    'tfs_z': 2.0
}

# Load model settings if they exist
try:
    with open('model_settings.json', 'r') as f:
        loaded_params = json.load(f)
        model_params.update(loaded_params)
        print(f"Loaded model parameters: {model_params}")
except (FileNotFoundError, json.JSONDecodeError):
    print("No model settings found, using defaults")

# Load context optimization settings if they exist
try:
    with open('context_settings.json', 'r') as f:
        loaded_settings = json.load(f)
        context_settings.update(loaded_settings)
        print(f"Loaded context optimization settings: {context_settings}")

except (FileNotFoundError, json.JSONDecodeError):
    print("No context optimization settings found, using defaults")
    with open('context_settings.json', 'w') as f:
        json.dump(context_settings, f)

devId = 665320537223987229

intents = discord.Intents.default().all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
guild = discord.Object(id=1287014795303845919)


try: os.remove('bot.log')
except: ...

print_ = print

def print(*args, end='\n', flush=False):
    print_(*args, end=end,flush=flush)
    with open('bot.log', 'a', encoding='utf-8') as f:
        f.write(' '.join(map(str, args))+end)

async def thinking_animation(message_obj, is_embed=True, title="Response [V2]"):
    """
    Display a thinking animation with dots (1-4) on a Discord message

    Args:
        message_obj: Discord message object to edit
        is_embed: Whether the message is an embed or plain text
        title: Title for embed if is_embed is True
    """
    dots = 1
    while True:
        thinking_text = f"Thinking{'.' * dots}"
        try:
            if is_embed:
                await message_obj.edit(embed=discord.Embed(title=title, description=thinking_text))
            else:
                await message_obj.edit(content=thinking_text)
        except:
            # Message might have been deleted
            break

        dots = dots % 4 + 1  # Cycle through 1-4 dots
        await asyncio.sleep(0.7)  # Update animation every 0.7 seconds

def estimate_tokens(text):
    """
    Estimate the number of tokens in text
    A rough approximation of 4 characters per token

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0
    return len(text) // 4  # Simple approximation of tokens

skip_channels = ['partners', '✨・controls', 'discord-spam']
priority_channels = ['announcements', 'updates']

async def scrape_channel_history(guild:discord.Guild, target_tokens=25_000, messages_per_channel=200):
    """
    Scrape message history from all accessible channels. Priority channels are fully scraped
    regardless of token count, then regular channels are scraped up to the token limit.
    Messages are sorted by creation date across all channels (oldest first, newest last).

    Args:
        guild: Discord guild to scrape
        target_tokens: Approximate number of tokens to collect (applies only to regular channels)
        messages_per_channel: Maximum number of messages to fetch per channel

    Returns:
        List of messages in history format (oldest first)
    """
    global history
    all_messages = []  # List to store message data with timestamps
    print(f"Scraping channels - priority channels fully, then regular channels up to ~{target_tokens} tokens...")
    
    # Current token count (only relevant for regular channels)
    current_tokens = 0

    # Get all text channels in the guild
    all_text_channels = [channel for channel in guild.channels if isinstance(channel, discord.TextChannel)]

    # Organize channels by priority
    priority_text_channels = [c for c in all_text_channels if c.name in priority_channels]
    regular_text_channels = [c for c in all_text_channels if c.name not in priority_channels and c.name not in skip_channels]

    # Sort each group by position for more natural order
    priority_text_channels.sort(key=lambda c: c.position)
    regular_text_channels.sort(key=lambda c: c.position)

    # First scrape all priority channels completely
    for channel in priority_text_channels:
        # Check if the bot has permissions to read the channel
        if not channel.permissions_for(guild.default_role).read_messages:
            continue

        print(f"Scraping PRIORITY channel #{channel.name} (no token limit)")
        
        try:
            async for message in channel.history(limit=messages_per_channel):
                # Skip messages from the bot itself
                if message.author == client.user:
                    continue

                author = message.author
                msg = message.content

                if not msg:
                    continue

                # Convert mentions, channels, and roles
                for mention in message.mentions:
                    msg = msg.replace(f'<@{mention.id}>', f'@{mention.display_name}')
                for ch in message.channel_mentions:
                    msg = msg.replace(f'<#{ch.id}>', f'#{ch.name}')
                for role in message.role_mentions:
                    msg = msg.replace(f'<@&{role.id}>', f'@{role.name}')

                # Calculate tokens for this message
                msg_tokens = estimate_tokens(msg)
                current_tokens += msg_tokens
                
                # Store message with timestamp and channel information
                all_messages.append({
                    'author': author.name,
                    'content': msg,
                    'timestamp': message.created_at,
                    'channel': channel.name,
                    'tokens': msg_tokens
                })
                    
        except discord.errors.Forbidden:
            print(f"Cannot access channel #{channel.name}")
            continue
    
    print(f"Scraped {len(all_messages)} messages from priority channels ({current_tokens} tokens)")
    
    # Then scrape regular channels up to the target token limit
    for channel in regular_text_channels:
        # Check if the bot has permissions to read the channel
        if not channel.permissions_for(guild.default_role).read_messages:
            continue

        print(f"Scraping regular channel #{channel.name}")
        
        try:
            async for message in channel.history(limit=messages_per_channel):
                # Skip messages from the bot itself
                if message.author == client.user:
                    continue

                author = message.author
                msg = message.content

                if not msg:
                    continue

                # Convert mentions, channels, and roles
                for mention in message.mentions:
                    msg = msg.replace(f'<@{mention.id}>', f'@{mention.display_name}')
                for ch in message.channel_mentions:
                    msg = msg.replace(f'<#{ch.id}>', f'#{ch.name}')
                for role in message.role_mentions:
                    msg = msg.replace(f'<@&{role.id}>', f'@{role.name}')

                # Calculate tokens for this message
                msg_tokens = estimate_tokens(msg)
                current_tokens += msg_tokens
                
                # Store message with timestamp and channel information
                all_messages.append({
                    'author': author.name,
                    'content': msg,
                    'timestamp': message.created_at,
                    'channel': channel.name,
                    'tokens': msg_tokens
                })
                
                # If we've reached our target for regular channels, stop collecting messages
                if current_tokens >= target_tokens:
                    print(f"Reached target token count for regular channels ({current_tokens}/{target_tokens})")
                    break
                    
        except discord.errors.Forbidden:
            print(f"Cannot access channel #{channel.name}")
            continue
            
        # If we've reached our target, stop collecting messages from more channels
        if current_tokens >= target_tokens:
            break

    # Sort messages by timestamp (oldest first)
    all_messages.sort(key=lambda m: m['timestamp'].timestamp())

    # Convert to the format used by our history
    scraped_history = [
        {'role': 'user', 'content': f"[#{msg['channel']}] {msg['author']}: {msg['content']}"}
        for msg in all_messages
    ]

    print(f"Scraped {len(scraped_history)} messages total: {current_tokens}/{target_tokens} tokens.")

    return scraped_history, current_tokens

async def check_perms(interaction,message='You do not have permission to execute this command.'):
    if interaction.user.id != devId:
        await interaction.response.send_message(message,ephemeral=True)
        return False
    return True

def save():
    json.dump(stats,open('stats.json','w'))

def save_history():
    """Save message history to a file"""
    history_data = {
        "public": history,
        "private": privHistory
    }
    with open('message_history.json', 'w') as f:
        json.dump(history_data, f)

def load_history():
    """Load message history from file or scrape channels if file doesn't exist"""
    global history, privHistory

    try:
        with open('message_history.json', 'r') as f:
            history_data = json.load(f)
            history = history_data.get("public", [])
            privHistory = history_data.get("private", {})
            print(f"Loaded {len(history)} public messages and {len(privHistory)} private conversations from file")
    except (FileNotFoundError, json.JSONDecodeError):
        print("No history file found or file corrupted. Will scrape channels when connected.")

async def setBio():
    global token
    await client.application.edit(
        description=bio.replace(
            '<stats>',
            f"""Messages seen: {stats['seen']}
                Prompts: {stats['total']}
                Public: {stats['public']}
                Private: {stats['private']}
            """.strip().replace('    ','')
        )
    )

async def setGenerating(state):
    global generating
    generating = state
    if state:
        await client.change_presence(activity=discord.CustomActivity(name='Generating...'))
    else:
        await client.change_presence(activity=discord.CustomActivity(name='Ready'))

async def privatePrompt(user,prompt,send_message,edit_message):
    if not prompt: return

    # Start generating
    await setGenerating(True)

    # Send response embed
    response_message = await send_message(
        embed=discord.Embed(
            title='Response [V2]',
            description='Thinking...'
        ),ephemeral=True
    )    # Detect topic of the prompt
    topic, confidence = detect_message_topic(prompt)
    print(f"[TOPIC] Detected topic: {topic} (confidence: {confidence:.2f})")
      # Add prompt to history with DM marker
    msg = {'role':'user','content':f'[DM] {user.name}: {prompt}'}

    # If there is no history for this user, then create a new list with the prompt in it
    if user.name not in privHistory:
        privHistory[user.name] = [msg]
    else:
    # Otherwise just add it
        privHistory[user.name].append(msg)

    # Use topic-specific focused prompt for high confidence topics
    if confidence > 0.6 and topic in ["minecraft", "discord"]:
        current_prompt = get_focused_prompt(topic)
        print(f"[PROMPT] Using focused prompt for topic: {topic}")
    else:
        current_prompt = sysPrompt

    # Optimize private history context using enhanced context manager
    optimized_history = context_manager.optimize_context(
        privHistory[user.name],
        max_messages=None if len(privHistory[user.name]) < 30 else 20
    )

    # Start with system prompt and add optimized history
    history = [current_prompt] + optimized_history

    stats['total'] += 1
    stats['private'] += 1
    save()
    await setBio()

    # Start generating tokens
    response_stream = await ai.chat(
        model,
        history,
        stream=True,
        options=model_params,
        keep_alive=-1
    )

    print(f'[PRIVATE] {user.display_name}: {prompt}')
    print('[PRIVATE] [AI] ',end='',flush=True)


    print('\n<end>\n')

    # Clean up history
    while len(privHistory[user.name]) > 49:
        privHistory[user.name].pop(0)

    # Save history to file
    save_history()

    # Stop generating
    await setGenerating(False)

@tree.command(name='system', description='Execute a console command', guild=guild)
async def system(interaction:discord.Interaction, command:str):
    if not await check_perms(interaction):
        return

    print(f'Executing command: {command}')

    output = subprocess.run(
        command,
        shell=True,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
        timeout=10
    )

    stdout = output.stdout or '<No output>'

    if output.returncode != 0:
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f'Command exited with non-zero status code: {output.returncode}',
                description=f'$ {command}\n\n{stdout}'
            ),
            ephemeral=True
        )
        print(f'Command exited with non-zero status code: {output.returncode}')
        print(stdout)
        return

    await interaction.response.send_message(
        embed=discord.Embed(
            title='Command output',
            description=f'$ {command}\n\n{stdout}'
        ),
        ephemeral=True
    )

@tree.command(name="reboot", description="Restart the bot", guild=guild)
async def reboot(interaction:discord.Interaction):
    if not await check_perms(interaction):
        return

    print('restarting')
    await interaction.response.send_message('restarting...',ephemeral=True)
    os.system('restart -s -t 0')

@tree.command(name="wipe_memory", description="Give the bot dementia", guild=guild)
async def wipe_memory(interaction:discord.Interaction):
    global history, privHistory
    if not await check_perms(interaction):
        return

    print('wiping memory')
    await interaction.response.send_message('wiping memory...',ephemeral=True)
    history = []
    privHistory = {}
    save_history()  # Save empty history to file

@tree.command(name="save_history", description="Save message history to file", guild=guild)
async def cmd_save_history(interaction:discord.Interaction):
    if not await check_perms(interaction):
        return

    print('Manually saving message history')
    save_history()
    await interaction.response.send_message('Message history saved to file',ephemeral=True)

@tree.command(name="history_stats", description="Show message history statistics", guild=guild)
async def history_stats(interaction:discord.Interaction):
    if not await check_perms(interaction):
        return

    # Calculate token statistics
    total_public_tokens = sum(estimate_tokens(msg['content']) for msg in history)
    total_private_tokens = sum(
        sum(estimate_tokens(msg['content']) for msg in user_history)
        for user_history in privHistory.values()
    )

    # Count message numbers
    total_public_messages = len(history)
    total_private_conversations = len(privHistory)
    total_private_messages = sum(len(user_history) for user_history in privHistory.values())

    # Get current topic from context manager
    current_topic, topic_confidence = context_manager.get_current_topic()

    stats_embed = discord.Embed(
        title="Message History Stats",
        description=f"Public messages: {total_public_messages} (~{total_public_tokens} tokens)\n"
                   f"Private conversations: {total_private_conversations}\n"
                   f"Private messages: {total_private_messages} (~{total_private_tokens} tokens)\n"
                   f"Total stored messages: {total_public_messages + total_private_messages}\n"
                   f"Estimated total tokens: {total_public_tokens + total_private_tokens}\n"
                   f"Current topic: {current_topic} (confidence: {topic_confidence:.2f})"
    )

    await interaction.response.send_message(embed=stats_embed, ephemeral=True)

@tree.command(name="run_benchmark", description="Run performance benchmark tests", guild=guild)
async def run_benchmark(interaction:discord.Interaction, prompt_type: str = "general", custom_prompt: str = None):
    """
    Run a benchmark to test different model configurations

    Args:
        prompt_type: Type of prompt to benchmark (general, minecraft, discord, factual, creative, coding)
        custom_prompt: Optional custom prompt to use instead of predefined ones
    """
    if not await check_perms(interaction):
        return

    await interaction.response.send_message("Starting benchmark, this may take a minute...", ephemeral=True)

    # Initialize benchmarker
    benchmarker = Benchmarker(model, ai)

    # Select prompt
    if custom_prompt:
        benchmark_prompt = custom_prompt
        prompt_source = "custom"
    else:
        if prompt_type in BENCHMARK_PROMPTS:
            benchmark_prompt = BENCHMARK_PROMPTS[prompt_type]
            prompt_source = prompt_type
        else:
            benchmark_prompt = BENCHMARK_PROMPTS["general"]
            prompt_source = "general (default)"

    # Run the benchmark comparisons
    results_embed = await benchmarker.run_compare_benchmarks(benchmark_prompt, history[-20:] if history else None)

    # Add prompt information to the embed
    results_embed.add_field(
        name="Benchmark Prompt",
        value=f"Type: {prompt_source}\nPrompt: {benchmark_prompt[:100]}...",
        inline=False
    )

    await interaction.followup.send(embed=results_embed, ephemeral=True)

@tree.command(name="set_model_params", description="Adjust model parameters", guild=guild)
async def set_model_params(interaction:discord.Interaction, temperature: float = None, context_size: int = None, predictable: bool = None, creative: bool = None):
    """
    Adjust model parameters to optimize generation

    Args:
        temperature: Value between 0 and 1 (lower = more focused, higher = more creative)
        context_size: Number of tokens to use for context
        predictable: Use mirostat for more predictable responses
        creative: Make responses more varied and creative (sets higher temperature)
    """
    global model_params

    if not await check_perms(interaction):
        return

    if temperature is not None:
        if 0.1 <= temperature <= 2.0:
            model_params['temperature'] = temperature
        else:
            await interaction.response.send_message("Temperature must be between 0.1 and 2.0", ephemeral=True)
            return

    if context_size is not None:
        if 1000 <= context_size <= 3000:
            model_params['num_ctx'] = context_size
        else:
            await interaction.response.send_message("Context size must be between 1000 and 3000", ephemeral=True)
            return

    if predictable is not None:
        model_params['mirostat'] = 2.0 if predictable else 0

    if creative is not None:
        if creative:
            model_params['temperature'] = 0.9
            model_params['mirostat'] = 0
        else:
            model_params['temperature'] = 0.7
            model_params['mirostat'] = 2.0

    # Save settings to file
    with open('model_settings.json', 'w') as f:
        json.dump(model_params, f)

    await interaction.response.send_message(
        embed=discord.Embed(
            title="Model parameters updated",
            description=f"Temperature: {model_params['temperature']}\n"
                       f"Context size: {model_params['num_ctx']}\n"
                       f"Mirostat: {model_params['mirostat']}\n"
                       f"TFS-Z: {model_params['tfs_z']}"
        ),
        ephemeral=True
    )

@tree.command(name="rescrape", description="Rescrape messages from all channels", guild=guild)
async def rescrape(interaction:discord.Interaction, token_limit: int = 10000, messages_per_channel: int = 200):
    if not await check_perms(interaction):
        return

    await interaction.response.send_message(f"Scraping messages with token limit: {token_limit}, messages per channel: {messages_per_channel}...", ephemeral=True)

    global history

    # Create a backup of current history
    old_history = history.copy()
    history = []

    try:
        # Scrape messages
        history, tokens = await scrape_channel_history(interaction.guild, token_limit, messages_per_channel)

        # Save the new history
        save_history()

        # Send confirmation
        await interaction.followup.send(
            f"Successfully scraped {len(history)} messages with approximately {tokens} tokens.",
            ephemeral=True
        )

    except Exception as e:
        # Restore old history if there was an error
        history = old_history
        await interaction.followup.send(f"Error scraping messages: {str(e)}\n\nRestored old history.", ephemeral=True)

    del old_history

@tree.command(name="show_log", description="View the bot's log remotely", guild=guild)
async def get_log(interaction:discord.Interaction):
    if not await check_perms(interaction):
        return

    with open('bot.log') as f:
        log = f.read()

    await interaction.response. send_message(
        embed=discord.Embed(
            title='Bot log',
            description=log
        ), ephemeral=True
    )

@tree.command(name="update", description="Update the bot to the latest version", guild=guild)
async def update(interaction:discord.Interaction):
    if not await check_perms(interaction):
        return

    os.system('git pull')
    print('Updating bot...')
    await interaction.response.send_message('Pulling changes... (/reboot to restart)',ephemeral=True, delete_after=5)

@tree.command(name='help',description='Show bot commands and usage info', guild=guild)
async def help_cmd(interaction:discord.Interaction):
    """Display help information about the bot"""

    help_embed = discord.Embed(
        title="ChatBot V2 Help",
        description="Here's how to use the ChatBot:",
        color=discord.Color.blue()
    )

    # General usage section
    help_embed.add_field(
        name="General Usage",
        value="- Mention the bot with your question/prompt\n"
              "- The bot will read all messages in public channels\n"
              "- For private conversations, use /prompt or DM the bot\n"
              "- The bot automatically detects topics and optimizes responses",
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
    if await check_perms(interaction, message=None):
        help_embed.add_field(
            name="Admin Commands",
            value="/set_model_params - Adjust model generation parameters\n"
                  "/set_response_mode - Change how responses are displayed (progressive/thinking/typing)\n"
                  "/context_settings - Configure context optimization settings\n"
                  "/set_prompt_style - Change the system prompt style\n"
                  "/history_stats - View message history statistics\n"
                  "/save_history - Manually save message history\n"
                  "/run_benchmark - Test different model configurations\n"
                  "/wipe_memory - Clear bot's memory\n"
                  "/rescrape - Re-collect messages from channels\n"
                  "/show_log - View the bot's log\n"
                  "/reboot - Restart the bot",
            inline=False
        )

        # Features section for admins
        help_embed.add_field(
            name="New Features",
            value="- **Progressive Responses**: See responses appear as they're generated\n"
                  "- **Topic Detection**: Automatically detects conversation topics\n"
                  "- **Context Optimization**: Prioritizes relevant conversation history\n"
                  "- **Response Caching**: Faster responses to common questions\n"
                  "- **Benchmark Mode**: Test different model configurations",
            inline=False
        )

    # Tips section
    help_embed.add_field(
        name="Tips for Better Responses",
        value="- Be specific in your questions\n"
              "- For complex topics, break into multiple questions\n"
              "- The bot remembers conversation context\n"
              "- For private questions, use /prompt or DMs\n"
              "- Stay on one topic for more coherent responses",
        inline=False
    )

    await interaction.response.send_message(embed=help_embed, ephemeral=True)

# This was a duplicate help command - removing to avoid conflicts

@tree.command(name='prompt',description='Privately prompt the AI', guild=guild)
async def prompt(interaction:discord.Interaction, prompt:str):
    # Dont let multiple people generating crash the system
    if generating:
        await interaction.reply("I'm already generating a response!")
        return

    # Wait until model is loaded
    if preloading:
        await interaction.reply('Loading... Try again later.')
        return

    await privatePrompt(
        interaction.user,
        prompt,
        interaction.response.send_message,
        interaction.edit_original_response
    )

@tree.command(name="context_settings", description="Adjust context optimization settings", guild=guild)
async def set_context_settings(interaction:discord.Interaction, max_tokens: int = None, remove_thinking: bool = None,
                               recency_weight: float = None, relevance_weight: float = None):
    """
    Adjust context optimization settings to improve model performance

    Args:
        max_tokens: Maximum tokens to keep in context window (500-2000)
        remove_thinking: Whether to remove thinking parts from model context
        recency_weight: Weight for message recency in scoring (0-1)
        relevance_weight: Weight for topic relevance in scoring (0-1)
    """
    global context_settings, context_manager

    if not await check_perms(interaction):
        return

    changes_made = False

    if max_tokens is not None:
        if 500 <= max_tokens <= 2000:
            context_settings['max_tokens'] = max_tokens
            context_manager.max_tokens = max_tokens
            changes_made = True
        else:
            await interaction.response.send_message("Token limit must be between 500 and 2000", ephemeral=True)
            return

    if remove_thinking is not None:
        context_settings['remove_thinking'] = remove_thinking
        context_manager.remove_thinking = remove_thinking
        changes_made = True

    if recency_weight is not None:
        if 0 <= recency_weight <= 1:
            context_settings['recency_weight'] = recency_weight
            context_manager.recency_weight = recency_weight
            changes_made = True
        else:
            await interaction.response.send_message("Recency weight must be between 0 and 1", ephemeral=True)
            return

    if relevance_weight is not None:
        if 0 <= relevance_weight <= 1:
            context_settings['relevance_weight'] = relevance_weight
            context_manager.relevance_weight = relevance_weight
            changes_made = True
        else:
            await interaction.response.send_message("Relevance weight must be between 0 and 1", ephemeral=True)
            return

    if changes_made:
        # Save settings to file
        with open('context_settings.json', 'w') as f:
            json.dump(context_settings, f)

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Context optimization settings updated",
                description=f"Max tokens: {context_settings['max_tokens']}\n"
                          f"Remove thinking parts: {context_settings['remove_thinking']}\n"
                          f"Recency weight: {context_settings['recency_weight']}\n"
                          f"Relevance weight: {context_settings['relevance_weight']}"
            ),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Current context optimization settings",
                description=f"Max tokens: {context_settings['max_tokens']}\n"
                          f"Remove thinking parts: {context_settings['remove_thinking']}\n"
                          f"Recency weight: {context_settings['recency_weight']}\n"
                          f"Relevance weight: {context_settings['relevance_weight']}"
            ),
            ephemeral=True
        )

@tree.command(name="set_response_mode", description="Change how responses are displayed", guild=guild)
async def set_response_mode(interaction:discord.Interaction, mode: str):
    """
    Change how the bot displays its responses

    Args:
        mode: "progressive", "thinking", or "typing"
    """
    global response_mode

    if not await check_perms(interaction):
        return

    # Validate and set the mode
    if response_mode.set_mode(mode.lower()):
        mode_descriptions = {
            "progressive": "Show responses as they're generated",
            "thinking": "Show thinking animation, then full response",
            "typing": "Just show Discord typing indicator"
        }

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Response mode updated",
                description=f"Mode: {mode.lower()}\n"
                          f"Description: {mode_descriptions.get(mode.lower(), '')}"
            ),
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Invalid mode. Choose from: {', '.join(response_mode.available_modes)}",
            ephemeral=True
        )

@tree.command(name="set_prompt_style", description="Change the system prompt style", guild=guild)
async def set_prompt_style(interaction:discord.Interaction, style: str = "optimized", topic: str = None):
    """
    Change the system prompt style to optimize for different use cases

    Args:
        style: "default", "optimized", or "focused"
        topic: Topic to focus on when using the "focused" style (minecraft or discord)
    """
    global sysPrompt

    if not await check_perms(interaction):
        return

    old_style = "default"
      # Determine the current style
    current_content = sysPrompt['content']
    if "helpful and concise" in current_content and len(current_content) < 200:
        old_style = "optimized"
    elif "Focus on" in current_content:
        old_style = "focused"
      # Set the new prompt style
    if style.lower() == "default":
        sysPrompt = get_default_prompt()
        new_style = "default (comprehensive)"
    elif style.lower() == "optimized":
        sysPrompt = get_optimized_prompt()
        new_style = "optimized (terse)"
    elif style.lower() == "focused":
        valid_topics = ["minecraft", "discord"]
        if topic and topic.lower() in valid_topics:
            sysPrompt = get_focused_prompt(topic.lower())
            new_style = f"focused on {topic.lower()}"
        else:
            await interaction.response.send_message(
                f"When using 'focused' style, please specify a valid topic: {', '.join(valid_topics)}",
                ephemeral=True
            )
            return
    else:
        await interaction.response.send_message(
            "Invalid style. Use 'default', 'optimized', or 'focused'.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=discord.Embed(
            title="System prompt updated",
            description=f"Changed from '{old_style}' to '{new_style}' style\n"
                       f"New prompt length: {len(sysPrompt['content'])} characters"
        ),
        ephemeral=True
    )

async def autosave_task():
    """Background task to periodically save message history"""
    await client.wait_until_ready()
    while not client.is_closed():
        await asyncio.sleep(300)  # Save every 5 minutes
        print("Auto-saving message history...")
        save_history()

@client.event
async def on_ready():
    global preloading, history, privHistory
    print(f'Logged in as {client.user}.')

    await tree.sync(guild=discord.Object(id=1287014795303845919))

    # Load message history from file
    load_history()
      # If no history file was found, scrape channels
    if len(history) == 0 and client.guilds:
        main_guild = client.get_guild(guild.id)
        if main_guild:
            print("No message history found, scraping channels...")
            history = await scrape_channel_history(main_guild, target_tokens=10000, messages_per_channel=200)
            save_history()  # Save the scraped history

    # Start autosave task
    client.loop.create_task(autosave_task())

    preloading = True
    print(f'Preloading {model}...')
    await client.change_presence(activity=discord.CustomActivity(name='Loading...'),status='dnd')
    ollama.chat(model=model,keep_alive=-1)

    preloading = False
    print('Preloaded.')
    await client.change_presence(activity=discord.CustomActivity(name='Ready'))
    await setBio()


@client.event
async def on_message(message:discord.Message):
    global generating, preloading, history

    # Ignore messages sent by the bot
    if message.author == client.user:
        return

    msg = message.content
    channel = message.channel
    author = message.author

    if not msg: return

    # Convert mentions <@{id}> -> @{display_name}
    for mention in message.mentions:
        msg = msg.replace(f'<@{mention.id}>', f'@{mention.display_name}')

    # Convert channels <#{id}> -> #{name}
    for channel in message.channel_mentions:
        msg = msg.replace(f'<#{channel.id}>', f'#{channel.name}')

    # Convert roles <@&id> -> @role_name>
    for role in message.role_mentions:
        msg = msg.replace(f'<@&{role.id}>', f'@{role.name}')

    # Is in dms
    if not message.guild:
        async def send(*args, **kwargs):
            global response
            kwargs.pop('ephemeral')
            response = await message.reply(*args,**kwargs)
        async def edit(*args, **kwargs):
            global response
            await response.edit(*args,**kwargs)
        await privatePrompt(author,msg,send,edit)

        return

    # Make sure that everyone has permissions to the messages the bot sees
    # Otherwise the bot could leak sensitive information
    if not channel.permissions_for(message.guild.default_role).read_messages:
        return

    stats['seen'] += 1
    save()
    await setBio()
    print(f'[#{channel.name}] {author.display_name}: {msg}')

    history.append({'role':'user','content':f'[#{channel.name}] {author.name}: {msg}'})
    save_history()

    # Not prompting the bot to respond
    if client.user not in message.mentions:
        print('not mentioned', message.mentions)
        return

    # Dont let multiple people generating crash the system
    if generating:
        await message.reply("I'm already generating a response!")
        return

    # Wait until model is loaded
    if preloading:
        await message.reply('Loading... Try again later.')
        return

    # Detect topic of the message
    topic, confidence = detect_message_topic(msg)
    print(f"[TOPIC] Detected topic: {topic} (confidence: {confidence:.2f})")

    # Use topic-aware context optimization
    optimized_history = context_manager.optimize_context(
        history,
        max_tokens=75_000
    )

    # Start with system prompt and add optimized history
    h = [{"role": "system", "content": sysPrompt}] + optimized_history

    stats['total'] += 1
    stats['public'] += 1
    save()
    await setBio()

    # Start generating
    await setGenerating(True)

    # Send the response embed with initial thinking message
    embed = discord.Embed(
        title='Response [V2.0]',
        description='Loading...'
    )

    response = await message.reply(embed=embed)

    # Start typing and generating tokens
    async with channel.typing():
        print('[AI] ',end='',flush=True)

        # Generate response
        stream = await ai.chat(
            model,
            h,
            stream=True,
            options=model_params,
            keep_alive=-1
        )

        resp = ''
        dot_count = 0
        last_updated = time.time()
        async for token in stream:
            token = token.message.content
            print(token,end='')

            resp += token
            # Started thinking but didn't end yet
            thinking = '<think>' in resp and '</think>' not in resp

            if thinking:
                dot_count += 1
                if dot_count > 3:
                    dot_count = 0

                embed = discord.Embed(
                   title='Response [V2.0]',
                   description=f'Thinking{'.'*dot_count}'
                )

            else:
                embed = discord.Embed(
                    title='Response [V2.0]',
                    description=resp.split('</think>')[-1].strip() if '</think>' in resp else resp
                )

            if time.time() - last_updated > 0.25:
                await response.edit(embed=embed)
                last_updated = time.time()

        print('\n<end>\n')

        await response.edit(embed=embed)

        history.append({'role':'assistant','content':f'[{channel.name}] ChatBot V2: {resp}'})

    # Use the context manager to handle pruning
    history = context_manager.optimize_context(history)

    # Save history to file
    save_history()

    # Stop generating
    await setGenerating(False)


with open('token.txt', 'rt') as f: token = f.read()

client.run(token)

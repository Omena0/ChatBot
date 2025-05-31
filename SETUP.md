
# ChatBot Setup Guide

This guide will help you set up and run the Discord chatbot powered by the tiny language model (deepseek-r1:1.5b).

## Prerequisites

1. Python 3.8 or higher
2. Ollama installed locally (<https://ollama.com/>)
3. Discord bot token

## Installation

1. Clone this repository or download all files
2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Pull the language model using Ollama:

   ```bash
   ollama pull deepseek-r1:1.5b
   ```

4. Create a file named `token.txt` in the project directory and paste your Discord bot token inside it

## Running the Bot

To start the bot:

```bash
python bot.py
```

The bot will:

1. Start up and log in to Discord
2. Preload the language model
3. Load conversation history or scrape channels for context
4. Set its status to "Ready" when available

## Using Response Modes

The bot supports three response modes:

1. **Thinking** (default): Shows a "Thinking..." animation while generating, then displays the full response
2. **Progressive**: Shows responses as they're generated in real-time
3. **Typing**: Only shows Discord typing indicator, then displays full response

To change the response mode (admin only):

```bash
/set_response_mode mode:progressive
```

## Optimizing for Better Responses

For the best performance with the tiny model:

1. Keep prompts clear and specific
2. Stay on one topic in conversations
3. Use `/context_settings` to adjust context optimization
4. Use `/run_benchmark` to test different configurations

## Troubleshooting

- If responses are slow, try decreasing `max_tokens` in context settings
- If responses are low quality, try using focused prompt style
- If the bot crashes, check that Ollama is running
- For more help, use the `/help` command

## Performance Tips

The tiny language model (deepseek-r1:1.5b) works best with:

- Shorter prompts
- Topic-specific conversations
- Progressive response mode
- Optimized context settings

Use the benchmarking tool to find the best configuration for your needs.

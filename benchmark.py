"""
Benchmarking utility for testing different bot configurations
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Tuple, Optional
import ollama
import discord

from context_optimization import optimize_context
from context_manager import ContextManager
from topic_detection import detect_message_topic

class BenchmarkResult:
    """Store and analyze benchmark results"""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        
    def add_result(self, 
                  config_name: str, 
                  generation_time: float, 
                  tokens_generated: int,
                  tokens_per_second: float,
                  context_size: int,
                  prompt_type: str):
        """Add a benchmark result"""
        self.results.append({
            "config_name": config_name,
            "generation_time": generation_time,
            "tokens_generated": tokens_generated,
            "tokens_per_second": tokens_per_second,
            "context_size": context_size,
            "prompt_type": prompt_type,
            "timestamp": time.time()
        })
        
    def get_best_config(self, priority: str = "speed") -> Optional[str]:
        """
        Get the name of the best configuration
        
        Args:
            priority: What to optimize for - "speed" or "tokens_efficiency"
            
        Returns:
            Name of the best configuration or None if no results
        """
        if not self.results:
            return None
            
        if priority == "speed":
            # Sort by tokens per second (higher is better)
            sorted_results = sorted(self.results, key=lambda x: x["tokens_per_second"], reverse=True)
        else:
            # Sort by tokens generated (higher is better) then by speed (higher is better)
            sorted_results = sorted(self.results, 
                                    key=lambda x: (x["tokens_generated"], x["tokens_per_second"]), 
                                    reverse=True)
            
        return sorted_results[0]["config_name"]

    def get_summary_embed(self) -> discord.Embed:
        """Create a Discord embed with benchmark results summary"""
        embed = discord.Embed(
            title="Benchmark Results",
            description=f"Tested {len(self.results)} configurations",
            color=discord.Color.blue()
        )
        
        if not self.results:
            embed.add_field(name="No Results", value="Run some benchmarks first", inline=False)
            return embed
            
        # Find fastest config
        fastest = max(self.results, key=lambda x: x["tokens_per_second"])
        
        # Find config that generated most tokens
        most_tokens = max(self.results, key=lambda x: x["tokens_generated"])
        
        # Add fields for the top results
        embed.add_field(
            name="Fastest Configuration",
            value=f"**{fastest['config_name']}**\n"
                  f"Speed: {fastest['tokens_per_second']:.2f} tokens/sec\n"
                  f"Tokens: {fastest['tokens_generated']}\n"
                  f"Prompt: {fastest['prompt_type']}",
            inline=True
        )
        
        embed.add_field(
            name="Most Detailed Configuration",
            value=f"**{most_tokens['config_name']}**\n"
                  f"Tokens: {most_tokens['tokens_generated']}\n"
                  f"Speed: {most_tokens['tokens_per_second']:.2f} tokens/sec\n"
                  f"Prompt: {most_tokens['prompt_type']}",
            inline=True
        )
        
        # Add all results in a compact format
        all_results = ""
        sorted_results = sorted(self.results, key=lambda x: x["tokens_per_second"], reverse=True)
        
        for result in sorted_results:
            all_results += f"**{result['config_name']}**: " \
                          f"{result['tokens_per_second']:.2f} t/s, " \
                          f"{result['tokens_generated']} tokens, " \
                          f"{result['generation_time']:.2f}s\n"
                          
        embed.add_field(
            name="All Test Results (Sorted by Speed)",
            value=all_results,
            inline=False
        )
        
        return embed
        
    def save_to_file(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
            
    def load_from_file(self, filename: str = "benchmark_results.json") -> bool:
        """Load benchmark results from file"""
        try:
            with open(filename, "r") as f:
                self.results = json.load(f)
            return True
        except (FileNotFoundError, json.JSONDecodeError):
            return False

class Benchmarker:
    """Run benchmarks with different configurations"""
    
    def __init__(self, model: str, client):
        """
        Initialize the benchmarker
        
        Args:
            model: The model name to benchmark
            client: Ollama AsyncClient instance
        """
        self.model = model
        self.client = client
        self.results = BenchmarkResult()
        self.standard_params = {
            'temperature': 0.7,
            'num_predict': 200,
            'stop': ['<end>', '<stop>', 'User: ', '<|']
        }
        
    async def run_benchmark(self, 
                          config_name: str,
                          prompt: str,
                          history: List[Dict[str, Any]] = None,
                          system_prompt_type: str = "optimized",
                          context_optimizer = None,
                          model_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run a single benchmark
        
        Args:
            config_name: Name of this configuration
            prompt: The prompt to use for benchmarking
            history: Optional conversation history
            system_prompt_type: Type of system prompt to use
            context_optimizer: Optional context optimizer to use
            model_params: Optional model parameters to use
            
        Returns:
            Dictionary with benchmark results
        """
        # Prepare the prompt
        if system_prompt_type == "default":
            system_prompt = get_default_prompt()
        elif system_prompt_type == "focused":
            topic, _ = detect_message_topic(prompt)
            system_prompt = get_focused_prompt(topic)
        else:
            system_prompt = get_default_prompt()

    # Format the user prompt
        user_msg = {'role': 'user', 'content': f'Benchmark: {prompt}'}
        
        # Process history if provided
        if history and context_optimizer:
            optimized_history = context_optimizer.optimize_context(history)
            messages = [system_prompt] + optimized_history + [user_msg]
        elif history:
            messages = [system_prompt] + history + [user_msg]
        else:
            messages = [system_prompt, user_msg]
            
        # Set model parameters
        params = self.standard_params.copy()
        if model_params:
            params.update(model_params)
            
        # Run the benchmark
        start_time = time.time()
        
        response = await self.client.chat(
            model=self.model,
            messages=messages,
            stream=True,
            options=params
        )
        
        # Collect response tokens
        tokens_generated = 0
        generated_text = ""
        
        async for token in response:
            token_content = token['message']['content']
            generated_text += token_content
            tokens_generated += 1
            
        end_time = time.time()
        generation_time = end_time - start_time
        
        # Calculate metrics
        tokens_per_second = tokens_generated / generation_time if generation_time > 0 else 0
        context_size = sum(len(msg["content"]) // 4 for msg in messages)  # Rough estimate
        
        # Store the result
        result = {
            "config_name": config_name,
            "generation_time": generation_time,
            "tokens_generated": tokens_generated,
            "tokens_per_second": tokens_per_second,
            "context_size": context_size,
            "prompt_type": system_prompt_type,
            "generated_text": generated_text
        }
        
        # Add to results collection
        self.results.add_result(
            config_name=config_name,
            generation_time=generation_time,
            tokens_generated=tokens_generated,
            tokens_per_second=tokens_per_second,
            context_size=context_size,
            prompt_type=system_prompt_type
        )
        
        return result

    async def run_compare_benchmarks(self, 
                                    prompt: str,
                                    history: List[Dict[str, Any]] = None) -> discord.Embed:
        """
        Run a series of benchmarks with different configurations in parallel
        
        Args:
            prompt: The prompt to use for benchmarking
            history: Optional conversation history
            
        Returns:
            Discord embed with comparison results
        """
        # Define configurations to test
        configs = [
            {
                "name": "Default",
                "system_prompt": "default",
                "context_optimizer": None,
                "params": {"temperature": 0.7, "mirostat": 0}
            },
            {
                "name": "Optimized",
                "system_prompt": "optimized",
                "context_optimizer": None,
                "params": {"temperature": 0.7, "mirostat": 0}
            },
            {
                "name": "Topic-Focused",
                "system_prompt": "focused",
                "context_optimizer": None,
                "params": {"temperature": 0.7, "mirostat": 0}
            },
            {
                "name": "Context-Optimized",
                "system_prompt": "optimized",
                "context_optimizer": ContextManager(),
                "params": {"temperature": 0.7, "mirostat": 0}
            },
            {
                "name": "Low Temperature",
                "system_prompt": "optimized",
                "context_optimizer": ContextManager(),
                "params": {"temperature": 0.3, "mirostat": 0}
            },
            {
                "name": "Mirostat Enabled",
                "system_prompt": "optimized",
                "context_optimizer": ContextManager(),
                "params": {"temperature": 0.7, "mirostat": 2.0}
            }
        ]
        
        # Create tasks for all benchmarks to run in parallel
        tasks = []
        for config in configs:
            print(f"Queuing benchmark for configuration: {config['name']}")
            
            task = self.run_benchmark(
                config_name=config["name"],
                prompt=prompt,
                history=history,
                system_prompt_type=config["system_prompt"],
                context_optimizer=config["context_optimizer"],
                model_params=config["params"]
            )
            tasks.append(task)
        
        # Run all benchmarks in parallel
        print(f"Running {len(tasks)} benchmarks in parallel...")
        await asyncio.gather(*tasks)
            
        # Save results
        self.results.save_to_file()
        
        # Return summary embed
        return self.results.get_summary_embed()

# Benchmark prompt examples for testing different capabilities
BENCHMARK_PROMPTS = {
    "general": "Tell me what you know about artificial intelligence and its applications.",
    "minecraft": "What are the best strategies for surviving the first night in Minecraft?",
    "discord": "How can I set up roles and permissions in my Discord server?",
    "factual": "What is the capital of France and what are some famous landmarks there?",
    "creative": "Write a short poem about a robot discovering emotions.",
    "coding": "Explain how to write a basic function in Python that calculates factorial."
}

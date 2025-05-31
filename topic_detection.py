"""
Topic detection for better context management
This helps identify conversation topics and provides confidence scoring for better responses
"""

from collections import Counter
import re
import random
from typing import Dict, List, Tuple, Set, Optional

# Define topic categories and associated keywords
TOPICS = {
    "minecraft": {
        "keywords": [
            "minecraft", "block", "creeper", "crafting", "mining", "smp", "survival", 
            "mob", "nether", "end", "achievements", "points", "spells", "abilities",
            "achievement smp", "dash", "heal", "grab", "bolt", "ender pearl", "fireball",
            "freeze", "lifesteal", "defense", "damage", "fall damage", "speed"
        ],
        "weight": 1.5  # Give higher weight to matching this topic (server-specific)
    },
    "discord": {
        "keywords": [
            "discord", "server", "channel", "message", "dm", "ping", "mention", "bot",
            "role", "voice", "chat", "emoji", "react", "notification", "command", "mute",
            "ban", "kick", "moderator", "admin", "permissions"
        ],
        "weight": 1.0
    },
    "gaming": {
        "keywords": [
            "game", "gaming", "player", "level", "quest", "character", "rpg", "fps", "mmo",
            "strategy", "build", "team", "play", "win", "lose", "match", "server", "client",
            "mod", "steam", "xbox", "playstation", "nintendo", "console", "pc"
        ],
        "weight": 0.8
    },
    "general": {
        "keywords": [
            "help", "question", "how", "what", "when", "where", "who", "why", "thanks",
            "hello", "hi", "hey", "nice", "good", "bad", "cool", "awesome", "interesting",
            "amazing", "terrible", "awful", "great", "wonderful", "explain", "tell"
        ],
        "weight": 0.5  # Lower weight for generic terms
    }
}

def detect_message_topic(message: str) -> Tuple[str, float]:
    """
    Detect the most likely topic of a message using keyword matching
    
    Args:
        message: The message to analyze
        
    Returns:
        Tuple of (topic_name, confidence_score)
    """
    # Normalize the message
    message = message.lower()
    
    # Calculate scores for each topic
    scores = {}
    
    for topic, topic_info in TOPICS.items():
        score = 0
        weight = topic_info.get("weight", 1.0)
        
        for keyword in topic_info["keywords"]:
            # Check for whole word matches
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = re.findall(pattern, message)
            score += len(matches) * weight
        
        scores[topic] = score
    
    # Find the topic with the highest score
    best_topic = max(scores.items(), key=lambda x: x[1])
    
    # If no clear topic was found, default to "general"
    if best_topic[1] == 0:
        return "general", 0.1
    
    # Calculate a confidence score (0-1)
    total_score = sum(scores.values())
    confidence = best_topic[1] / total_score if total_score > 0 else 0
    
    return best_topic[0], min(confidence, 1.0)

def get_topic_keywords(topic: str) -> Set[str]:
    """
    Get the keywords for a specific topic
    
    Args:
        topic: The topic name
        
    Returns:
        Set of keywords for the topic
    """
    return set(TOPICS.get(topic, {}).get("keywords", []))

def score_message_relevance(message: str, current_topic: str) -> float:
    """
    Score a message's relevance to the current topic (0-1)
    
    Args:
        message: The message to score
        current_topic: The current conversation topic
        
    Returns:
        Relevance score between 0 and 1
    """
    # Get keywords for the topic
    keywords = get_topic_keywords(current_topic)
    
    # If no keywords found for the topic, assume moderate relevance
    if not keywords:
        return 0.5
    
    # Normalize the message
    message = message.lower()
    
    # Count keyword matches
    matches = 0
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, message):
            matches += 1
    
    # Calculate relevance score
    if not keywords:
        return 0.5
    
    # Base relevance (0.3) plus keyword match contribution
    relevance = 0.3 + (0.7 * min(matches / (len(keywords) * 0.3), 1.0))
    
    return min(relevance, 1.0)

def analyze_conversation_topics(messages: List[str]) -> Dict[str, float]:
    """
    Analyze a sequence of messages to determine the overall conversation topics
    
    Args:
        messages: List of message strings
        
    Returns:
        Dictionary of topics with their weight in the conversation
    """
    topics = []
    
    # Detect topics for each message
    for message in messages:
        topic, confidence = detect_message_topic(message)
        if confidence > 0.2:  # Only count topics with reasonable confidence
            topics.append((topic, confidence))
    
    # Count topic occurrences, weighted by confidence
    topic_weights = {}
    for topic, confidence in topics:
        topic_weights[topic] = topic_weights.get(topic, 0) + confidence
    
    # Normalize weights
    total_weight = sum(topic_weights.values()) if topic_weights else 1
    for topic in topic_weights:
        topic_weights[topic] /= total_weight
    
    return topic_weights
    
# All hallucination control functions have been removed

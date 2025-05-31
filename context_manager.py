"""
Advanced context management with topic awareness
Helps prioritize relevant messages in limited context windows
"""

from typing import List, Dict, Any, Tuple, Optional
import time

from context_optimization import estimate_tokens, remove_thinking_parts
from topic_detection import detect_message_topic, score_message_relevance

class ContextManager:
    """Manages conversation context with topic awareness"""

    def __init__(self,
                 max_tokens: int = 100_000,
                 recency_weight: float = 0.6,
                 relevance_weight: float = 0.4,
                 remove_thinking: bool = True):
        """
        Initialize the context manager

        Args:
            max_tokens: Maximum tokens to keep in context
            recency_weight: Weight for message recency in scoring (0-1)
            relevance_weight: Weight for topic relevance in scoring (0-1)
            remove_thinking: Whether to remove thinking parts from assistant responses
        """
        self.max_tokens = max_tokens
        self.recency_weight = recency_weight
        self.relevance_weight = relevance_weight
        self.remove_thinking = remove_thinking
        self.current_topic = "general"
        self.topic_confidence = 0.0

    def optimize_context(self,
                        history: List[Dict[str, Any]],
                        max_tokens: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Optimize conversation history for small language models using topic awareness

        Args:
            history: List of conversation messages
            max_tokens: Maximum number of tokens to keep

        Returns:
            Optimized conversation history
        """
        if not history:
            return history

        # Update current topic based on recent messages
        self._update_current_topic(history)

        # Create a working copy
        optimized = []
        current_tokens = 0

        # Score and sort messages by importance
        scored_messages = self._score_messages(history)

        # Process messages in order of importance
        for msg, _ in scored_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')

            # Skip empty messages
            if not content:
                continue

            # Estimate token count for this message
            message_tokens = estimate_tokens(content)

            # Apply role-specific optimizations
            if role == 'user':
                # For user messages, keep them intact - they provide important context
                optimized_content = content
                message_tokens = estimate_tokens(optimized_content)
            elif role == 'assistant':
                # For assistant messages, remove any thinking parts if enabled
                optimized_content = remove_thinking_parts(content) if self.remove_thinking else content
                message_tokens = estimate_tokens(optimized_content)
            else:
                # For system messages, keep intact
                optimized_content = content

            # If adding this message exceeds the token limit and we have at least some context
            # then stop adding more messages
            if current_tokens + message_tokens > self.max_tokens and optimized:
                break

            # Add the optimized message to our context
            optimized.append({
                'role': role,
                'content': optimized_content
            })
            current_tokens += message_tokens

            # If we've reached max_tokens, stop
            if max_tokens and current_tokens >= max_tokens:
                break

        # Return in chronological order
        return optimized

    def _update_current_topic(self, history: List[Dict[str, Any]]) -> None:
        """Update the current conversation topic based on recent messages"""
        # Extract recent user messages (last 5)
        recent_messages = []
        for msg in reversed(history):
            if msg.get('role') == 'user' and len(recent_messages) < 5:
                content = msg.get('content', '')
                # Extract the actual message from the format
                if '<|user|>' in content and '<|end|>' in content:
                    parts = content.split('<|user|>')
                    if len(parts) > 1:
                        msg_content = parts[1].split('<|end|>')[0].strip()
                        recent_messages.append(msg_content)

        # If we have recent messages, detect their topics
        if recent_messages:
            topic_counts = {}
            total_confidence = 0

            for message in recent_messages:
                topic, confidence = detect_message_topic(message)
                topic_counts[topic] = topic_counts.get(topic, 0) + confidence
                total_confidence += confidence

            # Find the most common topic
            if topic_counts:
                self.current_topic = max(topic_counts.items(), key=lambda x: x[1])[0]
                self.topic_confidence = topic_counts[self.current_topic] / total_confidence if total_confidence > 0 else 0.5
            else:
                self.current_topic = "general"
                self.topic_confidence = 0.1

    def _score_messages(self, history: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
        """
        Score messages based on recency and topic relevance

        Args:
            history: List of conversation messages

        Returns:
            List of (message, score) tuples, sorted by decreasing score
        """
        scored = []
        history_length = len(history)

        # Process each message
        for i, msg in enumerate(history):
            content = msg.get('content', '')

            # Skip empty messages
            if not content:
                continue

            # Calculate recency score (0-1) - more recent = higher score
            recency_score = i / history_length if history_length > 0 else 0

            # Calculate relevance score for this message
            relevance_score = 0.5  # Default medium relevance

            # Extract the actual message from the format
            clean_content = content
            if '<|user|>' in content and '<|end|>' in content:
                parts = content.split('<|user|>')
                if len(parts) > 1:
                    clean_content = parts[1].split('<|end|>')[0].strip()

            # Score relevance based on topic
            relevance_score = score_message_relevance(clean_content, self.current_topic)

            # Combine scores - weight recency and relevance appropriately
            combined_score = (
                recency_score * self.recency_weight +
                relevance_score * self.relevance_weight
            )

            # System messages always get high priority
            if msg.get('role') == 'system':
                combined_score = 5.0

            scored.append((msg, combined_score))

        # Sort by score in descending order
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def get_current_topic(self) -> Tuple[str, float]:
        """
        Get the current detected conversation topic

        Returns:
            Tuple of (topic_name, confidence_score)
        """
        return self.current_topic, self.topic_confidence

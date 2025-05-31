"""
Context optimization for small language models
This module helps with context pruning and optimization for small LLMs
"""

def optimize_context(history, max_tokens=100_000, max_messages=None):
    """
    Optimizes conversation history for small language models by:
    1. Keeping only essential parts of messages (removing thinking parts)
    2. Prioritizing recent and important messages
    3. Ensuring the context stays within token limits
    
    Args:
        history: List of conversation messages
        max_tokens: Maximum number of tokens to keep in context
        max_messages: Maximum number of messages to keep (if None, determined by tokens)
        
    Returns:
        Optimized conversation history
    """
    if not history:
        return history
        
    # Create a working copy
    optimized = []
    current_tokens = 0
    
    # Process messages from newest to oldest (most recent first)
    for msg in reversed(history):
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
            # For assistant messages, remove any thinking parts
            # Thinking often starts with phrases like "let me think" or appears in sections
            optimized_content = remove_thinking_parts(content)
            message_tokens = estimate_tokens(optimized_content)
        else:
            # For system messages, keep intact
            optimized_content = content
            
        # If adding this message exceeds the token limit and we have at least some context
        # then stop adding more messages
        if current_tokens + message_tokens > max_tokens and optimized:
            break
            
        # Add the optimized message to our context
        optimized.append({
            'role': role,
            'content': optimized_content
        })
        current_tokens += message_tokens
        
        # If we've reached max_messages, stop
        if max_messages and len(optimized) >= max_messages:
            break
            
    # Reverse back to chronological order (oldest first)
    optimized.reverse()
    
    return optimized

def remove_thinking_parts(text):
    """
    Remove thinking parts from assistant responses.
    
    Args:
        text: The response text
        
    Returns:
        Text with thinking parts removed
    """
    if '</think>' not in text:
        return text

    result = text.split('</think>',1)[-1].strip()

    return result

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

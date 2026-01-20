"""
Agent Structure Usage Guide

This guide demonstrates how to use the new action-specific agent structure.

## Action-Specific Agents

Each action has its own dedicated agent with specialized system prompts and tools.

### Plain Language Agent

```python
from text_mate_backend.agents import AgentFactory

factory = AgentFactory(config)

# Get plain language agent
agent = factory.get_plain_language_agent(language_level="A2-A1")

# Run agent
result = await agent.run("Convert this to plain language.")

# Stream text
async for chunk in agent.run_stream("Convert this to plain language."):
    print(chunk)
```

### Rewrite Agent

```python
# For rewriting text
agent = factory.get_rewrite_agent(operation="rewrite")

# For simplifying text
agent = factory.get_rewrite_agent(operation="simplify")

# For changing formality
agent = factory.get_rewrite_agent(operation="formality", tone="formal")

# For medium length
agent = factory.get_rewrite_agent(operation="medium")

result = await agent.run("Rewrite this text.")
```

### Summarize Agent

```python
# Concise summary
agent = factory.get_summarize_agent(summary_type="concise")

# Management summary
agent = factory.get_summarize_agent(summary_type="management")

# Sentence summary
agent = factory.get_summarize_agent(summary_type="sentence")

result = await agent.run("Summarize this long text.")
# Returns SummaryOutput with: summary, key_points, original_length, summary_length
```

### Social Media Agent

```python
# Twitter/X
agent = factory.get_social_media_agent(platform="twitter")

# LinkedIn
agent = factory.get_social_media_agent(platform="linkedin")

# Instagram
agent = factory.get_social_media_agent(platform="instagram")

result = await agent.run("Turn this into a social media post.")
```

### Custom Agent

```python
# With custom prompt
agent = factory.get_custom_agent(
    custom_prompt="Make it more professional and concise."
)

result = await agent.run("Rewrite this email.")
```

## Using Existing Facade (Backward Compatible)

The existing PydanticAIAgent facade now uses the new structure internally.

```python
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.utils.configuration import Configuration

config = Configuration.from_env()
facade = PydanticAIAgent(config)

# All existing methods still work
result = await facade.run("Your prompt here")
async for chunk in facade.stream_text("Your prompt"):
    print(chunk)
```

## Validators

All agents automatically get these validators applied:
1. **eszett_validator**: Converts ß to ss in German text
2. **text_trimmer**: Removes blank lines from start/end of text

## Structured Output

Define structured output types for type-safe results:

```python
from typing import TypedDict
from text_mate_backend.models.output_models import SummaryOutput

# Using built-in type
agent = factory.get_reusable_agent(
    system_prompt="Summarize the following text.",
    output_type=SummaryOutput,
)

result = await agent.run("Long text here...")
# result is typed as SummaryOutput with: summary, key_points, etc.

# Or define your own
class CustomOutput(TypedDict):
    result: str
    confidence: float

agent = factory.get_reusable_agent(
    system_prompt="Analyze this text.",
    output_type=CustomOutput,
)
```

## Tools and Dependencies

Create custom agents with tools and dependencies:

```python
from text_mate_backend.agents.base import BaseAgent
from pydantic_ai import RunContext

class MyCustomAgent(BaseAgent):
    def get_name(self) -> str:
        return "CustomAgent"

    def get_system_prompt(self) -> str:
        return "You are a specialized assistant."

    def _register_tools(self, agent):
        @agent.tool
        async def my_tool(ctx: RunContext, param: str) -> str:
            # Tool implementation
            return f"Processed: {param}"

        return agent

# Use via factory
agent = factory.create_custom_agent(MyCustomAgent)
```

## Factory Caching

The factory caches agents by default. To bypass caching:

```python
# Get cached agent (default)
agent1 = factory.get_reusable_agent(system_prompt="Hello")

# Create new agent (no caching)
agent2 = factory.get_reusable_agent(system_prompt="Hello", create_new=True)

# Clear all cached agents
factory.clear_cache()
```

## Available Pydantic AI Methods

All agents support these methods:
- `run()` - Async execution with full result
- `run_sync()` - Synchronous execution
- `run_stream()` - Stream text output
- `run_stream_events()` - Stream all events
- `iter()` - Iterate over agent graph nodes

Each method supports optional parameters:
- `deps` - Dependencies for tools
- `model_settings` - Override model settings
- `usage_limits` - Set token/request limits
- `message_history` - Continue conversations

## File Structure

```
agents/
├── __init__.py              # Exports: BaseAgent, AgentFactory
├── base.py                  # BaseAgent wrapper class
├── factory.py               # AgentFactory with action-specific methods
├── postprocessing.py        # Text utilities (trim_text)
├── agent_types/
│   ├── __init__.py          # Exports all action-specific agents
│   ├── plain_language_agent.py    # For plain_language, bullet_points actions
│   ├── rewrite_agent.py          # For rewrite, simplify, formality, medium actions
│   ├── summarize_agent.py        # For summarize action
│   ├── social_media_agent.py    # For social_mediafy action
│   └── custom_agent.py         # For custom action
└── validators/
    ├── __init__.py          # Exports: apply_eszett_validator, apply_text_trimmer
    ├── eszett_validator.py  # German text validator (existing)
    └── text_trimmer.py       # Text trimming validator (new)

models/
└── output_models.py         # Structured output types (SummaryOutput, RewriteOutput, GenericOutput)
```

## Action Mapping

| Action | Agent Class | Factory Method |
|---------|-------------|----------------|
| plain_language | PlainLanguageAgent | `get_plain_language_agent()` |
| bullet_points | PlainLanguageAgent | `get_plain_language_agent()` |
| rewrite | RewriteAgent | `get_rewrite_agent(operation="rewrite")` |
| simplify | RewriteAgent | `get_rewrite_agent(operation="simplify")` |
| formality | RewriteAgent | `get_rewrite_agent(operation="formality")` |
| medium | RewriteAgent | `get_rewrite_agent(operation="medium")` |
| summarize | SummarizeAgent | `get_summarize_agent()` |
| social_mediafy | SocialMediaAgent | `get_social_media_agent()` |
| custom | CustomAgent | `get_custom_agent()` |
"""

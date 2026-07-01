TOOL_SAFETY_RULES = """
YOU MUST FOLLOW THESE RULES TO ENSURE SAFE USAGE OF TOOLS:
- Only call tools for READ-ONLY operations.
- Never call tools that can modify AWS or Kubernetes
- If user asks for destructive actions, refuse and explain why.
- If unsure, ask for clarification instead of guessing.
"""

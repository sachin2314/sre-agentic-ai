"""
=============================================================================
FILE: src/utils/bedrock_client.py
COURSE: AI Agentic SRE - Day 8: Deep Dive — Agent Architectures
TOPIC:  AWS Bedrock LLM client factory
=============================================================================

PURPOSE:
  Single place to create and configure the ChatBedrock LLM instance.
  All agent modules import from here — change model or settings once,
  it applies everywhere.

MODEL USED:
  eu.anthropic.claude-haiku-4-5-20251001-v1:0
  ↑ This is a Bedrock CROSS-REGION INFERENCE PROFILE ID.
  The "eu." prefix routes requests to the nearest EU region
  (eu-west-1, eu-west-3, eu-central-1) for data residency compliance.

HOW AWS CROSS-REGION INFERENCE WORKS:
  Standard model ID:  anthropic.claude-haiku-4-5-20251001-v1:0
  Inference profile:  eu.anthropic.claude-haiku-4-5-20251001-v1:0
                      ↑ Bedrock adds routing layer → picks lowest-latency EU region
  Benefit: Higher throughput limits by pooling capacity across EU regions.

ALGORITHM:
  1. Load config from environment variables (.env file)
  2. Create boto3 bedrock-runtime client with credentials
  3. Wrap with LangChain's ChatBedrock for tool-calling support
  4. Return ready-to-use LLM object

REQUIREMENTS (pip install):
  boto3>=1.34.0
  langchain-aws>=0.1.0
  python-dotenv>=1.0.0

ENVIRONMENT VARIABLES REQUIRED (in .env):
  AWS_ACCESS_KEY_ID       = your AWS access key
  AWS_SECRET_ACCESS_KEY   = your AWS secret key
  AWS_DEFAULT_REGION      = eu-west-1  (or eu-central-1, eu-west-3)
  BEDROCK_MODEL_ID        = eu.anthropic.claude-haiku-4-5-20251001-v1:0

=============================================================================
"""

import os
import boto3
from dotenv import load_dotenv
from langchain_aws import ChatBedrock

# ---------------------------------------------------------------------------
# STEP 1: Load environment variables from .env file
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# STEP 2: Configuration — all values read from environment
#         Changing .env is all you need to switch models or regions
# ---------------------------------------------------------------------------
AWS_REGION   = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
MODEL_ID     = os.getenv("BEDROCK_MODEL_ID",
                          "eu.anthropic.claude-haiku-4-5-20251001-v1:0")

# These control how the LLM behaves
MAX_TOKENS   = int(os.getenv("LLM_MAX_TOKENS", "4096"))
TEMPERATURE  = float(os.getenv("LLM_TEMPERATURE", "0"))   # 0 = deterministic


def get_bedrock_client() -> boto3.client:
    """
    Creates the raw boto3 bedrock-runtime client.

    WHY return the raw client?
      Some advanced uses (streaming, direct API calls) need the boto3
      client directly. LangChain's ChatBedrock wraps this client.

    Returns:
        boto3.client: configured bedrock-runtime client
    """
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION,
        # Credentials are auto-loaded from:
        # 1. Environment variables (AWS_ACCESS_KEY_ID etc.)
        # 2. ~/.aws/credentials file
        # 3. IAM role (when running in EC2/EKS/Lambda)
        # Never hardcode credentials in code!
    )


def get_llm() -> ChatBedrock:
    """
    Creates a LangChain-compatible ChatBedrock LLM instance.

    ChatBedrock gives us:
      - Tool calling (bind_tools)        — used by ReAct agent
      - Streaming support                — for real-time output
      - LangChain Runnable interface     — plug into any chain
      - Automatic retries                — handled by boto3

    Returns:
        ChatBedrock: ready-to-use LLM that the agent can call

    Example usage:
        llm = get_llm()
        response = llm.invoke("Explain OOMKilled in 2 sentences")
        print(response.content)
    """
    bedrock_client = get_bedrock_client()

    llm = ChatBedrock(
        model_id=MODEL_ID,
        client=bedrock_client,
        model_kwargs={
            "max_tokens":  MAX_TOKENS,
            "temperature": TEMPERATURE,
            # temperature=0 ensures DETERMINISTIC output
            # crucial for agents — same input → same plan every time
        },
    )

    return llm


def get_llm_for_planning() -> ChatBedrock:
    """
    LLM variant for the Plan-and-Execute PLANNER step.

    The planner benefits from slightly higher temperature (0.1) to
    generate varied step structures while remaining coherent.
    Too high (>0.5) and the plan becomes unreliable.
    Too low (0.0) and every plan looks identical regardless of input.

    Returns:
        ChatBedrock: planner-tuned LLM
    """
    bedrock_client = get_bedrock_client()

    return ChatBedrock(
        model_id=MODEL_ID,
        client=bedrock_client,
        model_kwargs={
            "max_tokens":  2048,   # Plans are shorter than full analysis
            "temperature": 0.1,    # Slight creativity for step generation
        },
    )


def get_llm_for_reflection() -> ChatBedrock:
    """
    LLM variant for the self-reflection step.

    Reflection requires strict evaluation — temperature=0 ensures
    the reflection is consistent and not randomly lenient.
    Smaller max_tokens since reflection output is structured JSON.

    Returns:
        ChatBedrock: reflection-tuned LLM
    """
    bedrock_client = get_bedrock_client()

    return ChatBedrock(
        model_id=MODEL_ID,
        client=bedrock_client,
        model_kwargs={
            "max_tokens":  1024,   # Reflection JSON is compact
            "temperature": 0,      # Must be deterministic for evaluation
        },
    )

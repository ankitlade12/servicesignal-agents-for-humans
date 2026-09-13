"""Check provider availability without printing secrets or account identifiers."""

import json
import os

import boto3
from botocore.config import Config

os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
session = boto3.Session()
config = Config(connect_timeout=8, read_timeout=15, retries={"max_attempts": 0})
try:
    session.client("sts", config=config).get_caller_identity()
    print("AWS identity: authenticated")
    bedrock = session.client("bedrock", region_name=os.getenv("AWS_REGION", "us-east-1"), config=config)
    models = bedrock.list_foundation_models(byProvider="Anthropic")["modelSummaries"]
    print(json.dumps({"bedrock_models": [m["modelId"] for m in models if "haiku" in m["modelId"]]}, indent=2))
except Exception as error:
    print("AWS access:", type(error).__name__)

import json
import asyncio
from app import JOB_REGISTRY
print(json.dumps(JOB_REGISTRY._active, default=str, indent=2))

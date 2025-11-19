try:
    from langfuse.decorators import langfuse_context

    print("from langfuse.decorators import langfuse_context: SUCCESS")
except ImportError as e:
    print(f"from langfuse.decorators import langfuse_context: FAILED ({e})")

try:
    from langfuse import langfuse_context

    print("from langfuse import langfuse_context: SUCCESS")
except ImportError as e:
    print(f"from langfuse import langfuse_context: FAILED ({e})")

import langfuse

print(
    f"langfuse version: {langfuse.version.__version__ if hasattr(langfuse, 'version') else 'unknown'}"
)
print("langfuse dir:", dir(langfuse))

import adalflow as adal

from deepwiki_cli.infrastructure.config import configs, get_embedder_type


def get_embedder(
    is_local_lmstudio: bool = False,
    embedder_type: str | None = None,
) -> adal.Embedder:
    """Get embedder based on configuration or parameters.

    Args:
        is_local_lmstudio: Legacy parameter for LM Studio embedder
        embedder_type: Direct specification of embedder type ('lmstudio', 'openrouter', 'openai')

    Returns:
        adal.Embedder: Configured embedder instance
    """
    # Determine which embedder config to use
    if embedder_type:
        if embedder_type == "lmstudio":
            embedder_config = configs["embedder_lmstudio"]
        elif embedder_type == "openrouter":
            embedder_config = configs["embedder_openrouter"]
        elif embedder_type == "openai":
            embedder_config = configs.get("embedder_openai", configs["embedder"])
        else:  # default to openai
            embedder_config = configs.get("embedder_openai", configs["embedder"])
    elif is_local_lmstudio:
        embedder_config = configs["embedder_lmstudio"]
    else:
        # Auto-detect based on current configuration
        current_type = get_embedder_type()
        if current_type == "lmstudio":
            embedder_config = configs["embedder_lmstudio"]
        elif current_type == "openrouter":
            embedder_config = configs["embedder_openrouter"]
        else:
            embedder_config = configs.get("embedder_openai", configs["embedder"])

    # --- Initialize Embedder ---
    model_client_class = embedder_config["model_client"]
    if "initialize_kwargs" in embedder_config:
        model_client = model_client_class(**embedder_config["initialize_kwargs"])
    else:
        model_client = model_client_class()

    # Create embedder with basic parameters
    embedder_kwargs = {
        "model_client": model_client,
        "model_kwargs": embedder_config["model_kwargs"],
    }

    embedder = adal.Embedder(**embedder_kwargs)

    # Set batch_size as an attribute if available (not a constructor parameter)
    if "batch_size" in embedder_config:
        embedder.batch_size = embedder_config["batch_size"]
    return embedder

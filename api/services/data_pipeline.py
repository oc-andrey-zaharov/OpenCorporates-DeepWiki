import base64
import contextlib
import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import adalflow as adal
import requests
import tiktoken
from adalflow.components.data_process import TextSplitter, ToEmbeddings
from adalflow.core.db import LocalDB
from adalflow.core.types import Document, List
from adalflow.utils import get_adalflow_default_root_path
from requests.exceptions import RequestException

from api.config import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_FILES, configs
from api.ollama_patch import OllamaDocumentProcessor
from api.tools.embedder import get_embedder
from api.utils.repo_scanner import collect_repository_files

# Configure logging
logger = logging.getLogger(__name__)

# Maximum token limit for OpenAI embedding models
MAX_EMBEDDING_TOKENS = 8192

# Multiplier for code files token limit (configurable via configs)
# Default to 2 for safety, but can be overridden in config
CODE_FILE_TOKEN_MULTIPLIER = 2


# Cache encoding objects to avoid repeated initialization
_encoding_cache = {}


def _get_encoding(embedder_type: str):
    """Get or create cached encoding object."""
    if embedder_type not in _encoding_cache:
        if embedder_type in {"ollama", "google"}:
            _encoding_cache[embedder_type] = tiktoken.get_encoding("cl100k_base")
        else:  # OpenAI or default
            _encoding_cache[embedder_type] = tiktoken.encoding_for_model(
                "text-embedding-3-small",
            )
    return _encoding_cache[embedder_type]


def count_tokens(
    text: str, embedder_type: str | None = None, is_ollama_embedder: bool | None = None,
) -> int:
    """Count the number of tokens in a text string using tiktoken.

    Args:
        text (str): The text to count tokens for.
        embedder_type (str, optional): The embedder type ('openai', 'google', 'ollama').
                                     If None, will be determined from configuration.
        is_ollama_embedder (bool, optional): DEPRECATED. Use embedder_type instead.
                                           If None, will be determined from configuration.

    Returns:
        int: The number of tokens in the text.
    """
    try:
        # Handle backward compatibility
        if embedder_type is None and is_ollama_embedder is not None:
            embedder_type = "ollama" if is_ollama_embedder else None

        # Determine embedder type if not specified
        if embedder_type is None:
            from api.config import get_embedder_type

            embedder_type = get_embedder_type()

        encoding = _get_encoding(embedder_type)
        return len(encoding.encode(text))
    except Exception as e:
        # Fallback to a simple approximation if tiktoken fails
        logger.warning(f"Error counting tokens with tiktoken: {e}")
        # Rough approximation: 4 characters per token
        return len(text) // 4


def count_tokens_batch(
    texts: List[str], embedder_type: str | None = None, num_threads: int | None = None,
) -> List[int]:
    """Count tokens for multiple texts in parallel using tiktoken batch operations.

    Args:
        texts (List[str]): List of texts to count tokens for.
        embedder_type (str, optional): The embedder type ('openai', 'google', 'ollama').
                                     If None, will be determined from configuration.
        num_threads (int, optional): Number of threads for parallel processing.
                                    If None, uses default (typically CPU count).

    Returns:
        List[int]: List of token counts corresponding to input texts.
    """
    if not texts:
        return []

    try:
        # Determine embedder type if not specified
        if embedder_type is None:
            from api.config import get_embedder_type

            embedder_type = get_embedder_type()

        encoding = _get_encoding(embedder_type)

        # Use batch encoding with threading for better performance
        if num_threads is None:
            # Default to number of CPU cores, but cap at 8 for I/O bound operations
            num_threads = min(os.cpu_count() or 4, 8)

        # Use encode_batch for parallel processing
        encoded_batch = encoding.encode_batch(texts, num_threads=num_threads)
        return [len(tokens) for tokens in encoded_batch]

    except Exception as e:
        # Fallback to sequential processing if batch fails
        logger.warning(
            f"Error in batch token counting: {e}, falling back to sequential",
        )
        return [count_tokens(text, embedder_type) for text in texts]


def _chunk_file_content(
    content: str,
    relative_path: str,
    ext: str,
    is_code: bool,
    is_implementation: bool,
    embedder_type: str,
    max_chunk_tokens: int,
) -> List[Document]:
    """Chunk a file's content into multiple documents that fit within the token limit.

    Args:
        content: The file content to chunk
        relative_path: Relative path of the file
        ext: File extension
        is_code: Whether this is a code file
        is_implementation: Whether this is an implementation file
        embedder_type: Embedder type for token counting
        max_chunk_tokens: Maximum tokens per chunk

    Returns:
        List of Document objects, one per chunk
    """
    encoding = _get_encoding(embedder_type)
    encoded_tokens = encoding.encode(content)

    chunks = []
    chunk_index = 0

    # Split into chunks of max_chunk_tokens
    for i in range(0, len(encoded_tokens), max_chunk_tokens):
        chunk_tokens = encoded_tokens[i : i + max_chunk_tokens]
        chunk_text = encoding.decode(chunk_tokens)
        chunk_token_count = len(chunk_tokens)

        # Create document for this chunk
        chunk_doc = Document(
            text=chunk_text,
            meta_data={
                "file_path": relative_path,
                "type": ext[1:],
                "is_code": is_code,
                "is_implementation": is_implementation,
                "title": f"{relative_path} (chunk {chunk_index + 1})",
                "token_count": chunk_token_count,
                "chunk_index": chunk_index,
                "is_chunked": True,
            },
        )
        chunks.append(chunk_doc)
        chunk_index += 1

    logger.info(
        f"Chunked {relative_path} into {len(chunks)} chunks "
        f"(max {max_chunk_tokens} tokens each)",
    )
    return chunks


def download_repo(
    repo_url: str, local_path: str, repo_type: str | None = None, access_token: str | None = None,
) -> str:
    """Downloads a Git repository (GitHub) to a specified local path.

    Args:
        repo_type(str): Type of repository
        repo_url (str): The URL of the Git repository to clone.
        local_path (str): The local directory where the repository will be cloned.
        access_token (str, optional): Access token for private repositories.

    Returns:
        str: The output message from the `git` command.
    """
    try:
        # Check if Git is installed
        logger.info(f"Preparing to clone repository to {local_path}")
        subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
        )

        # Check if repository already exists
        if os.path.exists(local_path) and os.listdir(local_path):
            # Directory exists and is not empty
            logger.warning(
                f"Repository already exists at {local_path}. Using existing repository.",
            )
            return f"Using existing repository at {local_path}"

        # Ensure the local path exists
        os.makedirs(local_path, exist_ok=True)

        # Build token-less clone URL (never embed token in URL for security)
        clone_url = repo_url
        logger.info(f"Cloning repository to {local_path}")

        # Prepare environment for Git with credential helper if token is provided
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"  # Disable terminal prompts

        # If access token is provided, use Git credential helper to supply credentials securely
        # This avoids embedding the token in command arguments or URLs
        if access_token:
            logger.info("Using access token for authentication via credential helper")

            # Create a Git credential helper script that provides the token securely
            # Git credential helper protocol: reads protocol, host, path from stdin
            # and outputs username=value and password=value
            import stat
            import tempfile

            # Create a temporary credential helper script
            credential_script = tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".sh",
            )
            # For GitHub HTTPS, use token as username with empty password
            # The script reads Git's credential request and outputs credentials
            credential_script.write(f"""#!/bin/sh
# Git credential helper - reads protocol, host, path and outputs credentials
read protocol
read host
read path
read
echo username={access_token}
echo password=
""")
            credential_script.close()

            # Make it executable
            os.chmod(credential_script.name, stat.S_IRUSR | stat.S_IXUSR)

            # Configure Git to use our credential helper
            # Use absolute path to avoid PATH issues and ensure security
            env["GIT_CREDENTIAL_HELPER"] = f"!{credential_script.name}"

            # Also set GIT_ASKPASS as fallback (though credential helper should handle HTTPS)
            env["GIT_ASKPASS"] = credential_script.name

            try:
                # Clone the repository with safe environment (token not in argv)
                result = subprocess.run(
                    [
                        "git",
                        "clone",
                        "--depth=1",
                        "--single-branch",
                        clone_url,
                        local_path,
                    ],
                    check=True,
                    capture_output=True,
                    env=env,
                )
            finally:
                # Clean up the temporary credential helper script
                with contextlib.suppress(OSError):
                    os.unlink(credential_script.name)
        else:
            # No token, clone normally
            result = subprocess.run(
                ["git", "clone", "--depth=1", "--single-branch", clone_url, local_path],
                check=True,
                capture_output=True,
                env=env,
            )

        logger.info("Repository cloned successfully")
        return result.stdout.decode("utf-8")

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode("utf-8")
        # Sanitize error message to remove any tokens that might have leaked
        if access_token:
            # Remove token from error message if it somehow appears
            error_msg = error_msg.replace(access_token, "***TOKEN***")
            # Also check for token-like patterns in URLs
            import re

            # Pattern to match tokens in URLs (e.g., https://token@domain)
            url_token_pattern = re.compile(r"https?://[^@]+@")
            error_msg = url_token_pattern.sub("https://***TOKEN***@", error_msg)
        raise ValueError(f"Error during cloning: {error_msg}")
    except Exception as e:
        raise ValueError(f"An unexpected error occurred: {e!s}")


# Alias for backward compatibility
download_github_repo = download_repo


def read_all_documents(
    path: str,
    embedder_type: str | None = None,
    is_ollama_embedder: bool | None = None,
    excluded_dirs: List[str] = None,
    excluded_files: List[str] = None,
    included_dirs: List[str] = None,
    included_files: List[str] = None,
):
    """Recursively reads all documents in a directory and its subdirectories.

    Args:
        path (str): The root directory path.
        embedder_type (str, optional): The embedder type ('openai', 'google', 'ollama').
                                     If None, will be determined from configuration.
        is_ollama_embedder (bool, optional): DEPRECATED. Use embedder_type instead.
                                           If None, will be determined from configuration.
        excluded_dirs (List[str], optional): List of directories to exclude from processing.
            Overrides the default configuration if provided.
        excluded_files (List[str], optional): List of file patterns to exclude from processing.
            Overrides the default configuration if provided.
        included_dirs (List[str], optional): List of directories to include exclusively.
            When provided, only files in these directories will be processed.
        included_files (List[str], optional): List of file patterns to include exclusively.
            When provided, only files matching these patterns will be processed.

    Returns:
        list: A list of Document objects with metadata.
    """
    # Handle backward compatibility
    if embedder_type is None and is_ollama_embedder is not None:
        embedder_type = "ollama" if is_ollama_embedder else None
    documents = []
    # File extensions to look for, prioritizing code files
    code_extensions = [
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".go",
        ".rs",
        ".jsx",
        ".tsx",
        ".html",
        ".css",
        ".php",
        ".swift",
        ".cs",
    ]
    doc_extensions = [".md", ".txt", ".rst", ".json", ".yaml", ".yml"]

    # Determine filtering mode: inclusion or exclusion
    use_inclusion_mode = (included_dirs is not None and len(included_dirs) > 0) or (
        included_files is not None and len(included_files) > 0
    )

    if use_inclusion_mode:
        # Inclusion mode: only process specified directories and files
        final_included_dirs = set(included_dirs) if included_dirs else set()
        final_included_files = set(included_files) if included_files else set()

        logger.info("Using inclusion mode")
        logger.info(f"Included directories: {list(final_included_dirs)}")
        logger.info(f"Included files: {list(final_included_files)}")

        # Convert to lists for processing
        included_dirs = list(final_included_dirs)
        included_files = list(final_included_files)
        excluded_dirs = []
        excluded_files = []
    else:
        # Exclusion mode: use default exclusions plus any additional ones
        final_excluded_dirs = set(DEFAULT_EXCLUDED_DIRS)
        final_excluded_files = set(DEFAULT_EXCLUDED_FILES)

        # Add any additional excluded directories from config
        if "file_filters" in configs and "excluded_dirs" in configs["file_filters"]:
            final_excluded_dirs.update(configs["file_filters"]["excluded_dirs"])

        # Add any additional excluded files from config
        if "file_filters" in configs and "excluded_files" in configs["file_filters"]:
            final_excluded_files.update(configs["file_filters"]["excluded_files"])

        # Add any explicitly provided excluded directories and files
        if excluded_dirs is not None:
            final_excluded_dirs.update(excluded_dirs)

        if excluded_files is not None:
            final_excluded_files.update(excluded_files)

        # Convert back to lists for compatibility
        excluded_dirs = list(final_excluded_dirs)
        excluded_files = list(final_excluded_files)
        included_dirs = []
        included_files = []

        logger.info("Using exclusion mode")
        logger.info(f"Excluded directories: {excluded_dirs}")
        logger.info(f"Excluded files: {excluded_files}")

    logger.info(f"Reading documents from {path}")

    def should_process_file(
        file_path: str,
        use_inclusion: bool,
        included_dirs: List[str],
        included_files: List[str],
        excluded_dirs: List[str],
        excluded_files: List[str],
    ) -> bool:
        """Determine if a file should be processed based on inclusion/exclusion rules.

        Args:
            file_path (str): The file path to check
            use_inclusion (bool): Whether to use inclusion mode
            included_dirs (List[str]): List of directories to include
            included_files (List[str]): List of files to include
            excluded_dirs (List[str]): List of directories to exclude
            excluded_files (List[str]): List of files to exclude

        Returns:
            bool: True if the file should be processed, False otherwise
        """
        file_path_parts = os.path.normpath(file_path).split(os.sep)
        file_name = os.path.basename(file_path)

        if use_inclusion:
            # Inclusion mode: file must be in included directories or match included files
            is_included = False

            # Check if file is in an included directory
            if included_dirs:
                for included in included_dirs:
                    clean_included = included.strip("./").rstrip("/")
                    if clean_included in file_path_parts:
                        is_included = True
                        break

            # Check if file matches included file patterns
            if not is_included and included_files:
                for included_file in included_files:
                    if file_name == included_file or file_name.endswith(included_file):
                        is_included = True
                        break

            # If no inclusion rules are specified for a category, allow all files from that category
            if not included_dirs and not included_files:
                is_included = True
            elif not included_dirs and included_files:
                # Only file patterns specified, allow all directories
                pass  # is_included is already set based on file patterns
            elif included_dirs and not included_files:
                # Only directory patterns specified, allow all files in included directories
                pass  # is_included is already set based on directory patterns

            return is_included
        # Exclusion mode: file must not be in excluded directories or match excluded files
        is_excluded = False

        # Check if file is in an excluded directory
        for excluded in excluded_dirs:
            clean_excluded = excluded.strip("./").rstrip("/")
            if clean_excluded in file_path_parts:
                is_excluded = True
                break

        # Check if file matches excluded file patterns
        if not is_excluded:
            for excluded_file in excluded_files:
                if file_name == excluded_file:
                    is_excluded = True
                    break

        return not is_excluded

    def read_single_file(
        file_path: str, ext: str, is_code: bool, path: str, embedder_type: str,
    ) -> List[Document] | None:
        """Read a single file and return Document object(s). May return multiple
        documents if the file needs to be chunked.

        Args:
            file_path: Full path to the file
            ext: File extension
            is_code: Whether this is a code file
            path: Base path for relative path calculation
            embedder_type: Embedder type for token counting

        Returns:
            List of Document objects (or None if file should be skipped)
            Note: Returns a list to support chunking, but typically contains one document
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
                relative_path = os.path.relpath(file_path, path)

                # Get configurable multiplier from configs, fallback to default
                multiplier = CODE_FILE_TOKEN_MULTIPLIER
                if "code_file_token_multiplier" in configs:
                    multiplier = configs["code_file_token_multiplier"]
                elif (
                    "file_filters" in configs
                    and "code_file_token_multiplier" in configs.get("file_filters", {})
                ):
                    multiplier = configs["file_filters"]["code_file_token_multiplier"]

                if is_code:
                    # Determine if this is an implementation file
                    is_implementation = (
                        not relative_path.startswith("test_")
                        and not relative_path.startswith("app_")
                        and "test" not in relative_path.lower()
                    )
                    max_tokens = MAX_EMBEDDING_TOKENS * multiplier
                else:
                    is_implementation = False
                    max_tokens = MAX_EMBEDDING_TOKENS

                # Check token count
                token_count = count_tokens(content, embedder_type)

                # If file exceeds max tokens, chunk it into embedding-sized pieces
                if token_count > max_tokens:
                    logger.info(
                        f"Chunking large file {relative_path}: Token count ({token_count}) exceeds limit ({max_tokens})",
                    )
                    return _chunk_file_content(
                        content=content,
                        relative_path=relative_path,
                        ext=ext,
                        is_code=is_code,
                        is_implementation=is_implementation,
                        embedder_type=embedder_type,
                        max_chunk_tokens=MAX_EMBEDDING_TOKENS,
                    )

                # File fits within limit, return single document
                doc = Document(
                    text=content,
                    meta_data={
                        "file_path": relative_path,
                        "type": ext[1:],
                        "is_code": is_code,
                        "is_implementation": is_implementation,
                        "title": relative_path,
                        "token_count": token_count,
                    },
                )
                return [doc]
        except Exception as e:
            logger.exception(f"Error reading {file_path}: {e}")
            return None

    # Collect all files to process using shared repository scanner
    all_files = []
    discovered_files = collect_repository_files(path)
    for file_path in discovered_files:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in code_extensions:
            is_code = True
        elif ext in doc_extensions:
            is_code = False
        else:
            continue

        if should_process_file(
            file_path,
            use_inclusion_mode,
            included_dirs,
            included_files,
            excluded_dirs,
            excluded_files,
        ):
            all_files.append((file_path, ext, is_code))

    logger.info(f"Found {len(all_files)} files to process, reading in parallel...")

    # Process files in parallel using ThreadPoolExecutor
    # Use a reasonable number of workers (I/O bound, so can use more than CPU count)
    max_workers = min(
        os.cpu_count() * 2 or 8, 16,
    )  # Cap at 16 to avoid too many open files

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all file reading tasks
        future_to_file = {
            executor.submit(
                read_single_file, file_path, ext, is_code, path, embedder_type,
            ): (file_path, ext, is_code)
            for file_path, ext, is_code in all_files
        }

        # Collect results as they complete
        for future in as_completed(future_to_file):
            file_path, ext, is_code = future_to_file[future]
            try:
                result = future.result()
                if result is not None:
                    # read_single_file now returns a list (for chunking support)
                    if isinstance(result, list):
                        documents.extend(result)
                    else:
                        # Backward compatibility: handle single Document if returned
                        documents.append(result)
            except Exception as e:
                logger.exception(f"Error processing {file_path}: {e}")

    logger.info(f"Found {len(documents)} documents")
    return documents


def prepare_data_pipeline(embedder_type: str | None = None, is_ollama_embedder: bool | None = None):
    """Creates and returns the data transformation pipeline.

    Args:
        embedder_type (str, optional): The embedder type ('openai', 'google', 'ollama').
                                     If None, will be determined from configuration.
        is_ollama_embedder (bool, optional): DEPRECATED. Use embedder_type instead.
                                           If None, will be determined from configuration.

    Returns:
        adal.Sequential: The data transformation pipeline
    """
    from api.config import get_embedder_config, get_embedder_type

    # Handle backward compatibility
    if embedder_type is None and is_ollama_embedder is not None:
        embedder_type = "ollama" if is_ollama_embedder else None

    # Determine embedder type if not specified
    if embedder_type is None:
        embedder_type = get_embedder_type()

    splitter = TextSplitter(**configs["text_splitter"])
    embedder_config = get_embedder_config()

    embedder = get_embedder(embedder_type=embedder_type)

    # Choose appropriate processor based on embedder type
    if embedder_type == "ollama":
        # Use Ollama document processor for single-document processing
        embedder_transformer = OllamaDocumentProcessor(embedder=embedder)
    else:
        # Use batch processing for OpenAI and Google embedders
        # Increase batch size for better performance (OpenAI supports up to 2048)
        batch_size = embedder_config.get("batch_size", 500)
        # Optimize batch size: OpenAI supports up to 2048, but use 2000 for safety margin
        # Google supports up to 100, so keep that limit
        if embedder_type == "openai":
            batch_size = min(batch_size, 2000) if batch_size < 2000 else batch_size
        elif embedder_type == "google":
            batch_size = min(batch_size, 100) if batch_size > 100 else batch_size

        embedder_transformer = ToEmbeddings(embedder=embedder, batch_size=batch_size)

    return adal.Sequential(
        splitter, embedder_transformer,
    )  # sequential will chain together splitter and embedder


def transform_documents_and_save_to_db(
    documents: List[Document],
    db_path: str,
    embedder_type: str | None = None,
    is_ollama_embedder: bool | None = None,
) -> LocalDB:
    """Transforms a list of documents and saves them to a local database.

    Args:
        documents (list): A list of `Document` objects.
        db_path (str): The path to the local database file.
        embedder_type (str, optional): The embedder type ('openai', 'google', 'ollama').
                                     If None, will be determined from configuration.
        is_ollama_embedder (bool, optional): DEPRECATED. Use embedder_type instead.
                                           If None, will be determined from configuration.
    """
    # Get the data transformer
    data_transformer = prepare_data_pipeline(embedder_type, is_ollama_embedder)

    # Save the documents to a local database
    db = LocalDB()
    db.register_transformer(transformer=data_transformer, key="split_and_embed")
    db.load(documents)
    db.transform(key="split_and_embed")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db.save_state(filepath=db_path)
    return db


def get_github_file_content(
    repo_url: str, file_path: str, access_token: str | None = None,
) -> str:
    """Retrieves the content of a file from a GitHub repository using the GitHub API.
    Supports both public GitHub (github.com) and GitHub Enterprise (custom domains).

    Args:
        repo_url (str): The URL of the GitHub repository
                       (e.g., "https://github.com/username/repo" or "https://github.company.com/username/repo")
        file_path (str): The path to the file within the repository (e.g., "src/main.py")
        access_token (str, optional): GitHub personal access token for private repositories

    Returns:
        str: The content of the file as a string

    Raises:
        ValueError: If the file cannot be fetched or if the URL is not a valid GitHub URL
    """
    try:
        # Parse the repository URL to support both github.com and enterprise GitHub
        parsed_url = urlparse(repo_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("Not a valid GitHub repository URL")

        # Check if it's a GitHub-like URL structure
        path_parts = parsed_url.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError(
                "Invalid GitHub URL format - expected format: https://domain/owner/repo",
            )

        owner = path_parts[-2]
        repo = path_parts[-1].replace(".git", "")

        # Determine the API base URL
        if parsed_url.netloc == "github.com":
            # Public GitHub
            api_base = "https://api.github.com"
        else:
            # GitHub Enterprise - API is typically at https://domain/api/v3/
            api_base = f"{parsed_url.scheme}://{parsed_url.netloc}/api/v3"

        # Use GitHub API to get file content
        # The API endpoint for getting file content is: /repos/{owner}/{repo}/contents/{path}
        api_url = f"{api_base}/repos/{owner}/{repo}/contents/{file_path}"

        # Fetch file content from GitHub API
        headers = {}
        if access_token:
            headers["Authorization"] = f"token {access_token}"
        logger.info(f"Fetching file content from GitHub API: {api_url}")
        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
        except RequestException as e:
            raise ValueError(f"Error fetching file content: {e}")
        try:
            content_data = response.json()
        except json.JSONDecodeError:
            raise ValueError("Invalid response from GitHub API")

        # Check if we got an error response
        if "message" in content_data and "documentation_url" in content_data:
            raise ValueError(f"GitHub API error: {content_data['message']}")

        # GitHub API returns file content as base64 encoded string
        if "content" in content_data and "encoding" in content_data:
            if content_data["encoding"] == "base64":
                # The content might be split into lines, so join them first
                content_base64 = content_data["content"].replace("\n", "")
                return base64.b64decode(content_base64).decode("utf-8")
            raise ValueError(f"Unexpected encoding: {content_data['encoding']}")
        raise ValueError("File content not found in GitHub API response")

    except Exception as e:
        raise ValueError(f"Failed to get file content: {e!s}")


def get_file_content(
    repo_url: str, file_path: str, repo_type: str | None = None, access_token: str | None = None,
) -> str:
    """Retrieves the content of a file from a GitHub repository.

    Args:
        repo_type (str): Type of repository (should be 'github')
        repo_url (str): The URL of the repository
        file_path (str): The path to the file within the repository
        access_token (str, optional): GitHub personal access token for private repositories

    Returns:
        str: The content of the file as a string

    Raises:
        ValueError: If the file cannot be fetched or if the URL is not valid
    """
    return get_github_file_content(repo_url, file_path, access_token)


class DatabaseManager:
    """Manages the creation, loading, transformation, and persistence of LocalDB instances."""

    def __init__(self) -> None:
        self.db = None
        self.repo_url_or_path = None
        self.repo_paths = None

    def prepare_database(
        self,
        repo_url_or_path: str,
        repo_type: str | None = None,
        access_token: str | None = None,
        embedder_type: str | None = None,
        is_ollama_embedder: bool | None = None,
        excluded_dirs: List[str] = None,
        excluded_files: List[str] = None,
        included_dirs: List[str] = None,
        included_files: List[str] = None,
    ) -> List[Document]:
        """Create a new database from the repository.

        Args:
            repo_type(str): Type of repository
            repo_url_or_path (str): The URL or local path of the repository
            access_token (str, optional): Access token for private repositories
            embedder_type (str, optional): Embedder type to use ('openai', 'google', 'ollama').
                                         If None, will be determined from configuration.
            is_ollama_embedder (bool, optional): DEPRECATED. Use embedder_type instead.
                                               If None, will be determined from configuration.
            excluded_dirs (List[str], optional): List of directories to exclude from processing
            excluded_files (List[str], optional): List of file patterns to exclude from processing
            included_dirs (List[str], optional): List of directories to include exclusively
            included_files (List[str], optional): List of file patterns to include exclusively

        Returns:
            List[Document]: List of Document objects
        """
        # Handle backward compatibility
        if embedder_type is None and is_ollama_embedder is not None:
            embedder_type = "ollama" if is_ollama_embedder else None

        self.reset_database()
        self._create_repo(repo_url_or_path, repo_type, access_token)
        return self.prepare_db_index(
            embedder_type=embedder_type,
            excluded_dirs=excluded_dirs,
            excluded_files=excluded_files,
            included_dirs=included_dirs,
            included_files=included_files,
        )

    def reset_database(self) -> None:
        """Reset the database to its initial state."""
        self.db = None
        self.repo_url_or_path = None
        self.repo_paths = None

    def _extract_repo_name_from_url(self, repo_url_or_path: str, repo_type: str) -> str:
        # Extract owner and repo name to create unique identifier
        url_parts = repo_url_or_path.rstrip("/").split("/")

        if repo_type == "github" and len(url_parts) >= 5:
            # GitHub URL format: https://github.com/owner/repo
            owner = url_parts[-2]
            repo = url_parts[-1].replace(".git", "")
            repo_name = f"{owner}_{repo}"
        else:
            repo_name = url_parts[-1].replace(".git", "")
        return repo_name

    def _create_repo(
        self, repo_url_or_path: str, repo_type: str | None = None, access_token: str | None = None,
    ) -> None:
        """Download and prepare all paths.
        Paths:
        ~/.adalflow/repos/{owner}_{repo_name} (for url, local path will be the same)
        ~/.adalflow/databases/{owner}_{repo_name}.pkl.

        Args:
            repo_type(str): Type of repository
            repo_url_or_path (str): The URL or local path of the repository
            access_token (str, optional): Access token for private repositories
        """
        logger.info(f"Preparing repo storage for {repo_url_or_path}...")

        try:
            root_path = get_adalflow_default_root_path()

            os.makedirs(root_path, exist_ok=True)
            # url
            if repo_url_or_path.startswith(("https://", "http://")):
                # Extract the repository name from the URL
                repo_name = self._extract_repo_name_from_url(
                    repo_url_or_path, repo_type,
                )
                logger.info(f"Extracted repo name: {repo_name}")

                save_repo_dir = os.path.join(root_path, "repos", repo_name)

                # Check if the repository directory already exists and is not empty
                if not (os.path.exists(save_repo_dir) and os.listdir(save_repo_dir)):
                    # Only download if the repository doesn't exist or is empty
                    download_repo(
                        repo_url_or_path, save_repo_dir, repo_type, access_token,
                    )
                else:
                    logger.info(
                        f"Repository already exists at {save_repo_dir}. Using existing repository.",
                    )
            else:  # local path
                repo_name = os.path.basename(repo_url_or_path)
                save_repo_dir = repo_url_or_path

            save_db_file = os.path.join(root_path, "databases", f"{repo_name}.pkl")
            os.makedirs(save_repo_dir, exist_ok=True)
            os.makedirs(os.path.dirname(save_db_file), exist_ok=True)

            self.repo_paths = {
                "save_repo_dir": save_repo_dir,
                "save_db_file": save_db_file,
            }
            self.repo_url_or_path = repo_url_or_path
            logger.info(f"Repo paths: {self.repo_paths}")

        except Exception as e:
            logger.exception(f"Failed to create repository structure: {e}")
            raise

    def prepare_db_index(
        self,
        embedder_type: str | None = None,
        is_ollama_embedder: bool | None = None,
        excluded_dirs: List[str] = None,
        excluded_files: List[str] = None,
        included_dirs: List[str] = None,
        included_files: List[str] = None,
    ) -> List[Document]:
        """Prepare the indexed database for the repository.
        Uses incremental updates when possible to speed up subsequent runs.

        Args:
            embedder_type (str, optional): Embedder type to use ('openai', 'google', 'ollama').
                                         If None, will be determined from configuration.
            is_ollama_embedder (bool, optional): DEPRECATED. Use embedder_type instead.
                                               If None, will be determined from configuration.
            excluded_dirs (List[str], optional): List of directories to exclude from processing
            excluded_files (List[str], optional): List of file patterns to exclude from processing
            included_dirs (List[str], optional): List of directories to include exclusively
            included_files (List[str], optional): List of file patterns to include exclusively

        Returns:
            List[Document]: List of Document objects
        """
        # Handle backward compatibility
        if embedder_type is None and is_ollama_embedder is not None:
            embedder_type = "ollama" if is_ollama_embedder else None

        # Check the database
        if self.repo_paths and os.path.exists(self.repo_paths["save_db_file"]):
            logger.info("Loading existing database...")
            try:
                self.db = LocalDB.load_state(self.repo_paths["save_db_file"])
                existing_documents = self.db.get_transformed_data(key="split_and_embed")
                if existing_documents:
                    logger.info(
                        f"Loaded {len(existing_documents)} documents from existing database",
                    )

                    # Try incremental update: check file modification times
                    try:
                        # Build a map of existing documents by file path
                        existing_by_path = {}
                        for doc in existing_documents:
                            file_path = doc.meta_data.get("file_path")
                            if file_path:
                                existing_by_path[file_path] = doc

                        # Read all current documents
                        current_documents = read_all_documents(
                            self.repo_paths["save_repo_dir"],
                            embedder_type=embedder_type,
                            excluded_dirs=excluded_dirs,
                            excluded_files=excluded_files,
                            included_dirs=included_dirs,
                            included_files=included_files,
                        )

                        # Check which files have changed
                        changed_files = []
                        new_files = []
                        unchanged_files = []

                        for doc in current_documents:
                            file_path = doc.meta_data.get("file_path")
                            if not file_path:
                                new_files.append(doc)
                                continue

                            full_path = os.path.join(
                                self.repo_paths["save_repo_dir"], file_path,
                            )

                            if file_path in existing_by_path:
                                # Check if file has been modified
                                existing_doc = existing_by_path[file_path]
                                existing_mtime = existing_doc.meta_data.get(
                                    "file_mtime",
                                )

                                try:
                                    current_mtime = os.path.getmtime(full_path)
                                    if (
                                        existing_mtime is None
                                        or abs(current_mtime - existing_mtime) > 1.0
                                    ):
                                        # File has changed (1 second tolerance for filesystem precision)
                                        changed_files.append(doc)
                                        doc.meta_data["file_mtime"] = current_mtime
                                    else:
                                        # File unchanged, reuse existing document
                                        unchanged_files.append(existing_doc)
                                        doc.meta_data["file_mtime"] = current_mtime
                                except OSError:
                                    # File might have been deleted or moved, treat as changed
                                    changed_files.append(doc)
                            else:
                                # New file
                                try:
                                    full_path = os.path.join(
                                        self.repo_paths["save_repo_dir"], file_path,
                                    )
                                    doc.meta_data["file_mtime"] = os.path.getmtime(
                                        full_path,
                                    )
                                except OSError:
                                    pass
                                new_files.append(doc)

                        # If there are changes, do incremental update
                        if changed_files or new_files:
                            logger.info(
                                f"Incremental update: {len(changed_files)} changed, "
                                f"{len(new_files)} new, {len(unchanged_files)} unchanged files",
                            )

                            # Only process changed and new files
                            files_to_process = changed_files + new_files

                            if files_to_process:
                                # Transform only changed/new documents
                                data_transformer = prepare_data_pipeline(
                                    embedder_type, is_ollama_embedder,
                                )
                                temp_db = LocalDB()
                                temp_db.register_transformer(
                                    transformer=data_transformer, key="split_and_embed",
                                )
                                temp_db.load(files_to_process)
                                temp_db.transform(key="split_and_embed")

                                # Get transformed documents
                                transformed_new = temp_db.get_transformed_data(
                                    key="split_and_embed",
                                )

                                # Combine unchanged and new/updated documents
                                # Note: Both unchanged_files and transformed_new are already transformed,
                                # so we should not call transform() again to avoid double-embedding
                                all_documents = unchanged_files + transformed_new

                                # Rebuild database with all documents
                                # Since all documents are already transformed, we load them directly
                                # without calling transform() again
                                self.db = LocalDB()
                                self.db.register_transformer(
                                    transformer=data_transformer, key="split_and_embed",
                                )
                                # Load already-transformed documents without re-transforming
                                # We use load() to add them to the database, but skip transform()
                                # since they're already transformed
                                self.db.load(all_documents)
                                # Skip transform() - documents are already transformed
                                # This prevents double-embedding of unchanged_files
                                self.db.save_state(
                                    filepath=self.repo_paths["save_db_file"],
                                )

                                logger.info(
                                    f"Incremental update complete: {len(all_documents)} total documents "
                                    f"({len(unchanged_files)} reused, {len(transformed_new)} processed)",
                                )

                                return self.db.get_transformed_data(
                                    key="split_and_embed",
                                )
                            # No changes, return existing documents
                            return existing_documents
                        logger.info(
                            "No file changes detected, using cached database",
                        )
                        return existing_documents

                    except Exception as e:
                        logger.warning(
                            f"Incremental update failed: {e}, falling back to full rebuild",
                        )
                        # Fall through to full rebuild

                    # If incremental update didn't work, return existing documents
                    return existing_documents
            except Exception as e:
                logger.exception(f"Error loading existing database: {e}")
                # Continue to create a new database

        # prepare the database (full rebuild)
        logger.info("Creating new database...")
        documents = read_all_documents(
            self.repo_paths["save_repo_dir"],
            embedder_type=embedder_type,
            excluded_dirs=excluded_dirs,
            excluded_files=excluded_files,
            included_dirs=included_dirs,
            included_files=included_files,
        )

        # Add file modification times to metadata for future incremental updates
        for doc in documents:
            file_path = doc.meta_data.get("file_path")
            if file_path:
                try:
                    full_path = os.path.join(
                        self.repo_paths["save_repo_dir"], file_path,
                    )
                    doc.meta_data["file_mtime"] = os.path.getmtime(full_path)
                except OSError:
                    pass

        self.db = transform_documents_and_save_to_db(
            documents, self.repo_paths["save_db_file"], embedder_type=embedder_type,
        )
        logger.info(f"Total documents: {len(documents)}")
        transformed_docs = self.db.get_transformed_data(key="split_and_embed")
        logger.info(f"Total transformed documents: {len(transformed_docs)}")
        return transformed_docs

    def prepare_retriever(
        self, repo_url_or_path: str, repo_type: str | None = None, access_token: str | None = None,
    ):
        """Prepare the retriever for a repository.
        This is a compatibility method for the isolated API.

        Args:
            repo_type(str): Type of repository
            repo_url_or_path (str): The URL or local path of the repository
            access_token (str, optional): Access token for private repositories

        Returns:
            List[Document]: List of Document objects
        """
        return self.prepare_database(repo_url_or_path, repo_type, access_token)

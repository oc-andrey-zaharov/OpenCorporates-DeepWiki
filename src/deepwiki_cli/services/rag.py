import weakref
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import uuid4

import adalflow as adal
import structlog

from deepwiki_cli.infrastructure.embedding.embedder import get_embedder
from deepwiki_cli.infrastructure.prompts.builders import (
    RAG_SYSTEM_PROMPT,
    RAG_TEMPLATE,
)


# Create our own implementation of the conversation classes
@dataclass
class UserQuery:
    query_str: str


@dataclass
class AssistantResponse:
    response_str: str


@dataclass
class DialogTurn:
    id: str
    user_query: UserQuery
    assistant_response: AssistantResponse


class CustomConversation:
    """Custom implementation of Conversation to fix the list assignment index out of range error."""

    def __init__(self) -> None:
        self.dialog_turns: list[Any] = []

    def append_dialog_turn(self, dialog_turn: Any) -> None:
        """Safely append a dialog turn to the conversation."""
        if not hasattr(self, "dialog_turns"):
            self.dialog_turns = []
        self.dialog_turns.append(dialog_turn)


# Import other adalflow components
from adalflow.components.retriever.faiss_retriever import FAISSRetriever

from deepwiki_cli.infrastructure.config import configs
from deepwiki_cli.services.data_pipeline import DatabaseManager, count_tokens

logger = structlog.get_logger()

# Maximum token limit for embedding models
MAX_INPUT_TOKENS = 7500  # Safe threshold below 8192 token limit


class Memory(adal.core.component.DataComponent):
    """Simple conversation management with a list of dialog turns."""

    def __init__(self) -> None:
        super().__init__()
        # Use our custom implementation instead of the original Conversation class
        self.current_conversation = CustomConversation()

    def call(self) -> dict:
        """Return the conversation history as a dictionary."""
        all_dialog_turns = {}
        try:
            # Check if dialog_turns exists and is a list
            if hasattr(self.current_conversation, "dialog_turns"):
                if self.current_conversation.dialog_turns:
                    logger.info(
                        f"Memory content: {len(self.current_conversation.dialog_turns)} turns",
                    )
                    for i, turn in enumerate(self.current_conversation.dialog_turns):
                        if hasattr(turn, "id") and turn.id is not None:
                            all_dialog_turns[turn.id] = turn
                            logger.info(
                                f"Added turn {i + 1} with ID {turn.id} to memory",
                            )
                        else:
                            logger.warning(
                                f"Skipping invalid turn object in memory: {turn}",
                            )
                else:
                    logger.info("Dialog turns list exists but is empty")
            else:
                logger.info("No dialog_turns attribute in current_conversation")
                # Try to initialize it
                self.current_conversation.dialog_turns = []
        except Exception as e:
            logger.exception(f"Error accessing dialog turns: {e!s}")
            # Try to recover
            try:
                self.current_conversation = CustomConversation()
                logger.info("Recovered by creating new conversation")
            except Exception as e2:
                logger.exception(f"Failed to recover: {e2!s}")

        logger.info(f"Returning {len(all_dialog_turns)} dialog turns from memory")
        return all_dialog_turns

    def add_dialog_turn(self, user_query: str, assistant_response: str) -> bool:
        """Add a dialog turn to the conversation history.

        Args:
            user_query: The user's query
            assistant_response: The assistant's response

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create a new dialog turn using our custom implementation
            dialog_turn = DialogTurn(
                id=str(uuid4()),
                user_query=UserQuery(query_str=user_query),
                assistant_response=AssistantResponse(response_str=assistant_response),
            )

            # Make sure the current_conversation has the append_dialog_turn method
            if not hasattr(self.current_conversation, "append_dialog_turn"):
                logger.warning(
                    "current_conversation does not have append_dialog_turn method, creating new one",
                )
                # Initialize a new conversation if needed
                self.current_conversation = CustomConversation()

            # Ensure dialog_turns exists
            if not hasattr(self.current_conversation, "dialog_turns"):
                logger.warning("dialog_turns not found, initializing empty list")
                self.current_conversation.dialog_turns = []

            # Safely append the dialog turn
            self.current_conversation.dialog_turns.append(dialog_turn)
            logger.info(
                f"Successfully added dialog turn, now have {len(self.current_conversation.dialog_turns)} turns",
            )
            return True

        except Exception as e:
            logger.exception(f"Error adding dialog turn: {e!s}")
            # Try to recover by creating a new conversation
            try:
                self.current_conversation = CustomConversation()
                dialog_turn = DialogTurn(
                    id=str(uuid4()),
                    user_query=UserQuery(query_str=user_query),
                    assistant_response=AssistantResponse(
                        response_str=assistant_response,
                    ),
                )
                self.current_conversation.dialog_turns.append(dialog_turn)
                logger.info("Recovered from error by creating new conversation")
                return True
            except Exception as e2:
                logger.exception(f"Failed to recover from error: {e2!s}")
                return False


from dataclasses import dataclass, field


@dataclass
class RAGAnswer(adal.DataClass):
    rationale: str = field(
        default="",
        metadata={"desc": "Chain of thoughts for the answer."},
    )
    answer: str = field(
        default="",
        metadata={
            "desc": "Answer to the user query, formatted in markdown for beautiful rendering with react-markdown. DO NOT include ``` triple backticks fences at the beginning or end of your answer.",
        },
    )

    __output_fields__: ClassVar[list[str]] = ["rationale", "answer"]


class RAG(adal.Component):
    """RAG with one repo.
    If you want to load a new repos, call prepare_retriever(repo_url_or_path) first.
    """

    def __init__(
        self,
        provider: str = "google",
        model: str | None = None,
        use_s3: bool = False,
    ) -> None:
        """Initialize the RAG component.

        Args:
            provider: Model provider to use (google, openai, openrouter, ollama)
            model: Model name to use with the provider
            use_s3: Whether to use S3 for database storage (default: False)
        """
        super().__init__()

        self.provider = provider
        self.model = model

        # Import the helper functions
        from deepwiki_cli.config import get_embedder_config, get_embedder_type

        # Determine embedder type based on current configuration
        self.embedder_type = get_embedder_type()
        self.is_ollama_embedder = (
            self.embedder_type == "ollama"
        )  # Backward compatibility

        # Check if Ollama model exists before proceeding
        if self.is_ollama_embedder:
            from deepwiki_cli.ollama_patch import check_ollama_model_exists

            embedder_config = get_embedder_config()
            if embedder_config and embedder_config.get("model_kwargs", {}).get("model"):
                model_name = embedder_config["model_kwargs"]["model"]
                if not check_ollama_model_exists(model_name):
                    raise Exception(
                        f"Ollama model '{model_name}' not found. Please run 'ollama pull {model_name}' to install it.",
                    )

        # Initialize components
        self.memory = Memory()
        self.embedder = get_embedder(embedder_type=self.embedder_type)

        self_weakref = weakref.ref(self)

        # Patch: ensure query embedding is always single string for Ollama
        def single_string_embedder(query: str | list[str]) -> Any:
            # Accepts either a string or a list, always returns embedding for a single string
            if isinstance(query, list):
                if len(query) != 1:
                    raise ValueError("Ollama embedder only supports a single string")
                query = query[0]
            instance = self_weakref()
            if instance is None:
                raise RuntimeError(
                    "RAG instance is no longer available, but the query embedder was called.",
                )
            return instance.embedder(input=query)

        # Use single string embedder for Ollama, regular embedder for others
        self.query_embedder = (
            single_string_embedder if self.is_ollama_embedder else self.embedder
        )

        self.initialize_db_manager()

        # Set up the output parser
        data_parser = adal.DataClassParser(data_class=RAGAnswer, return_data_class=True)

        # Format instructions to ensure proper output structure
        format_instructions = (
            data_parser.get_output_format_str()
            + """

IMPORTANT FORMATTING RULES:
1. DO NOT include your thinking or reasoning process in the output
2. Provide only the final, polished answer
3. DO NOT include ```markdown fences at the beginning or end of your answer
4. DO NOT wrap your response in any kind of fences
5. Start your response directly with the content
6. The content will already be rendered as markdown
7. Do not use backslashes before special characters like [ ] { } in your answer
8. When listing tags or similar items, write them as plain text without escape characters
9. For pipe characters (|) in text, write them directly without escaping them"""
        )

        # Get model configuration based on provider and model
        from deepwiki_cli.config import get_model_config

        generator_config = get_model_config(self.provider, self.model)

        # Set up the main generator
        self.generator = adal.Generator(
            template=RAG_TEMPLATE,
            prompt_kwargs={
                "output_format_str": format_instructions,
                "conversation_history": self.memory(),
                "system_prompt": RAG_SYSTEM_PROMPT,
                "contexts": None,
            },
            model_client=generator_config["model_client"](),
            model_kwargs=generator_config["model_kwargs"],
            output_processors=data_parser,
        )

    def initialize_db_manager(self) -> None:
        """Initialize the database manager with local storage."""
        self.db_manager = DatabaseManager()
        self.transformed_docs: list[Any] = []

    def _validate_and_filter_embeddings(self, documents: list) -> list:
        """Validate embeddings and filter out documents with invalid or mismatched embedding sizes.

        Ensures all embeddings have consistent dimensions by finding the most common
        embedding size and filtering out documents with different sizes.

        Args:
            documents: List of documents with embeddings to validate.

        Returns:
            List of documents with valid embeddings of consistent size. Returns empty
            list if no valid embeddings are found.

        Example:
            >>> rag = RAG()
            >>> docs = [doc1, doc2, doc3]  # Documents with embeddings
            >>> valid_docs = rag._validate_and_filter_embeddings(docs)
            >>> len(valid_docs) <= len(docs)
            True
        """
        if not documents:
            logger.warning("No documents provided for embedding validation")
            return []

        valid_documents: list[Any] = []
        embedding_sizes: dict[int, int] = {}

        # First pass: collect all embedding sizes and count occurrences
        for i, doc in enumerate(documents):
            if not hasattr(doc, "vector") or doc.vector is None:
                logger.warning(f"Document {i} has no embedding vector, skipping")
                continue

            try:
                if isinstance(doc.vector, list):
                    embedding_size = len(doc.vector)
                elif hasattr(doc.vector, "shape"):
                    embedding_size = (
                        doc.vector.shape[0]
                        if len(doc.vector.shape) == 1
                        else doc.vector.shape[-1]
                    )
                elif hasattr(doc.vector, "__len__"):
                    embedding_size = len(doc.vector)
                else:
                    logger.warning(
                        f"Document {i} has invalid embedding vector type: {type(doc.vector)}, skipping",
                    )
                    continue

                if embedding_size == 0:
                    logger.warning(f"Document {i} has empty embedding vector, skipping")
                    continue

                embedding_sizes[embedding_size] = (
                    embedding_sizes.get(embedding_size, 0) + 1
                )

            except Exception as e:
                logger.warning(
                    f"Error checking embedding size for document {i}: {e!s}, skipping",
                )
                continue

        if not embedding_sizes:
            logger.error("No valid embeddings found in any documents")
            return []

        # Find the most common embedding size (this should be the correct one)
        target_size = max(embedding_sizes.keys(), key=lambda k: embedding_sizes[k])
        logger.info(
            f"Target embedding size: {target_size} (found in {embedding_sizes[target_size]} documents)",
        )

        # Log all embedding sizes found
        for size, count in embedding_sizes.items():
            if size != target_size:
                logger.warning(
                    f"Found {count} documents with incorrect embedding size {size}, will be filtered out",
                )

        # Second pass: filter documents with the target embedding size
        # Keep vectors as Python lists (FAISSRetriever will handle conversion internally)
        for i, doc in enumerate(documents):
            if not hasattr(doc, "vector") or doc.vector is None:
                continue

            try:
                # Get embedding size (works for lists, numpy arrays, or any sequence)
                if isinstance(doc.vector, list):
                    embedding_size = len(doc.vector)
                elif hasattr(doc.vector, "shape"):
                    # Handle numpy arrays or array-like objects
                    embedding_size = (
                        doc.vector.shape[0]
                        if len(doc.vector.shape) == 1
                        else doc.vector.shape[-1]
                    )
                    # Convert numpy array to list for consistency
                    if hasattr(doc.vector, "tolist"):
                        doc.vector = doc.vector.tolist()
                elif hasattr(doc.vector, "__len__"):
                    embedding_size = len(doc.vector)
                    # Convert to list if possible
                    if hasattr(doc.vector, "tolist"):
                        doc.vector = doc.vector.tolist()
                    elif not isinstance(doc.vector, list):
                        doc.vector = list(doc.vector)
                else:
                    continue

                if embedding_size == target_size:
                    valid_documents.append(doc)
                else:
                    # Log which document is being filtered out
                    file_path = getattr(doc, "meta_data", {}).get(
                        "file_path",
                        f"document_{i}",
                    )
                    logger.warning(
                        f"Filtering out document '{file_path}' due to embedding size mismatch: {embedding_size} != {target_size}",
                    )

            except Exception as e:
                file_path = getattr(doc, "meta_data", {}).get(
                    "file_path",
                    f"document_{i}",
                )
                logger.warning(
                    f"Error validating embedding for document '{file_path}': {e!s}, skipping",
                )
                continue

        logger.info(
            f"Embedding validation complete: {len(valid_documents)}/{len(documents)} documents have valid embeddings",
        )

        if len(valid_documents) == 0:
            logger.error("No documents with valid embeddings remain after filtering")
        elif len(valid_documents) < len(documents):
            filtered_count = len(documents) - len(valid_documents)
            logger.warning(
                f"Filtered out {filtered_count} documents due to embedding issues",
            )

        return valid_documents

    def _truncate_query_by_tokens(self, query: str, max_tokens: int) -> str:
        """Truncate a query string to fit within the maximum token limit.

        Uses binary search to efficiently find the truncation point that results
        in exactly max_tokens or fewer tokens. Logs a warning if truncation occurs.

        Args:
            query: The query string to truncate.
            max_tokens: Maximum number of tokens allowed.

        Returns:
            Truncated query string that fits within the token limit. Returns original
            query if it's already within the limit.

        Example:
            >>> rag = RAG()
            >>> long_query = "a" * 10000
            >>> truncated = rag._truncate_query_by_tokens(long_query, 100)
            >>> len(truncated) <= len(long_query)
            True
        """
        if not query:
            return query

        # Count tokens in the original query
        token_count = count_tokens(query, embedder_type=self.embedder_type)

        # If within limit, return as-is
        if token_count <= max_tokens:
            return query

        # Binary search for the truncation point
        # Start with the full query length
        left, right = 0, len(query)
        best_truncated = query

        while left < right:
            mid = (left + right) // 2
            truncated = query[:mid]

            if not truncated:
                left = mid + 1
                continue

            current_tokens = count_tokens(truncated, embedder_type=self.embedder_type)

            if current_tokens <= max_tokens:
                best_truncated = truncated
                left = mid + 1
            else:
                right = mid

        # Final check: ensure we didn't exceed the limit
        final_tokens = count_tokens(best_truncated, embedder_type=self.embedder_type)
        if final_tokens > max_tokens:
            # If still over limit, reduce character by character from the end
            while (
                best_truncated
                and count_tokens(best_truncated, embedder_type=self.embedder_type)
                > max_tokens
            ):
                best_truncated = best_truncated[:-1]

        logger.warning(
            f"Query truncated from {token_count} tokens to "
            f"{count_tokens(best_truncated, embedder_type=self.embedder_type)} tokens "
            f"(limit: {max_tokens} tokens)",
        )

        return best_truncated

    def prepare_retriever(
        self,
        repo_url_or_path: str,
        type: str = "github",
        access_token: str | None = None,
        excluded_dirs: list[str] | None = None,
        excluded_files: list[str] | None = None,
        included_dirs: list[str] | None = None,
        included_files: list[str] | None = None,
    ) -> None:
        """Prepare the retriever for a repository.
        Will load database from local storage if available.

        Args:
            repo_url_or_path: URL or local path to the repository
            type: Type of repository ('github' or 'local')
            access_token: Optional access token for private repositories (if not provided, uses GITHUB_TOKEN from env)
            excluded_dirs: Optional list of directories to exclude from processing
            excluded_files: Optional list of file patterns to exclude from processing
            included_dirs: Optional list of directories to include exclusively
            included_files: Optional list of file patterns to include exclusively
        """
        from deepwiki_cli.config import GITHUB_TOKEN

        # Use provided token or fall back to GITHUB_TOKEN from env
        token_to_use = access_token or GITHUB_TOKEN

        self.initialize_db_manager()
        self.repo_url_or_path = repo_url_or_path
        self.transformed_docs = self.db_manager.prepare_database(
            repo_url_or_path,
            type,
            token_to_use,
            embedder_type=self.embedder_type,
            excluded_dirs=excluded_dirs,
            excluded_files=excluded_files,
            included_dirs=included_dirs,
            included_files=included_files,
        )
        logger.info(f"Loaded {len(self.transformed_docs)} documents for retrieval")

        # Validate and filter embeddings to ensure consistent sizes
        self.transformed_docs = self._validate_and_filter_embeddings(
            self.transformed_docs,
        )

        if not self.transformed_docs:
            raise ValueError(
                "No valid documents with embeddings found. Cannot create retriever.",
            )

        logger.info(
            f"Using {len(self.transformed_docs)} documents with valid embeddings for retrieval",
        )

        # Use the appropriate embedder for retrieval
        retrieve_embedder = (
            self.query_embedder if self.is_ollama_embedder else self.embedder
        )

        # Filter out documents with invalid vectors and ensure vectors are Python lists
        # FAISSRetriever expects Python lists, not numpy arrays
        valid_docs: list[Any] = []
        embedding_dim = None

        for doc in self.transformed_docs:
            if not hasattr(doc, "vector") or doc.vector is None:
                file_path = getattr(doc, "meta_data", {}).get(
                    "file_path",
                    "unknown",
                )
                logger.warning(
                    f"Document '{file_path}' has no vector attribute, skipping",
                )
                continue

            try:
                # Convert to Python list if needed
                if isinstance(doc.vector, list):
                    vector_list = doc.vector
                elif hasattr(doc.vector, "tolist"):
                    # Convert numpy array to list
                    vector_list = doc.vector.tolist()
                elif hasattr(doc.vector, "__len__"):
                    # Convert other sequence types to list
                    vector_list = list(doc.vector)
                else:
                    file_path = getattr(doc, "meta_data", {}).get(
                        "file_path",
                        "unknown",
                    )
                    logger.warning(
                        f"Document '{file_path}' has invalid vector type {type(doc.vector).__name__}, skipping",  # type: ignore[operator]
                    )
                    continue

                # Check for empty vectors
                if len(vector_list) == 0:
                    file_path = getattr(doc, "meta_data", {}).get(
                        "file_path",
                        "unknown",
                    )
                    logger.warning(
                        f"Document '{file_path}' has empty vector, skipping",
                    )
                    continue

                # Get embedding dimension from first valid vector
                if embedding_dim is None:
                    embedding_dim = len(vector_list)

                # Verify dimension consistency
                if len(vector_list) != embedding_dim:
                    file_path = getattr(doc, "meta_data", {}).get(
                        "file_path",
                        "unknown",
                    )
                    logger.warning(
                        f"Document '{file_path}' has dimension {len(vector_list)} != {embedding_dim}, skipping",
                    )
                    continue

                # Update document vector to Python list
                doc.vector = vector_list
                valid_docs.append(doc)

            except Exception as e:
                file_path = getattr(doc, "meta_data", {}).get(
                    "file_path",
                    "unknown",
                )
                logger.warning(
                    f"Error processing vector for {file_path}: {e}, skipping document",
                )
                continue

        # Update transformed_docs to only include valid documents
        if len(valid_docs) < len(self.transformed_docs):
            logger.info(
                f"Filtered {len(self.transformed_docs) - len(valid_docs)} documents with invalid vectors",
            )
        self.transformed_docs = valid_docs

        if not self.transformed_docs:

            def _raise_value_error() -> None:
                raise ValueError(
                    "No valid documents with vectors found. Cannot create retriever.",
                )

            _raise_value_error()

        logger.info(
            f"Verified {len(self.transformed_docs)} documents with Python list vectors (dim={embedding_dim})",
        )

        num_docs = len(self.transformed_docs)

        retriever_config = configs["retriever"].copy()

        # Log retriever config for debugging
        logger.info(f"Retriever config: {retriever_config}")
        logger.info(
            f"Creating FAISS retriever with {num_docs} documents (dim={embedding_dim})",
        )

        # Extract vectors from documents for FAISSRetriever
        # Vectors are already Python lists from the validation step above
        # Reference: adalflow docs show documents_embeddings = [x.embedding for x in output.data]
        document_vectors = [doc.vector for doc in self.transformed_docs]

        logger.info(
            f"Prepared {len(document_vectors)} vectors as Python lists for FAISS indexing",
        )

        # Create FAISSRetriever with list of lists (Python format)
        # FAISSRetriever will handle internal conversion to numpy arrays for FAISS operations
        self.retriever = FAISSRetriever(
            **retriever_config,
            embedder=retrieve_embedder,
            documents=document_vectors,
        )
        logger.info("FAISS retriever created successfully")

    def call(self, query: str) -> list:
        """Process a query using RAG.

        Retrieves relevant documents and processes the query using the configured
        generator model. Validates and truncates query if it exceeds token limits.

        Args:
            query: The user's query string.

        Returns:
            List containing retrieved documents. Returns empty list on error.

        Raises:
            No exceptions are raised; errors are logged and empty list is returned.

        Example:
            >>> rag = RAG(provider="google", model="gemini-pro")
            >>> rag.prepare_retriever("https://github.com/user/repo")
            >>> results = rag.call("What is the main purpose of this project?")
            >>> len(results) >= 0
            True
        """
        try:
            # Validate and truncate query if it exceeds token limit
            original_query = query
            query = self._truncate_query_by_tokens(query, MAX_INPUT_TOKENS)

            if query != original_query:
                logger.info(
                    "Query truncated due to token limit",
                    operation="rag_call",
                    status="warning",
                    max_tokens=MAX_INPUT_TOKENS,
                    original_length=len(original_query),
                    truncated_length=len(query),
                )

            retrieved_documents = self.retriever(query)

            # Fill in the documents
            retrieved_documents[0].documents = [
                self.transformed_docs[doc_index]
                for doc_index in retrieved_documents[0].doc_indices
            ]

            from typing import cast

            return cast("list[Any]", retrieved_documents)

        except Exception as e:
            logger.exception(
                "Error in RAG call",
                operation="rag_call",
                status="error",
                query=query,
                error=str(e),
            )
            return []

"""Shared test fixtures for the API test suite."""

import os
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from fastapi.testclient import TestClient
from numpy.typing import NDArray

# Set test environment variables before imports
os.environ.setdefault("UPSTAGE_API_KEY", "test-api-key")


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Ensure test environment variables are set for all tests."""
    os.environ.setdefault("UPSTAGE_API_KEY", "test-api-key")
    yield


@pytest.fixture
def seed_fixtures_path() -> Path:
    """Return path to seed fixtures directory."""
    return Path(__file__).parent.parent.parent.parent / "fixtures" / "seed"


@pytest.fixture
def temp_index_path(tmp_path: Path) -> Generator[Path, None, None]:
    """Create isolated temporary directory for index testing."""
    index_dir = tmp_path / "test_index"
    index_dir.mkdir(parents=True, exist_ok=True)
    yield index_dir
    # Cleanup handled by pytest tmp_path


@pytest.fixture
def mock_embedding_service() -> MagicMock:
    """
    Create mock embedding service with deterministic 4096-dim embeddings.

    Uses a seeded random generator for reproducible results.
    """
    mock = MagicMock()

    def generate_embedding(text: str) -> NDArray[np.float32]:
        """Generate deterministic embedding based on text hash."""
        seed = hash(text) % (2**32)
        local_rng = np.random.default_rng(seed)
        embedding = local_rng.random(4096).astype(np.float32)
        return embedding / np.linalg.norm(embedding)

    async def embed_query(text: str) -> NDArray[np.float32]:
        return generate_embedding(text)

    async def embed_documents(texts: list[str]) -> list[NDArray[np.float32]]:
        return [generate_embedding(t) for t in texts]

    mock.embed_query = AsyncMock(side_effect=embed_query)
    mock.embed_documents = AsyncMock(side_effect=embed_documents)

    return mock


@pytest.fixture
def isolated_index_service(
    temp_index_path: Path,
    mock_embedding_service: MagicMock,
) -> Generator:
    """
    Create empty IndexService for unit tests.

    Uses temp directory and mocked embedding service.
    """
    original_env = os.environ.get("VECTOR_STORE_PATH")
    original_seed = os.environ.get("SEED_INDEX_PATH")

    os.environ["VECTOR_STORE_PATH"] = str(temp_index_path)
    os.environ["SEED_INDEX_PATH"] = str(temp_index_path / "nonexistent_seed")

    from src.services.index import IndexService

    service = IndexService(embedding_service=mock_embedding_service)

    yield service

    # Restore environment
    if original_env is not None:
        os.environ["VECTOR_STORE_PATH"] = original_env
    else:
        os.environ.pop("VECTOR_STORE_PATH", None)

    if original_seed is not None:
        os.environ["SEED_INDEX_PATH"] = original_seed
    else:
        os.environ.pop("SEED_INDEX_PATH", None)


@pytest.fixture
def seed_index_service(
    seed_fixtures_path: Path,
    temp_index_path: Path,
    mock_embedding_service: MagicMock,
) -> Generator:
    """
    Create IndexService pre-loaded with seed fixtures.

    Copies seed data to temp directory for isolation.
    """
    original_env = os.environ.get("VECTOR_STORE_PATH")
    original_seed = os.environ.get("SEED_INDEX_PATH")

    # Copy seed fixtures to temp directory (ChromaDB structure)
    if seed_fixtures_path.exists():
        for item in seed_fixtures_path.iterdir():
            if item.is_file():
                shutil.copy(item, temp_index_path / item.name)
            elif item.is_dir() and item.name != "pdfs":
                target_dir = temp_index_path / item.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

    os.environ["VECTOR_STORE_PATH"] = str(temp_index_path)
    os.environ["SEED_INDEX_PATH"] = str(seed_fixtures_path)

    from src.services.index import IndexService

    service = IndexService(embedding_service=mock_embedding_service)

    yield service

    # Restore environment
    if original_env is not None:
        os.environ["VECTOR_STORE_PATH"] = original_env
    else:
        os.environ.pop("VECTOR_STORE_PATH", None)

    if original_seed is not None:
        os.environ["SEED_INDEX_PATH"] = original_seed
    else:
        os.environ.pop("SEED_INDEX_PATH", None)


@pytest.fixture
def client_with_seed(
    seed_fixtures_path: Path,
    temp_index_path: Path,
    mock_embedding_service: MagicMock,
) -> Generator[TestClient, None, None]:
    """
    Create TestClient with pre-loaded seed index for integration tests.
    """
    original_env = os.environ.get("VECTOR_STORE_PATH")
    original_seed = os.environ.get("SEED_INDEX_PATH")

    # Copy seed fixtures (ChromaDB structure)
    if seed_fixtures_path.exists():
        for item in seed_fixtures_path.iterdir():
            if item.is_file():
                shutil.copy(item, temp_index_path / item.name)
            elif item.is_dir() and item.name != "pdfs":
                target_dir = temp_index_path / item.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(item, target_dir)

    os.environ["VECTOR_STORE_PATH"] = str(temp_index_path)
    os.environ["SEED_INDEX_PATH"] = str(seed_fixtures_path)

    from src.main import app
    from src.services.index import IndexService

    # Create services with mocked embedding
    index_service = IndexService(embedding_service=mock_embedding_service)
    app.state.embedding_service = mock_embedding_service
    app.state.index_service = index_service

    with TestClient(app) as client:
        yield client

    # Restore environment
    if original_env is not None:
        os.environ["VECTOR_STORE_PATH"] = original_env
    else:
        os.environ.pop("VECTOR_STORE_PATH", None)

    if original_seed is not None:
        os.environ["SEED_INDEX_PATH"] = original_seed
    else:
        os.environ.pop("SEED_INDEX_PATH", None)

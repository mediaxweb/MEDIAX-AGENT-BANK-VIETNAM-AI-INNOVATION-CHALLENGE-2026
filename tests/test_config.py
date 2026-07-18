from pathlib import Path

from app.core.config import Configs


def test_storage_root_derives_persist_directories():
    configs = Configs(_env_file=None, storage_root="/data")

    assert configs.resolved_llama_chroma_persist_dir == "/data/chroma_db"
    assert configs.resolved_bm25_persist_dir == "/data/bm25_storage"
    assert configs.resolved_docstore_persist_dir == "/data/docstore"
    assert Path(configs.resolved_orchestrator_session_db_path) == Path(
        "/data/orchestrator_sessions.db"
    )


def test_session_db_falls_back_to_local_storage():
    configs = Configs(
        _env_file=None,
        storage_root=None,
        railway_volume_mount_path=None,
    )

    assert Path(configs.resolved_orchestrator_session_db_path) == Path(
        ".local_storage/orchestrator_sessions.db"
    )


def test_explicit_persist_directories_override_storage_root():
    configs = Configs(
        _env_file=None,
        storage_root="/data",
        llama_chroma_persist_dir="/custom/chroma",
        bm25_persist_dir="/custom/bm25",
        docstore_persist_dir="/custom/docstore",
    )

    assert configs.resolved_llama_chroma_persist_dir == "/custom/chroma"
    assert configs.resolved_bm25_persist_dir == "/custom/bm25"
    assert configs.resolved_docstore_persist_dir == "/custom/docstore"


def test_openclaw_api_key_is_trimmed():
    configs = Configs(_env_file=None, rag_brain_openclaw_api_key="  secret  ")

    assert configs.resolved_rag_brain_openclaw_api_key == "secret"

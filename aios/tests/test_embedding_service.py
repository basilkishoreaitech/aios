from services.embedding_service import FoundryIQAdapter


def test_foundry_iq_adapter_uses_stable_search_api_version():
    adapter = FoundryIQAdapter(
        endpoint="https://srch-aios-dev.search.windows.net",
        api_key="test-key",
        api_version="2026-04-01",
        knowledge_base_name="aios-kb",
        knowledge_source_name="aios-kb",
    )

    assert adapter.api_version == "2024-07-01"

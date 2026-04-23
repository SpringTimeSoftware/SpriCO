from pyrit.backend.sprico.pyrit_adapter.compatibility import get_pyrit_version_info, load_compatibility_matrix


def test_pyrit_version_info_reports_availability() -> None:
    info = get_pyrit_version_info()
    assert "available" in info
    assert "source" in info
    assert "error" in info


def test_compatibility_matrix_contains_features() -> None:
    payload = load_compatibility_matrix()
    assert "pyrit" in payload
    assert "features" in payload
    assert isinstance(payload["features"], list)
    assert any(feature["id"] == "pyrit.target.openai_vector_store" for feature in payload["features"])

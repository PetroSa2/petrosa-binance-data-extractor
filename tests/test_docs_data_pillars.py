"""Guard public documentation against obsolete direct-MySQL guidance."""

FORBIDDEN = (
    "db_adapter=mysql",
    "mysqladapter",
    "mysql_uri",
    "(primary) - production",
    "writes directly to mysql",
)
DOC_FILES = (
    "README.md",
    ".env.example",
    ".cursorrules",
    "docs/DEPLOYMENT_GUIDE.md",
    "docs/OPERATIONS_GUIDE.md",
    "docs/QUICK_REFERENCE.md",
)


def find_obsolete_guidance(path) -> list[str]:
    """Return obsolete matches in one documentation file."""
    contents = path.read_text(encoding="utf-8").lower()
    return [pattern for pattern in FORBIDDEN if pattern in contents]


def test_public_docs_use_data_manager():
    root = __import__("pathlib").Path(__file__).parents[1]
    assert not [match for filename in DOC_FILES for match in find_obsolete_guidance(root / filename)]


def test_checker_flags_mysql_adapter_in_temp_file(tmp_path):
    candidate = tmp_path / "stale.md"
    candidate.write_text("DB_ADAPTER=mysql\n", encoding="utf-8")
    assert find_obsolete_guidance(candidate)

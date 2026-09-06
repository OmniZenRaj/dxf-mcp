import pytest

from dxf_mcp import paths


@pytest.fixture(autouse=True)
def rooted(tmp_path, monkeypatch):
    monkeypatch.setenv(paths.ROOT_ENV, str(tmp_path))
    return tmp_path


def test_relative_path_resolves_under_root(rooted):
    assert paths.resolve("drawings/a.dxf") == rooted / "drawings" / "a.dxf"


def test_parent_traversal_is_refused():
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve("../../etc/passwd")


def test_absolute_path_outside_root_is_refused():
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve("/etc/passwd")


def test_symlink_escaping_root_is_refused(rooted, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.dxf").write_text("x")
    (rooted / "link.dxf").symlink_to(outside / "secret.dxf")
    with pytest.raises(paths.PathNotAllowed):
        paths.resolve("link.dxf")


def test_root_itself_is_allowed(rooted):
    assert paths.resolve(".") == rooted


def test_find_dxf_files_is_sorted_and_recursive(rooted):
    (rooted / "sub").mkdir()
    for name in ("b.dxf", "a.dxf", "sub/c.dxf", "notes.txt"):
        (rooted / name).write_text("x")
    assert [p.name for p in paths.find_dxf_files()] == ["a.dxf", "b.dxf", "c.dxf"]
    assert [p.name for p in paths.find_dxf_files(recursive=False)] == ["a.dxf", "b.dxf"]

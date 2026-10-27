from ts_iis_fetcher import settings


def test_remember_merges_and_round_trips(tmp_path):
    local = tmp_path / ".local" / "settings.json"
    assert settings.load_folders(local) == {}
    settings.remember(local, root=r"G:\DACN")
    settings.remember(local, dest=r"C:\out")
    assert settings.load_folders(local) == {"root": r"G:\DACN", "dest": r"C:\out"}


def test_broken_file_falls_back_to_empty(tmp_path):
    local = tmp_path / "settings.json"
    local.write_text("not json", encoding="utf-8")
    assert settings.load_folders(local) == {}

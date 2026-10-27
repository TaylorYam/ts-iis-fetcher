from ts_iis_fetcher import settings


def test_local_roots_override_defaults_and_round_trip(tmp_path):
    products = tmp_path / "products.toml"
    products.write_text("[roots]\nFCN = 'G:\\FCN'\nDACN = ''\n", encoding="utf-8")
    local = tmp_path / ".local" / "settings.json"
    cfg = settings.load(products, local)
    assert cfg.products == ["FCN", "DACN"] and cfg.product == "FCN" and cfg.roots["FCN"] == r"G:\FCN"
    cfg.roots["DACN"] = r"G:\DACN"
    cfg.roots["SUPERBALL"] = r"G:\SB"
    cfg.product, cfg.dest = "DACN", r"C:\out"
    settings.save(cfg, local)
    again = settings.load(products, local)
    assert again.roots == {"FCN": r"G:\FCN", "DACN": r"G:\DACN", "SUPERBALL": r"G:\SB"}
    assert (again.product, again.dest) == ("DACN", r"C:\out")


def test_broken_files_fall_back_to_empty(tmp_path):
    local = tmp_path / "settings.json"
    local.write_text("not json", encoding="utf-8")
    cfg = settings.load(tmp_path / "missing.toml", local)
    assert cfg.roots == {} and cfg.product == "" and cfg.dest == ""

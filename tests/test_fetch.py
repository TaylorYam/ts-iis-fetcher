from pathlib import Path

import pytest

from ts_iis_fetcher.fetch import fetch, parse_tdccs

A = "029199990001"
B = "325199990002"


def pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF " + path.name.encode())
    return path


def both(root: Path, folder: str, code: str) -> None:
    pdf(root / folder / f"{code}_TS.pdf")
    pdf(root / folder / f"{code}_IIS.pdf")


def test_parse_keeps_order_dedups_and_restores_leading_zero():
    text = f"TDCC\n{A}\r\n{B}\t{A}, 29199990003\n20261027 12345"
    assert parse_tdccs(text) == [A, B, "029199990003"]


def test_copies_both_files_into_dest(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    both(root, A, A)
    [found] = fetch(root, [A], dest)
    assert found.ok and found.status == "完成"
    assert sorted(p.name for p in dest.iterdir()) == [f"{A}_IIS.pdf", f"{A}_TS.pdf"]


def test_reports_missing_folder_and_missing_kind(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    pdf(root / A / f"{A}_TS.pdf")
    pdf(root / A / "其他.pdf")
    root.joinpath(B).mkdir()
    no_folder, = fetch(root, ["000000000000"], dest)
    assert no_folder.status == "找不到商品資料夾"
    a, b = fetch(root, [A, B], dest)
    assert a.copied == ["TS"] and a.status == "找不到 IIS" and a.mark("IIS") == "缺"
    assert b.status == "找不到 TS；找不到 IIS"


def test_finds_tdcc_folder_at_any_depth_and_nested_files(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    pdf(root / "2026" / "10月" / A / "final" / f"{A}_TS.pdf")
    pdf(root / "2026" / "10月" / A / f"{A}_IIS.pdf")
    pdf(root / f"{B} 某某" / f"{B}_TS.pdf")  # 名稱不是剛好等於 TDCC 的資料夾不算
    a, b = fetch(root, [A, B], dest)
    assert a.ok and a.folder == root / "2026" / "10月" / A
    assert b.status == "找不到商品資料夾"


def test_same_name_folders_are_not_guessed(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    both(root, f"2025/{A}", A)
    both(root, f"2026/{A}", A)
    [found] = fetch(root, [A], dest)
    assert found.copied == [] and found.status.startswith("找到 2 個同名商品資料夾")


def test_missing_root_raises(tmp_path):
    with pytest.raises(OSError):
        fetch(tmp_path / "nope", [A], tmp_path / "out")


def test_duplicate_files_in_folder_are_not_guessed(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    pdf(root / A / "v1" / f"{A}_TS.pdf")
    pdf(root / A / "v2" / f"{A}_TS.pdf")
    pdf(root / A / f"{A}_IIS.pdf")
    [found] = fetch(root, [A], dest)
    assert found.copied == ["IIS"] and found.status == "TS 有 2 份"


def test_wrong_suffix_is_not_taken(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    pdf(root / A / f"{A}_ TS.pdf")
    pdf(root / A / f"{A}_IIS.pdf")
    [found] = fetch(root, [A], dest)
    assert found.status == "找不到 TS"

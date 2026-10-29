from pathlib import Path

from ts_iis_fetcher.orders import fetch_orders

A = "029199990001"
B = "325199990002"


def msg(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MSG " + path.name.encode())
    return path


def test_copies_every_order_mail_at_any_depth(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    msg(root / "2026" / A / f"{A} Order Confirmation.msg")
    msg(root / "2026" / A / "信件" / "RE_ order 確認.MSG")
    msg(root / "2026" / A / "Termsheet.msg")  # 檔名沒有 Order
    msg(root / "2026" / A / "Order.pdf")  # 不是 Outlook 信件
    [found] = fetch_orders(root, [A], dest)
    assert found.ok and found.mark() == "2 封"
    assert sorted(p.name for p in dest.iterdir()) == [f"{A} Order Confirmation.msg", f"{A}_RE_ order 確認.MSG"]


def test_same_named_mails_of_different_tdccs_do_not_overwrite(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    msg(root / A / "Order.msg")
    msg(root / B / "Order.msg")
    a, b = fetch_orders(root, [A, B], dest)
    assert a.ok and b.ok
    assert sorted(p.name for p in dest.iterdir()) == [f"{A}_Order.msg", f"{B}_Order.msg"]


def test_reports_missing_folder_and_missing_mail(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    msg(root / A / "Termsheet.msg")
    a, b = fetch_orders(root, [A, B], dest)
    assert a.status == "找不到 Order 信" and a.mark() == "缺"
    assert b.status == "找不到商品資料夾"


def test_same_name_mails_in_one_folder_are_not_guessed(tmp_path):
    root, dest = tmp_path / "share", tmp_path / "out"
    msg(root / A / "v1" / "Order.msg")
    msg(root / A / "v2" / "Order.msg")
    msg(root / A / "Order 2.msg")
    [found] = fetch_orders(root, [A], dest)
    assert [p.name for p in found.copied] == [f"{A}_Order 2.msg"]
    assert found.status == "「Order.msg」有 2 封同名"

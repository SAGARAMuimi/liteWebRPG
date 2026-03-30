#!/usr/bin/env python3
"""
data/gen_sql.py
===============
seed/ ディレクトリの CSV から DB システム別の初期データ投入 SQL を生成する。

使い方:
    # 標準出力に SQLite 用 SQL を出力
    python text_rpg/data/gen_sql.py --dialect sqlite

    # ファイルに出力
    python text_rpg/data/gen_sql.py --dialect sqlite     -o text_rpg/data/db_init.sql
    python text_rpg/data/gen_sql.py --dialect mysql      -o text_rpg/data/init_mysql.sql
    python text_rpg/data/gen_sql.py --dialect postgresql -o text_rpg/data/init_postgresql.sql

    # 特定テーブルのみ生成
    python text_rpg/data/gen_sql.py --dialect sqlite --table enemies skills

CSV フォーマット:
    - 1 行目: カラム名（モデルの列名と一致させること）
    - 空文字列フィールド → SQL の '' （空文字列リテラル）
    - "NULL" フィールド  → SQL の NULL
    - コンマを含む値は CSV 規格に従いダブルクォートで囲む
      例: "warrior,knight"
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

# seed/ ディレクトリは gen_sql.py と同じディレクトリに置く
SEED_DIR = Path(__file__).parent / "seed"

# テーブルの処理順序（外部キー依存の昇順）
TABLE_ORDER: list[str] = ["dungeons", "enemies", "skills", "items", "equipments"]

# PostgreSQL の ON CONFLICT 句で使用する主キー列名
TABLE_PK: dict[str, str] = {
    "dungeons":   "id",
    "enemies":    "id",
    "skills":     "id",
    "items":      "id",
    "equipments": "id",
}


# ---------------------------------------------------------------------------
# SQL 値変換
# ---------------------------------------------------------------------------

def sql_val(v: str) -> str:
    """CSV フィールド値を SQL リテラル文字列に変換する。

    変換規則:
        空文字列      → ''   (空文字列リテラル)
        "NULL"        → NULL (大文字小文字不問)
        整数文字列    → そのまま（クォートなし）
        浮動小数点    → そのまま（クォートなし）
        その他文字列  → シングルクォートで囲み、内部の ' を '' にエスケープ
    """
    if v.upper() == "NULL":
        return "NULL"
    if v == "":
        return "''"
    try:
        int(v)
        return v
    except ValueError:
        pass
    try:
        float(v)
        return v
    except ValueError:
        pass
    # 文字列: シングルクォート囲み＋エスケープ
    return "'" + v.replace("'", "''") + "'"


# ---------------------------------------------------------------------------
# INSERT 文生成（方言別）
# ---------------------------------------------------------------------------

def generate_insert(dialect: str, table: str, columns: list[str], rows: list[list[str]]) -> str:
    """1 テーブル分の INSERT SQL ブロックを生成して返す。

    Args:
        dialect:  "sqlite" | "mysql" | "postgresql"
        table:    テーブル名
        columns:  カラム名リスト
        rows:     CSV から読み込んだ行リスト（各行は文字列のリスト）

    Returns:
        セミコロン終端の SQL 文字列
    """
    col_list = "(" + ", ".join(columns) + ")"

    # 値行を構築（最後の行はカンマなし）
    value_lines: list[str] = []
    for i, row in enumerate(rows):
        vals = ", ".join(sql_val(v) for v in row)
        comma = "," if i < len(rows) - 1 else ""
        value_lines.append(f"  ({vals}){comma}")

    values_block = "\n".join(value_lines)

    if dialect == "sqlite":
        # SQLite 独自構文: INSERT OR IGNORE
        return f"INSERT OR IGNORE INTO {table} {col_list} VALUES\n{values_block};\n"

    elif dialect == "mysql":
        # MySQL 独自構文: INSERT IGNORE
        return f"INSERT IGNORE INTO {table} {col_list} VALUES\n{values_block};\n"

    elif dialect == "postgresql":
        # PostgreSQL 標準: INSERT … ON CONFLICT (pk) DO NOTHING
        pk = TABLE_PK.get(table, "id")
        return (
            f"INSERT INTO {table} {col_list} VALUES\n"
            f"{values_block}\n"
            f"ON CONFLICT ({pk}) DO NOTHING;\n"
        )

    else:
        raise ValueError(f"未対応の方言: {dialect!r}  (sqlite / mysql / postgresql のいずれかを指定)")


# ---------------------------------------------------------------------------
# CSV 読み込み
# ---------------------------------------------------------------------------

def load_csv(table: str) -> tuple[list[str], list[list[str]]]:
    """seed/{table}.csv を読み込み (列名リスト, 行リスト) を返す。

    空行（全フィールドが空白）は自動スキップする。
    """
    csv_path = SEED_DIR / f"{table}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV が見つかりません: {csv_path}")

    with open(csv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = [row for row in reader if any(cell.strip() for cell in row)]

    return headers, rows


# ---------------------------------------------------------------------------
# 全体 SQL 生成
# ---------------------------------------------------------------------------

def generate_all(dialect: str, tables: list[str] | None = None) -> str:
    """全テーブル（または指定テーブル）の INSERT SQL を生成して返す。

    Args:
        dialect: "sqlite" | "mysql" | "postgresql"
        tables:  生成対象テーブル名リスト。None または空リストで全テーブル。
    """
    target = tables if tables else TABLE_ORDER
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header_lines = [
        f"-- 自動生成: gen_sql.py --dialect {dialect}  [{now}]",
        f"-- 元データ: text_rpg/data/seed/*.csv",
        f"-- !! 直接編集禁止 — seed/*.csv を更新後に再生成すること !!",
        f"--",
        f"-- 再生成コマンド:",
        f"--   python text_rpg/data/gen_sql.py --dialect sqlite     -o text_rpg/data/db_init.sql",
        f"--   python text_rpg/data/gen_sql.py --dialect mysql      -o text_rpg/data/init_mysql.sql",
        f"--   python text_rpg/data/gen_sql.py --dialect postgresql -o text_rpg/data/init_postgresql.sql",
        f"--",
        f"-- [NOTE] テーブル DDL は SQLAlchemy の create_all() / migrate_db() が担当する。",
        f"-- [NOTE] 既存 DB へのスキーマ変更は models/database.py の migrate_db() を使うこと。",
        "",
    ]

    body_lines: list[str] = []
    for table in target:
        try:
            columns, rows = load_csv(table)
        except FileNotFoundError as e:
            body_lines.append(f"-- [WARNING] {e}\n")
            continue

        body_lines.append(f"-- {table}  ({len(rows)} 行)")
        body_lines.append(generate_insert(dialect, table, columns, rows))

    return "\n".join(header_lines) + "\n".join(body_lines)


# ---------------------------------------------------------------------------
# CLI エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gen_sql.py",
        description="seed/*.csv から DB 方言別 INSERT SQL を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python text_rpg/data/gen_sql.py --dialect sqlite
  python text_rpg/data/gen_sql.py --dialect mysql      -o text_rpg/data/init_mysql.sql
  python text_rpg/data/gen_sql.py --dialect postgresql -o text_rpg/data/init_postgresql.sql
  python text_rpg/data/gen_sql.py --dialect sqlite --table enemies skills
        """,
    )
    parser.add_argument(
        "--dialect",
        choices=["sqlite", "mysql", "postgresql"],
        default="sqlite",
        help="出力 SQL の方言  (デフォルト: sqlite)",
    )
    parser.add_argument(
        "--table",
        nargs="*",
        choices=TABLE_ORDER,
        metavar="TABLE",
        help=f"生成対象テーブル（省略時は全テーブル）  選択肢: {', '.join(TABLE_ORDER)}",
    )
    parser.add_argument(
        "--output", "-o",
        default="-",
        help="出力先ファイルパス（デフォルト: 標準出力）",
    )

    args = parser.parse_args()
    sql = generate_all(args.dialect, args.table or None)

    if args.output == "-":
        sys.stdout.write(sql + "\n")
    else:
        out_path = Path(args.output)
        out_path.write_text(sql + "\n", encoding="utf-8")
        print(f"✅ 出力完了: {out_path}  ({len(sql):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()

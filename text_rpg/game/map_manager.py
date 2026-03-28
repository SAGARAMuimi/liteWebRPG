"""
game/map_manager.py - R-14 グリッドマップ移動ロジック

グリッド型ダンジョン（map_type='grid'）専用のマップ管理クラス。
マップデータは config.FLOOR_MAPS に静的定義されており、
プレイヤーの現在座標 (x, y) を保持して移動・描写・イベント判定を行う。
"""

from __future__ import annotations

from config import (
    FLOOR_MAPS,
    DIRECTIONS,
    DIRECTION_NAMES_JA,
    CELL_WALL,
    CELL_DESCRIBE,
)


class MapManager:
    """
    グリッドマップ上のプレイヤー位置管理と移動ロジックを担う。

    Attributes:
        floor        : 現在のフロア番号
        x            : 現在のX座標
        y            : 現在のY座標
        grid         : フロアのグリッドデータ [y][x]
        start        : スタート座標 (x, y)
        goal         : ゴール座標（ボス部屋） (x, y)
        fixed_events : 座標 → イベント種別の固定マップ
    """

    def __init__(self, floor: int, x: int, y: int) -> None:
        """
        Parameters
        ----------
        floor : フロア番号（config.FLOOR_MAPS のキー）
        x     : プレイヤーの初期X座標
        y     : プレイヤーの初期Y座標
        """
        if floor not in FLOOR_MAPS:
            raise KeyError(f"フロア {floor} のマップデータが config.FLOOR_MAPS に定義されていません。")
        floor_data = FLOOR_MAPS[floor]
        self.floor: int = floor
        self.x: int = x
        self.y: int = y
        self.grid: list[list[int]] = floor_data["grid"]
        self.start: tuple[int, int] = floor_data["start"]
        self.goal: tuple[int, int] = floor_data["goal"]
        self.fixed_events: dict[tuple[int, int], str] = floor_data.get("fixed_events", {})

    # ------------------------------------------------------------------
    # 移動判定
    # ------------------------------------------------------------------

    def can_move(self, direction: str) -> bool:
        """
        指定方向へ移動できるかどうかを返す。

        通路（CELL_PASSAGE）・スタート（CELL_START）・ゴール（CELL_GOAL）は
        移動可能。壁（CELL_WALL）および範囲外は移動不可。

        Parameters
        ----------
        direction : "north" / "south" / "east" / "west"
        """
        if direction not in DIRECTIONS:
            raise ValueError(f"不正な方向: '{direction}'（有効値: {list(DIRECTIONS.keys())}）")
        dx, dy = DIRECTIONS[direction]
        nx, ny = self.x + dx, self.y + dy
        if ny < 0 or ny >= len(self.grid) or nx < 0 or nx >= len(self.grid[0]):
            return False
        return self.grid[ny][nx] != CELL_WALL

    def available_directions(self) -> list[str]:
        """移動可能な方向名のリストを返す（"north" / "south" / "east" / "west"）"""
        return [d for d in DIRECTIONS if self.can_move(d)]

    # ------------------------------------------------------------------
    # 移動
    # ------------------------------------------------------------------

    def move(self, direction: str) -> tuple[int, int]:
        """
        指定方向へ移動し、新しい座標 (x, y) を返す。

        Parameters
        ----------
        direction : "north" / "south" / "east" / "west"

        Returns
        -------
        (x, y) : 移動後の座標

        Raises
        ------
        ValueError : 移動不可の方向が指定された場合
        """
        if not self.can_move(direction):
            raise ValueError(f"方向 '{direction}' には移動できません。")
        dx, dy = DIRECTIONS[direction]
        self.x += dx
        self.y += dy
        return self.x, self.y

    # ------------------------------------------------------------------
    # 位置判定
    # ------------------------------------------------------------------

    def is_goal(self) -> bool:
        """現在地がゴールマス（ボス部屋）かどうか"""
        return (self.x, self.y) == self.goal

    def is_start(self) -> bool:
        """現在地がスタートマスかどうか"""
        return (self.x, self.y) == self.start

    # ------------------------------------------------------------------
    # セル情報
    # ------------------------------------------------------------------

    def cell_at(self, x: int, y: int) -> int:
        """
        指定座標のセル種別を返す。範囲外の場合は CELL_WALL を返す。

        Parameters
        ----------
        x, y : 確認したい座標
        """
        if y < 0 or y >= len(self.grid) or x < 0 or x >= len(self.grid[0]):
            return CELL_WALL
        return self.grid[y][x]

    # ------------------------------------------------------------------
    # テキスト描写
    # ------------------------------------------------------------------

    def describe_surroundings(self) -> str:
        """
        現在地の周辺4方向を描写するテキストを返す。

        例::

            北: 壁が立ちはだかっている。
            南: 暗い通路が続いている。
            東: 重厚な扉が見える…何かが待ち構えているようだ。
            西: 壁が立ちはだかっている。
        """
        lines: list[str] = []
        for direction, (dx, dy) in DIRECTIONS.items():
            cell = self.cell_at(self.x + dx, self.y + dy)
            dir_ja = DIRECTION_NAMES_JA[direction]
            desc = CELL_DESCRIBE.get(cell, "???")
            lines.append(f"{dir_ja}: {desc}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # イベント
    # ------------------------------------------------------------------

    def get_fixed_event(self) -> str | None:
        """
        現在地に固定イベントが設定されていれば event_type を返す。
        設定がなければ None を返す。

        Returns
        -------
        str | None : "encounter" / "trap" / "merchant" / "shrine" / "rest" / "chest" など
        """
        return self.fixed_events.get((self.x, self.y))

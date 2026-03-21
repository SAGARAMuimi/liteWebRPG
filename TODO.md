# liteWebRPG 改良要件 TODO リスト

凡例: ✅ 完了 / ⬜ 未着手  
依存矢印 `→` は「左が完了しないと右を始めにくい」関係を示す。

---

## 依存関係ツリー

```
                    ┌─ R-07 レベルアップ拡張 ⬜
                    ├─ R-06 クールダウン可視化 ⬜
                    ├─ R-12 敵AI（疑似AI）⬜ ──────────┐
独立して着手可 ───── ├─ R-13 味方自動行動AI ⬜           │
                    ├─ R-15 メタ進行（恒久解放）⬜       │
                    │                                    │
                    ├─ R-01 クラス拡張 ✅                │
                    │     └→ R-03 ターゲット/ヘイト ✅ ──┤
                    │                                    │
                    ├─ R-09 難易度調整レバー ✅           │
                    │                                    ↓
                    └─ R-02 バフ/デバフ ✅              R-12 は R-02/R-04 があると精度 UP
                          └→ R-04 状態異常 ✅
                                └→ R-13 と連携

R-05 アイテム ⬜ ─→ R-08 分岐・イベントマス ⬜
               └──→ R-10 通貨・町機能 ⬜ ─→ R-11 装備システム ⬜

R-14 マップ移動 ⬜  ← DungeonManager 全面再設計が前提（最後に着手）
```

---

## フェーズ別 タスクリスト

### ✅ Phase 0 — 完了済み

| 状態 | ID | 要件名 | 完了内容 |
|---|---|---|---|
| ✅ | R-01 | クラス拡張（4→8クラス） | `config.py` / `db_init.sql` / `helpers.py` / `1_character.py` |
| ✅ | R-09 | 難易度調整レバー | `DIFFICULTY_PRESETS` / `2_dungeon.py` / `3_battle.py` |
| ✅ | R-02 | バフ/デバフシステム | `models/skill.py` / `game/battle.py` / `3_battle.py` / `migrate_db()` |

---

### ⬜ Phase 1 — 優先度 P1（次に着手）

依存：R-01 ✅ / R-02 ✅ が前提

#### R-03 ターゲット/ヘイト制御
- [x] `game/battle.py` の `enemy_action()` に挑発（ヘイトテーブル）を追加
- [x] 騎士「挑発」スキルが `battle_buffs` の `taunt` フラグを立てる処理
- [x] ヘイト最大のキャラクターを優先ターゲットにするロジック
- **依存**: R-01（挑発スキル）✅、R-02（バフ管理基盤）✅

#### R-04 状態異常システム
- [x] `battle_buffs` に `status` エントリ（`poison`/`stun`/`def_down`/`silence`）を追加
- [x] `BattleEngine.tick_buffs()` で毒ダメージ・スタン判定を処理
- [x] `player_action()` でスタン・沈黙チェックを追加
- [x] `enemies` テーブルに `status_resistance` カラムを追加（`migrate_db()` 更新）
- [x] `3_battle.py` に状態異常アイコン表示を追加
- **依存**: R-02（`battle_buffs` 基盤）✅

#### R-05 アイテム（消耗品）
- [x] `models/item.py` を新規作成（Item モデル）
- [x] `models/inventory.py` を新規作成（ユーザー所持品）
- [x] `data/db_init.sql` に初期アイテムデータを追加
- [x] `3_battle.py` の行動選択に「アイテム」ボタンを追加
- [x] `2_dungeon.py` の探索中にアイテム使用 UI を追加
- **依存**: なし（独立実装可）→ R-08, R-10 への布石

#### R-08 分岐・イベントマス
- [x] `config.py` にイベント確率テーブルを追加
- [x] `game/dungeon.py` の `check_encounter()` をイベント種別返却に変更
- [x] `2_dungeon.py` に各イベント（罠/祈り/休憩/商人）の UI を追加
- **依存**: R-05（商人マスの場合）と連携 ※ 商人マスを最後にすれば先行実装可

---

### ⬜ Phase 2 — 優先度 P2

#### R-06 クールダウン可視化
- [X] `skills` テーブルに `cooldown` カラムを追加（`migrate_db()` 更新）
- [X] `BattleEngine` にスキルごとの残ターン管理 dict を追加
- [X] `3_battle.py` のスキルボタンにカウントダウン表示
- **依存**: なし（独立実装可）

#### R-07 レベルアップ拡張（選択式成長）
- [X] `models/character.py` の `level_up()` に分岐パラメータを追加
- [X] `3_battle.py` の勝利画面にレベルアップ時の成長方針選択 UI を追加
- **依存**: なし（独立実装可）

#### R-10 通貨・町機能
- [x] `models/user.py` に `gold` カラムを追加
- [x] `models/item.py` (R-05) にショップ価格を追加
- [X] `pages/4_town.py` を新規作成（購入/休息/帰還）
- **依存**: R-05（アイテムモデル）

#### R-11 装備システム
- [X] `models/equipment.py` を新規作成
- [X] `models/character.py` のステータス計算を「基礎値＋装備補正」に変更
- [X] `pages/1_character.py` に装備管理 UI を追加
- **依存**: R-10（通貨・購入フロー）と連動

#### R-12 敵AI（疑似AI）
- [X] `game/battle.py` の `enemy_action()` をルールベース AI に置き換え
  - 通常時: 攻撃→スキル→攻撃のローテーション
  - HP50%以下: 回復/妨害優先
  - 勝ち筋: 瀕死対象 or 最高ATK対象を狙う
- **依存**: なし（独立実装可）。R-02/R-04 があると精度 UP

---

### ⬜ Phase 3 — 優先度 P3（後回し）

#### R-13 味方自動行動AI
- [X] `st.session_state` に各キャラの行動方針（攻撃/防御/回復）を追加
- [X] `1_character.py` または `3_battle.py` に方針設定 UI を追加
- [X] `BattleEngine` に自動行動メソッドを追加
- **依存**: R-04（状態異常）があると回復 AI の精度 UP

#### R-15 メタ進行（恒久解放）
- [ ] `models/user.py` に `meta_gold`/`meta_titles` カラムを追加
- [ ] 全滅時に meta 情報を DB に保存する処理を追加
- [ ] ゲーム開始時に meta 報酬を適用する処理を追加
- **依存**: なし（独立実装可）

#### R-14 マップ移動（直角構成）
- [ ] `models/dungeon.py` の `DungeonProgress` に `x`/`y` カラムを追加
- [ ] `game/dungeon.py` の `DungeonManager` を 2D グリッド対応に全面再設計
- [ ] `2_dungeon.py` を前後左右ボタン UI に変更
- [ ] グリッドマップ生成ロジックを実装（通路/壁/イベント配置）
- **依存**: `DungeonManager` が安定してから。他の全要件が揃った後に着手推奨

---

## 推奨着手順サマリ

```
R-03（ヘイト）─┐
               ├→ R-04（状態異常）→ R-13（味方AI）
R-05（アイテム）┤
               └→ R-08（イベントマス）
                                         ↓
R-12（敵AI） ─────────────── R-10（町）→ R-11（装備）
                                         ↓
R-06 / R-07 / R-15 ─────────── R-14（マップ移動）← 最後
```

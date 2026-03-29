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
- [X] `models/user.py` に `meta_gold`/`meta_titles` カラムを追加
- [X] 全滅時に meta 情報を DB に保存する処理を追加
- [X] ゲーム開始時に meta 報酬を適用する処理を追加
- **依存**: なし（独立実装可）

#### R-14 マップ移動（直角構成）
- [X] `models/dungeon.py` の `DungeonProgress` に `x`/`y` カラムを追加
- [X] `game/dungeon.py` の `DungeonManager` を 2D グリッド対応に全面再設計
- [X] `2_dungeon.py` を前後左右ボタン UI に変更
- [X] グリッドマップ生成ロジックを実装（通路/壁/イベント配置）
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

---

## ⬜ Phase A — 即時着手可（コスト低・独立）

#### R-20 ステータス表示改善（最小実装）
- [ ] `pages/3_battle.py` のパーティカードに `ATK {chara.attack}  DEF {chara.defense}` を追加
- [ ] `pages/2_dungeon.py` のパーティ欄にも同様に ATK/DEF を追加
- **依存**: なし（独立実装可）

#### R-16 お知らせ機能
- [x] `config.py` に `NOTICE_TEXT` / `NOTICE_LEVEL` デフォルト定数を追加
- [x] `app.py` のトップページ最上部に `st.info()` / `st.warning()` でお知らせを表示（空なら非表示）
- **依存**: なし（独立実装可）

#### R-23 ダンジョン入場前チェック
- [ ] `config.py` に各ダンジョンの推奨レベル定数を追加
- [ ] `pages/2_dungeon.py` の `render_dungeon_select()` に推奨レベル vs パーティ平均 Lv の判定ロジックを追加
- [ ] 判定結果（✅ / ⚠️ / 🔴）をダンジョンカードに1行表示
- **依存**: なし（独立実装可）

#### R-28 バトルスピード設定
- [ ] `models/user.py` に `battle_speed VARCHAR(8) DEFAULT 'normal'` カラムを追加
- [ ] `models/database.py` の `migrate_db()` に `battle_speed` カラム追加マイグレーションを追加
- [ ] `pages/1_character.py` または `app.py` のサイドバーに `st.radio` で速度選択 UI を追加・DB 保存
- [ ] `pages/3_battle.py` の `time.sleep()` 呼び出しをセッションの設定値から取得するよう変更
- **依存**: なし（独立実装可）

---

## ⬜ Phase B — UX整理スプリント（コスト低〜中）

#### R-17 探索ログ改善
- [ ] `pages/2_dungeon.py` の画面上部に現在地サマリー1行を常時表示（フロア・部屋・HP残量・アイテム数）
- [ ] 直前イベント結果を最新1件のみメイン表示に残す
- [ ] `st.session_state["dungeon_log"]` を `st.expander` 内に逆順で全履歴表示
- **依存**: なし（独立実装可）

#### R-18 戦闘ログ改善
- [ ] `game/battle.py` にターン区切り文字列（`── ターン {n} ──`）を挿入する処理を追加
- [ ] `pages/3_battle.py` の画面上部に戦闘サマリー1行を常時表示（ターン数・生存数・敵残数）
- [ ] 直前ターン分のログのみメイン表示に残す（区切り文字列で抽出）
- [ ] `st.session_state["battle_log"]` を `st.expander` 内に全履歴表示
- **依存**: R-18 と R-22 は同スプリントで設計すると効率的

#### R-22 フロアクリア統計
- [ ] `pages/3_battle.py` の勝利後画面に `st.metric` で統計4項目を横並び表示（総与ダメ・被ダメ・使用MP・経過ターン）
- [ ] `battle_log` から正規表現で数値を集計するロジックを追加（または `game/battle.py` に専用ログエントリを追加）
- **依存**: R-18（ログフォーマット統一）と同スプリントが望ましい

#### R-21 スキル説明ポップオーバー
- [ ] `models/skill.py` に `description VARCHAR(256)` カラムを追加
- [ ] `models/database.py` の `migrate_db()` に `description` カラム追加マイグレーションを追加
- [ ] `data/db_init.sql` の全スキルに `description` データを追記
- [ ] `pages/3_battle.py` のスキルパネルで各スキルボタン下に `st.caption()` で効果・MP・CD・対象を1行表示
- **依存**: なし（独立実装可）

#### R-20 ステータス表示改善（中規模）
- [ ] `pages/3_battle.py` のパーティカードに `st.expander("詳細 ▼")` を追加
- [ ] expander 内に Lv / EXP（次Lvまで）/ INT / 装備スロット（武器・防具・アクセサリ）を表示
- [ ] 装備情報を戦闘開始時に `st.session_state["party_equipment"]` にキャッシュ（DB追加アクセス防止）
- [ ] `pages/2_dungeon.py` のパーティ欄にも同様の expander を追加
- **依存**: R-20 最小実装完了後

#### R-24 サイドバー装備・バフ早見表
- [ ] `utils/helpers.py` に `render_party_sidebar(party, buffs)` ヘルパー関数を追加
- [ ] `pages/2_dungeon.py` の `st.sidebar` から `render_party_sidebar()` を呼び出す
- [ ] `pages/3_battle.py` の `st.sidebar` から `render_party_sidebar()` を呼び出す
- **依存**: R-20 中規模実装と連続実装が効率的

---

## ⬜ Phase C — 機能拡張スプリント（コスト中）

#### R-27 ゲーム内チュートリアル
- [ ] `models/user.py` に `tutorial_step INTEGER DEFAULT 0` カラムを追加（途中離脱再開のためステップ番号で保存）
- [ ] `models/database.py` の `migrate_db()` にマイグレーションを追加
- [ ] `utils/auth.py` の `init_session_defaults()` に `tutorial_step` をセッションへ反映
- [ ] `pages/1_character.py` にステップ式チュートリアルバナー（`st.info` + 次へ/スキップボタン）を追加
- [ ] 全ステップ完了またはスキップで `tutorial_step = -1`（完了フラグ）を DB に保存
- **依存**: R-16（お知らせ）・R-28（スピード設定）と同時に `users` テーブル変更をまとめると効率的

#### R-29 実績・称号システム
- [ ] `config.py` に `ACHIEVEMENT_CONDITIONS` 辞書を追加（称号ID・称号名・解除条件・説明）
- [ ] `utils/helpers.py` に `check_and_grant_achievements(db, user_id, context)` を追加（重複付与ガード込み）
- [ ] `pages/3_battle.py` の勝利・全滅時に `check_and_grant_achievements()` を呼び出す
- [ ] `pages/1_character.py` の「メタ進行」セクションに取得済み称号一覧を表示
- [ ] 新称号取得時に `st.balloons()` + `st.success()` で演出
- [ ] R-15 の `perseverance` 付与処理と重複しないよう統合
- **依存**: R-15（メタ進行）✅ が前提

#### R-26 パーティプリセット保存
- [ ] `models/party_preset.py` を新規作成（`party_presets` テーブル: `id` / `user_id` / `name` / `character_ids` [JSON] / `created_at`）
- [ ] `models/database.py` の `migrate_db()` にテーブル作成マイグレーションを追加
- [ ] `models/__init__.py` に `PartyPreset` をエクスポート追加
- [ ] `pages/1_character.py` のパーティ編成セクションに保存フォーム（最大3件）と呼び出しボタンを追加
- [ ] 4件目保存時は上書き対象選択 UI を表示
- [ ] キャラ削除時にそのキャラを含むプリセットを無効化（警告表示）
- **依存**: なし（独立実装可）

---

## ⬜ Phase D — R-14完成後・ユーザー増加後

#### R-19 オートマッピング
- [ ] `models/dungeon.py` の `DungeonProgress` に `map_data TEXT`（JSON）カラムを追加
- [ ] `models/database.py` の `migrate_db()` にマイグレーションを追加
- [ ] `game/map_manager.py` に踏破済みマスの ASCII グリッド描画ロジックを追加
- [ ] `pages/2_dungeon.py` に `st.toggle("🗺️ マップ表示")` を追加（ON/OFF 切り替え）
- [ ] 探索終了・中断時に `visited_cells` を `dungeon_progress.map_data` に JSON 保存
- [ ] 次回入場時に `map_data` から `visited_cells` を復元
- **依存**: R-14（マップ移動・グリッドダンジョン）✅ が前提

#### R-25 敵図鑑
- [ ] `models/enemy.py` に `EncounteredEnemy` モデルを追加（`user_id` / `enemy_id` / `first_seen_at` / `encounter_count`）
- [ ] `models/database.py` の `migrate_db()` にテーブル作成マイグレーションを追加
- [ ] `pages/3_battle.py` の戦闘開始時に遭遇情報を DB に記録（`encounter_count` インクリメント）
- [ ] `pages/7_bestiary.py` を新規作成（遭遇済み敵の一覧表示・未遭遇は `???`）
- [ ] 遭遇回数 10 回以上の敵にドロップアイテム情報を解放
- **依存**: R-05（アイテム）✅ 推奨（ドロップ解放機能のため）

#### R-30 難易度別ランキング
- [ ] `models/` に `DungeonResult` モデルを新規作成（`user_id` / `dungeon_id` / `difficulty` / `turns` / `gold_earned` / `cleared_at`）
- [ ] `models/database.py` の `migrate_db()` にテーブル作成・複合インデックスのマイグレーションを追加
- [ ] `pages/2_dungeon.py` の全フロア突破時にベスト記録を `dungeon_results` に保存（最短ターン更新方式）
- [ ] `pages/8_ranking.py` を新規作成（ダンジョン・難易度別トップ10表示・自分の記録を別枠強調）
- **着手条件**: 登録ユーザー数が 10 名以上になってから着手推奨

-- data/db_init.sql
-- 初期データ投入スクリプト
-- 使用方法: python -c "from models.database import init_db; init_db()" でテーブル作成後に実行

-- ダンジョン
INSERT OR IGNORE INTO dungeons (id, name, floor) VALUES
  (1, '暗黒の洞窟', 3);

-- 敵（1F）
INSERT OR IGNORE INTO enemies (id, name, dungeon_id, floor, hp, attack, defense, exp_reward, is_boss) VALUES
  (1,  'スライム',    1, 1,  20,  5,  2,  10, 0),
  (2,  'コウモリ',    1, 1,  15,  7,  1,  12, 0);

-- 敵（2F）
INSERT OR IGNORE INTO enemies (id, name, dungeon_id, floor, hp, attack, defense, exp_reward, is_boss) VALUES
  (3,  'ゴブリン',    1, 2,  35, 10,  4,  20, 0),
  (4,  'オーク',      1, 2,  40, 12,  5,  25, 0);

-- 敵（3F 通常）
INSERT OR IGNORE INTO enemies (id, name, dungeon_id, floor, hp, attack, defense, exp_reward, is_boss) VALUES
  (5,  'ドラゴン',    1, 3,  60, 14,  6,  35, 0);

-- ボス（各階）
INSERT OR IGNORE INTO enemies (id, name, dungeon_id, floor, hp, attack, defense, exp_reward, is_boss) VALUES
  (10, 'ゴブリンキング',1, 1,  60, 10,  5,  50, 1),
  (11, 'オークチーフ',  1, 2,  90, 15,  8,  80, 1),
  (12, 'ダークロード',  1, 3, 120, 20, 10, 100, 1);

-- スキル（既存4クラス）
INSERT OR IGNORE INTO skills (id, name, class_type, mp_cost, power, effect_type) VALUES
  (1, 'ファイア',     'mage',    10, 30, 'attack'),
  (2, 'ヒール',       'priest',   8, 40, 'heal'),
  (3, 'バックスタブ', 'thief',    6, 25, 'attack'),
  (4, 'チャージ',     'warrior',  5, 20, 'attack'),
  (5, 'ポーション',   'all',      0, 30, 'heal');

-- スキル（追加4クラス）
INSERT OR IGNORE INTO skills (id, name, class_type, mp_cost, power, effect_type) VALUES
  -- 騎士: 防御バフ（挑発）・攻撃
  (6,  '挑発',       'knight',   4, 15, 'buff'),
  (7,  'シールドバッシュ', 'knight', 6, 15, 'attack'),
  -- 弓使い: 高威力単体攻撃
  (8,  '連射',       'archer',   7, 28, 'attack'),
  (9,  '矢雨',       'archer',  10, 35, 'attack'),
  -- 武道家: MP不要スキル
  (10, '気合い',     'monk',     0, 15, 'buff'),
  (11, '連打',       'monk',     0, 12, 'attack'),
  -- 吟遊詩人: バフ・回復
  (12, '鼓舞の歌',   'bard',     8, 15, 'buff'),
  (13, '癒しの歌',   'bard',    14, 55, 'heal');

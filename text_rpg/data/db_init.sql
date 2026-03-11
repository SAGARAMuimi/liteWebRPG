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

-- スキル（状態異常システム）
INSERT OR IGNORE INTO skills (id, name, class_type, mp_cost, power, effect_type, target_type, duration) VALUES
  (14, '浄化',   'priest',  5,  0, 'cure',     'ally',        0),
  (15, '毒霧',   'mage',   10,  0, 'poison',   'all_enemies', 3),
  (16, '目眩まし', 'thief',   7,  0, 'silence',  'enemy',       2),
  (17, '毒矢',   'archer',  6,  0, 'poison',   'enemy',       3),
  (18, '鎧裂き', 'warrior', 8,  0, 'def_down', 'enemy',       3);

-- スキル（追加4クラス）
INSERT OR IGNORE INTO skills (id, name, class_type, mp_cost, power, effect_type, target_type, duration) VALUES
  -- 騎士: 防御バフ（挑発）・攻撃
  (6,  '挑発',            'knight',   4,  5, 'buff_def', 'self',       3),
  (7,  'シールドバッシュ', 'knight',   6, 15, 'attack',   'enemy',      0),
  -- 弓使い: 高威力単体攻撃
  (8,  '連射',        'archer',   7, 28, 'attack',   'enemy',      0),
  (9,  '矢雨',        'archer',  10, 35, 'attack',   'enemy',      0),
  -- 武道家: MP不要スキル
  (10, '気合い',      'monk',     0,  4, 'buff_atk', 'self',       3),
  (11, '連打',        'monk',     0, 12, 'attack',   'enemy',      0),
  -- 吟遊詩人: 全体バフ・回復
  (12, '鼓舞の歌',    'bard',     8,  3, 'buff_atk', 'all_allies', 3),
  (13, '癒しの歌',    'bard',    14, 55, 'heal',     'ally',       0);

-- items テーブル（DDL）
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(64)  NOT NULL,
    description VARCHAR(256) NOT NULL DEFAULT '',
    effect_type VARCHAR(16)  NOT NULL,
    power       INTEGER      NOT NULL DEFAULT 0,
    target_type VARCHAR(16)  NOT NULL DEFAULT 'ally',
    duration    INTEGER      NOT NULL DEFAULT 0,
    price       INTEGER      NOT NULL DEFAULT 0
);

-- inventories テーブル（DDL）
CREATE TABLE IF NOT EXISTS inventories (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id),
    item_id  INTEGER NOT NULL REFERENCES items(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, item_id)
);

-- アイテム初期データ
INSERT OR IGNORE INTO items (id, name, description, effect_type, power, target_type, duration, price) VALUES
  (1, 'ポーション',       'HPを30回復する',               'heal_hp',  30, 'ally', 0,  50),
  (2, 'ハイポーション',   'HPを80回復する',               'heal_hp',  80, 'ally', 0, 150),
  (3, 'エーテル',         'MPを20回復する',               'heal_mp',  20, 'ally', 0,  80),
  (4, '万能薬',           '状態異常を全て回復する',       'cure',      0, 'ally', 0, 100),
  (5, 'フェニックスの羽', '戦闘不能を蘇生（HP30%）',     'revive',   30, 'ally', 0, 200),
  (6, '活力の薬',         'ATKを3上昇（3ターン）',       'buff_atk',  3, 'self', 3, 120);

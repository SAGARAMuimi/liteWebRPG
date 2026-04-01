-- 自動生成: gen_sql.py --dialect sqlite  [2026-03-30 15:45 UTC]
-- 元データ: text_rpg/data/seed/*.csv
-- !! 直接編集禁止 — seed/*.csv を更新後に再生成すること !!
--
-- 再生成コマンド:
--   python text_rpg/data/gen_sql.py --dialect sqlite     -o text_rpg/data/db_init.sql
--   python text_rpg/data/gen_sql.py --dialect mysql      -o text_rpg/data/init_mysql.sql
--   python text_rpg/data/gen_sql.py --dialect postgresql -o text_rpg/data/init_postgresql.sql
--
-- [NOTE] テーブル DDL は SQLAlchemy の create_all() / migrate_db() が担当する。
-- [NOTE] 既存 DB へのスキーマ変更は models/database.py の migrate_db() を使うこと。
-- dungeons  (2 行)
INSERT OR IGNORE INTO dungeons (id, name, floor, map_type) VALUES
  (1, '旅立ちの洞窟', 3, 'linear'),
  (2, '迷宮の神殿', 3, 'grid');

-- enemies  (16 行)
INSERT OR IGNORE INTO enemies (id, name, dungeon_id, floor, hp, attack, defense, exp_reward, gold_reward, is_boss, status_resistance, intelligence) VALUES
  (1, 'スライム', 1, 1, 20, 5, 2, 10, 8, 0, '', 1),
  (2, 'コウモリ', 1, 1, 15, 7, 1, 12, 10, 0, '', 1),
  (3, 'ゴブリン', 1, 2, 35, 10, 4, 20, 15, 0, '', 2),
  (4, 'オーク', 1, 2, 40, 12, 5, 25, 20, 0, '', 2),
  (5, 'ドラゴン', 1, 3, 60, 14, 6, 35, 30, 0, '', 2),
  (10, 'ゴブリンキング', 1, 1, 60, 10, 5, 50, 40, 1, 'stun', 3),
  (11, 'オークチーフ', 1, 2, 90, 15, 8, 80, 65, 1, 'stun', 3),
  (12, 'ダークロード', 1, 3, 120, 20, 10, 100, 100, 1, 'stun', 3),
  (20, 'ゾンビ', 2, 1, 30, 6, 3, 15, 12, 0, '', 1),
  (21, '骸骨剣士', 2, 1, 25, 8, 2, 18, 14, 0, '', 1),
  (22, '呪われた騎士', 2, 2, 50, 12, 6, 30, 25, 0, '', 2),
  (23, 'ダークエルフ', 2, 2, 40, 14, 4, 28, 22, 0, '', 2),
  (24, '死霊術師', 2, 3, 70, 16, 5, 40, 32, 0, '', 2),
  (25, '邪神の使徒', 2, 1, 70, 12, 6, 55, 45, 1, 'stun', 3),
  (26, '魔将軍', 2, 2, 100, 18, 9, 85, 70, 1, 'stun', 3),
  (27, '冥界の番人', 2, 3, 140, 24, 12, 110, 90, 1, 'stun', 3);

-- skills  (18 行)
INSERT OR IGNORE INTO skills (id, name, class_type, mp_cost, power, effect_type, target_type, duration, cooldown) VALUES
  (1, 'ファイア', 'mage', 10, 30, 'attack', 'enemy', 0, 0),
  (2, 'ヒール', 'priest', 8, 40, 'heal', 'ally', 0, 0),
  (3, 'バックスタブ', 'thief', 6, 25, 'attack', 'enemy', 0, 0),
  (4, 'チャージ', 'warrior', 5, 20, 'attack', 'enemy', 0, 0),
  (5, '応急手当', 'all', 0, 30, 'heal', 'ally', 0, 0),
  (6, '挑発', 'knight', 4, 5, 'buff_def', 'self', 3, 0),
  (7, 'シールドバッシュ', 'knight', 6, 15, 'attack', 'enemy', 0, 0),
  (8, '連射', 'archer', 7, 28, 'attack', 'enemy', 0, 0),
  (9, '矢雨', 'archer', 10, 35, 'attack', 'enemy', 0, 0),
  (10, '気合い', 'monk', 0, 4, 'buff_atk', 'self', 3, 0),
  (11, '連打', 'monk', 0, 12, 'attack', 'enemy', 0, 0),
  (12, '鼓舞の歌', 'bard', 8, 3, 'buff_atk', 'all_allies', 3, 0),
  (13, '癒しの歌', 'bard', 14, 55, 'heal', 'ally', 0, 0),
  (14, '浄化', 'priest', 5, 0, 'cure', 'ally', 0, 0),
  (15, '毒霧', 'mage', 10, 0, 'poison', 'all_enemies', 3, 0),
  (16, '目眩まし', 'thief', 7, 0, 'silence', 'enemy', 2, 0),
  (17, '毒矢', 'archer', 6, 0, 'poison', 'enemy', 3, 0),
  (18, '鎧裂き', 'warrior', 8, 0, 'def_down', 'enemy', 3, 0);

-- items  (6 行)
INSERT OR IGNORE INTO items (id, name, description, effect_type, power, target_type, duration, price) VALUES
  (1, 'ポーション', 'HPを30回復する', 'heal_hp', 30, 'ally', 0, 50),
  (2, 'ハイポーション', 'HPを80回復する', 'heal_hp', 80, 'ally', 0, 150),
  (3, 'エーテル', 'MPを20回復する', 'heal_mp', 20, 'ally', 0, 80),
  (4, '万能薬', '状態異常を全て回復する', 'cure', 0, 'ally', 0, 100),
  (5, 'フェニックスの羽', '戦闘不能を蘇生（HP30%）', 'revive', 30, 'ally', 0, 200),
  (6, '活力の薬', 'ATKを3上昇（3ターン）', 'buff_atk', 3, 'self', 3, 120);

-- equipments  (12 行)
INSERT OR IGNORE INTO equipments (id, name, description, slot, atk_bonus, def_bonus, hp_bonus, mp_bonus, price, required_class, disposable) VALUES
  (1, '銅の剣', '軽くて扱いやすい銅製の剣', 'weapon', 3, 0, 0, 0, 100, '', 0),
  (2, '鋼の剣', '頑丈な鋼製の両手剣。戦士・騎士向け', 'weapon', 6, 0, 0, 0, 280, 'warrior,knight', 0),
  (3, '魔法の杖', '魔力を込めた杖。MPも強化される', 'weapon', 3, 0, 0, 10, 200, 'mage,priest,bard', 0),
  (4, '短刀', '素早い連撃に特化した短刀', 'weapon', 5, 0, 0, 0, 150, 'thief,archer', 0),
  (5, '鉄の拳', '武道家専用の鉄製グローブ', 'weapon', 5, 2, 0, 0, 180, 'monk', 0),
  (6, '皮の鎧', '軽くて動きやすい革製の鎧', 'armor', 0, 3, 10, 0, 120, '', 0),
  (7, '鎖かたびら', '重厚な鎖製の鎧。重戦士向け', 'armor', 0, 7, 25, 0, 320, 'warrior,knight,monk', 0),
  (8, '魔法のローブ', '魔力を高める特殊素材のローブ', 'armor', 0, 2, 5, 20, 220, 'mage,priest,bard', 0),
  (9, '軽革鎧', '弓手や盗賊向けの軽量装甲', 'armor', 0, 4, 15, 5, 230, 'thief,archer', 0),
  (10, '体力のリング', '最大HPを上昇させる不思議な指輪', 'accessory', 0, 0, 20, 0, 150, '', 0),
  (11, '魔力のリング', '最大MPを上昇させる不思議な指輪', 'accessory', 0, 0, 0, 15, 150, '', 0),
  (12, '鋼の腕輪', '腕力を高める金属製の腕輪', 'accessory', 2, 0, 0, 0, 130, '', 0);


"""
Vocaloid Songs Database
"""

import sqlite3
import json

DATABASE = 'songs.db'

VOCALOID_COMPANY = {
    # Crypton Future Media
    '初音ミク': 'Crypton',
    '鏡音リン': 'Crypton',
    '鏡音レン': 'Crypton',
    '巡音ルカ': 'Crypton',
    'MEIKO': 'Crypton',
    'KAITO': 'Crypton',
    # Internet Co.
    'GUMI': 'Internet',
    'がくっぽいど': 'Internet',
    'Lily': 'Internet',
    # AHS
    '結月ゆかり': 'AHS',
    '東北ずん子': 'AHS',
    # Other
    'IA': '1st Place',
    'ONE': '1st Place',
    'flower': 'gynoid',
    '心華': 'GYNOID',
    '洛天依': 'Vsinger',
    '言和': 'Vsinger',
    '楽正綾': 'Vsinger',
}

GENRE_SIMILARITY = {
    'Pop': ['Pop', 'Electro Pop', 'Synth Pop', 'City Pop'],
    'Rock': ['Rock', 'J-Rock', 'Alternative Rock', 'Hard Rock'],
    'Ballad': ['Ballad', 'Slow', 'Piano'],
    'Electronic': ['Electronic', 'EDM', 'Techno', 'Trance', 'Dubstep'],
    'J-Pop': ['J-Pop', 'Pop', 'Anisong'],
    'Metal': ['Metal', 'Hard Rock', 'Screamo'],
    'Jazz': ['Jazz', 'Swing', 'Bossa Nova'],
    'Folk': ['Folk', 'Acoustic'],
    'Hip-Hop': ['Hip-Hop', 'Rap'],
    'Novelty': ['Novelty', 'Comedy', 'Meme'],
}

# Seed data: (title, title_jp, title_cn, producer, vocaloid, release_year, language, bpm, nico_views, genre, length_sec)
SEED_SONGS = [
    # ryo (supercell)
    ('Melt', 'メルト', 'Melt', 'ryo', '初音ミク', 2007, 'ja', 170, 15000000, 'Pop', 251),
    ('World is Mine', 'ワールドイズマイン', '世界第一的公主殿下', 'ryo', '初音ミク', 2008, 'ja', 165, 12000000, 'Pop', 258),
    ('Black Rock Shooter', 'ブラック★ロックシューター', '黑岩射手', 'ryo', '初音ミク', 2008, 'ja', 140, 8000000, 'Rock', 275),
    ('Koi wa Sensou', '恋は戦争', '恋爱即战争', 'ryo', '初音ミク', 2008, 'ja', 175, 5000000, 'Rock', 232),
    
    # kz (livetune)
    ('Tell Your World', 'Tell Your World', 'Tell Your World', 'kz', '初音ミク', 2012, 'ja', 128, 7000000, 'Electro Pop', 259),
    ('Packaged', 'Packaged', 'Packaged', 'kz', '初音ミク', 2007, 'ja', 130, 2000000, 'Electro Pop', 268),
    ('Weekender Girl', 'Weekender Girl', 'Weekender Girl', 'kz', '初音ミク', 2012, 'ja', 128, 1500000, 'Electro Pop', 237),
    
    # DECO*27
    ('Mozaik Role', 'モザイクロール', '马赛克卷', 'DECO*27', 'GUMI', 2010, 'ja', 145, 8000000, 'Rock', 203),
    ('Ghost Rule', 'ゴーストルール', '幽灵法则', 'DECO*27', '初音ミク', 2016, 'ja', 190, 20000000, 'Rock', 211),
    ('Hibana', 'ヒバナ', '火花', 'DECO*27', '初音ミク', 2017, 'ja', 200, 20000000, 'Rock', 205),
    ('Otome Kaibou', '乙女解剖', '少女解剖', 'DECO*27', '初音ミク', 2019, 'ja', 134, 10000000, 'Pop', 210),
    ('Vampire', 'ヴァンパイア', '吸血鬼', 'DECO*27', '初音ミク', 2021, 'ja', 164, 15000000, 'Pop', 187),
    ('Cinderella', 'シンデレラ', '灰姑娘', 'DECO*27', '初音ミク', 2020, 'ja', 147, 8000000, 'Pop', 167),
    ('Love Words IV', '愛言葉IV', '爱言叶IV', 'DECO*27', '初音ミク', 2022, 'ja', 140, 6000000, 'Pop', 215),
    
    # ハチ (Hachi)
    ('Matryoshka', 'マトリョシカ', '俄罗斯套娃', 'ハチ', '初音ミク', 2010, 'ja', 205, 10000000, 'Rock', 207),
    ('Donut Hole', 'ドーナツホール', '甜甜圈洞', 'ハチ', 'GUMI', 2013, 'ja', 140, 12000000, 'Rock', 225),
    ('Sand Planet', '砂の惑星', '沙之行星', 'ハチ', '初音ミク', 2017, 'ja', 95, 15000000, 'Electronic', 238),
    ('Panda Hero', 'パンダヒーロー', '熊猫英雄', 'ハチ', 'GUMI', 2011, 'ja', 190, 6000000, 'Rock', 205),
    
    # wowaka
    ('Rolling Girl', 'ローリンガール', '翻滚少女', 'wowaka', '初音ミク', 2010, 'ja', 195, 10000000, 'Rock', 207),
    ("World's End Dancehall", 'ワールズエンド・ダンスホール', '世界末日舞厅', 'wowaka', '初音ミク', 2010, 'ja', 171, 8000000, 'Rock', 229),
    ('Ura-Omote Lovers', '裏表ラバーズ', '表里情人', 'wowaka', '初音ミク', 2009, 'ja', 159, 7000000, 'Rock', 219),
    ('Unhappy Refrain', 'アンハッピーリフレイン', '不快乐的重复', 'wowaka', '初音ミク', 2011, 'ja', 200, 6000000, 'Rock', 248),
    
    # みきとP (MikitoP)
    ('1 2 Fanclub', 'いーあるふぁんくらぶ', '一二粉丝俱乐部', 'みきとP', 'GUMI', 2012, 'ja', 142, 6000000, 'Pop', 228),
    ('Roki', 'ロキ', '罗基', 'みきとP', '鏡音リン', 2018, 'ja', 150, 15000000, 'Rock', 175),
    ('Shoujo Rei', '少女レイ', '少女灵', 'みきとP', '初音ミク', 2017, 'ja', 150, 7000000, 'Pop', 199),
    
    # 40mP
    ('Karakuri Pierrot', 'からくりピエロ', '机关小丑', '40mP', '初音ミク', 2011, 'ja', 102, 7000000, 'Ballad', 227),
    ('Renai Yuusha', '恋愛勇者', '恋爱勇者', '40mP', 'GUMI', 2012, 'ja', 132, 3000000, 'Pop', 248),
    ('Doremi Rondo', 'ドレミファロンド', 'DoReMiFa Rondo', '40mP', '初音ミク', 2012, 'ja', 128, 2500000, 'Pop', 215),
    
    # Neru
    ('Tokyo Teddy Bear', '東京テディベア', '东京泰迪熊', 'Neru', '鏡音リン', 2011, 'ja', 204, 8000000, 'Rock', 183),
    ('Lost One no Goukoku', 'ロストワンの号哭', '迷失者的号哭', 'Neru', '鏡音レン', 2013, 'ja', 162, 10000000, 'Rock', 197),
    ('How-to Sekai Seifuku', 'ハウトゥー世界征服', '如何征服世界', 'Neru', '鏡音リン', 2013, 'ja', 140, 4000000, 'Rock', 195),
    
    # じん (Jin)
    ('Kagerou Days', 'カゲロウデイズ', '阳炎Days', 'じん', '初音ミク', 2011, 'ja', 200, 12000000, 'Rock', 223),
    ('Children Record', 'チルドレンレコード', '孩童记录', 'じん', 'IA', 2012, 'ja', 205, 8000000, 'Rock', 195),
    ('Lost Time Memory', 'ロスタイムメモリー', '伤停补时记忆', 'じん', 'IA', 2013, 'ja', 196, 5000000, 'Rock', 232),
    
    # れるりり
    ('Kami no Manimani', '神のまにまに', '随神之侧', 'れるりり', '初音ミク', 2014, 'ja', 120, 5000000, 'Pop', 226),
    
    # ギガP (GigaP)
    ('Gigantic O.T.N', 'ギガンティックO.T.N', 'Gigantic O.T.N', 'ギガP', '鏡音レン', 2013, 'ja', 140, 4000000, 'Electro Pop', 198),
    ('Okochama Sensou', 'おこちゃま戦争', '小孩战争', 'ギガP', '鏡音リン', 2014, 'ja', 175, 6000000, 'Pop', 179),
    ('Gimme×Gimme', 'Gimme×Gimme', 'Gimme×Gimme', 'ギガP', '初音ミク', 2019, 'ja', 128, 5000000, 'Electro Pop', 210),
    
    # ピノキオピー (PinocchioP)
    ('Common World Domination', 'ぼくらのすごいせかい', '我们的伟大世界', 'ピノキオピー', '初音ミク', 2014, 'ja', 160, 5000000, 'Pop', 212),
    ('Non-breath Oblige', 'ノンブレス・オブリージュ', '无呼吸义务', 'ピノキオピー', '初音ミク', 2021, 'ja', 164, 8000000, 'Pop', 210),
    ('God-ish', '神っぽいな', '像神一样', 'ピノキオピー', '初音ミク', 2022, 'ja', 142, 10000000, 'Pop', 209),
    ('Kirai Kirai Jigahidai', 'きらいきらいじがひだい', '讨厌讨厌自我肥大', 'ピノキオピー', '初音ミク', 2016, 'ja', 175, 3000000, 'Rock', 211),
    
    # ナユタン星人
    ('Alien Alien', 'エイリアンエイリアン', '外星人外星人', 'ナユタン星人', '初音ミク', 2016, 'ja', 152, 7000000, 'Pop', 189),
    ('Planet Loop', '惑星ループ', '行星环', 'ナユタン星人', '初音ミク', 2016, 'ja', 170, 8000000, 'Pop', 196),
    ('Dance Robot Dance', 'ダンスロボットダンス', '舞蹈机器人舞蹈', 'ナユタン星人', '初音ミク', 2017, 'ja', 170, 6000000, 'Pop', 184),
    
    # かいりきベア (Kairiki Bear)
    ('Venom', 'ベノム', '毒液', 'かいりきベア', 'flower', 2018, 'ja', 152, 10000000, 'Rock', 206),
    ('Bug', 'バグ', 'Bug', 'かいりきベア', '初音ミク', 2022, 'ja', 186, 8000000, 'Rock', 192),
    ('Angel', 'エンジェル', '天使', 'かいりきベア', '初音ミク', 2019, 'ja', 155, 5000000, 'Rock', 196),
    
    # Kanaria
    ('KING', 'KING', 'KING', 'Kanaria', 'GUMI', 2020, 'ja', 166, 12000000, 'Pop', 148),
    ('QUEEN', 'QUEEN', 'QUEEN', 'Kanaria', 'GUMI', 2021, 'ja', 128, 8000000, 'Pop', 157),
    ('EYE', 'EYE', 'EYE', 'Kanaria', 'GUMI', 2022, 'ja', 140, 5000000, 'Electro Pop', 142),
    
    # Chinozo
    ('Good-bye Sengen', 'グッバイ宣言', '再见宣言', 'Chinozo', 'flower', 2020, 'ja', 170, 20000000, 'Pop', 157),
    ('TAMAYA', 'TAMAYA', 'TAMAYA', 'Chinozo', 'flower', 2021, 'ja', 165, 5000000, 'Pop', 172),
    
    # ツミキ (Tsumiki)
    ('phony', 'フォニイ', 'phony', 'ツミキ', '初音ミク', 2021, 'ja', 170, 15000000, 'Rock', 193),
    
    # すりぃ (Surii)
    ('Envy Baby', 'エンヴィーベイビー', '嫉妒宝贝', 'すりぃ', '初音ミク', 2021, 'ja', 171, 7000000, 'Pop', 188),
    
    # 柊キライ
    ('Bocca della Verità', 'ボッカデラベリタ', '真理之口', '柊キライ', 'flower', 2020, 'ja', 170, 8000000, 'Rock', 188),
    
    # Ayase
    ('Ghost City Tokyo', '幽霊東京', '幽灵东京', 'Ayase', '初音ミク', 2019, 'ja', 128, 8000000, 'J-Pop', 217),
    
    # n-buna
    ('Dawn and Firefly', '夜明けと蛍', '黎明与萤火', 'n-buna', '初音ミク', 2017, 'ja', 130, 6000000, 'Ballad', 224),
    
    # Orangestar
    ('Daybreak Frontline', '夜明けのフロントライン', '黎明前线', 'Orangestar', 'IA', 2017, 'ja', 136, 7000000, 'Pop', 227),
    ('Henceforth', 'Henceforth', '从今以后', 'Orangestar', '初音ミク', 2020, 'ja', 132, 4000000, 'Pop', 222),
    
    # 稲葉曇 (Inabakumori)
    ('Lost Umbrella', 'ロストアンブレラ', '失落的伞', '稲葉曇', '初音ミク', 2019, 'ja', 170, 10000000, 'Rock', 196),
    ('Lagtrain', 'ラグトレイン', '延迟列车', '稲葉曇', '初音ミク', 2020, 'ja', 140, 6000000, 'Rock', 223),
    
    # ユリイ・キャノン (YurryCanon)
    ('Psychogram', 'サイコグラム', '心理图谱', 'ユリイ・キャノン', '初音ミク', 2019, 'ja', 200, 5000000, 'Rock', 207),
    
    # 和田たけあき (Wadatakeaki/KurageP)
    ('Chururira Chururira Daddadda!', 'チュルリラチュルリラダッダッダー！', '啾噜哩啦啾噜哩啦哒哒哒！', '和田たけあき', '結月ゆかり', 2016, 'ja', 220, 5000000, 'Rock', 209),
    
    # More classics
    ('Senbonzakura', '千本桜', '千本樱', '黒うさP', '初音ミク', 2011, 'ja', 154, 15000000, 'J-Pop', 250),
    ('Cantarella', 'カンタレラ', '坎特雷拉', '黒うさP', 'KAITO', 2008, 'ja', 110, 3000000, 'Ballad', 247),
    
    ('Miku Miku ni Shite Ageru', 'みくみくにしてあげる♪', '把你给MIKUMIKU掉', 'ika', '初音ミク', 2007, 'ja', 160, 10000000, 'Pop', 194),
    
    ('PoPiPo', 'ぽっぴっぽー', 'PoPiPo', 'ラマーズP', '初音ミク', 2008, 'ja', 150, 5000000, 'Novelty', 195),
    
    ('Double Lariat', 'ダブルラリアット', '双重回旋', 'アゴアニキP', '巡音ルカ', 2009, 'ja', 174, 5000000, 'Rock', 210),
    
    ('Just Be Friends', 'Just Be Friends', 'Just Be Friends', 'Dixie Flatline', '巡音ルカ', 2009, 'ja', 128, 6000000, 'Pop', 219),
    
    ('Magnet', 'magnet', '磁铁', 'minato', '初音ミク', 2009, 'ja', 108, 4000000, 'Pop', 260),
    
    ('Romeo and Cinderella', 'ロミオとシンデレラ', '罗密欧与灰姑娘', 'doriko', '初音ミク', 2009, 'ja', 146, 7000000, 'Pop', 260),
    
    ('Tsumugi Uta', '紡ぎ歌', '纺织之歌', 'DATEKEN', '鏡音リン', 2009, 'ja', 90, 2000000, 'Ballad', 264),
    
    ('Luka Luka Night Fever', 'ルカルカ★ナイトフィーバー', 'Luka Luka Night Fever', 'samfree', '巡音ルカ', 2009, 'ja', 128, 4000000, 'Electro Pop', 213),
    
    ('Hello, Planet', 'ハロー、プラネット。', '你好，星球', 'sasakure.UK', '初音ミク', 2009, 'ja', 160, 3000000, 'Electronic', 271),
    
    ('Two Breaths Walking', '二息歩行', '二息步行', 'DECO*27', '初音ミク', 2009, 'ja', 140, 3000000, 'Rock', 205),
    
    ('Electric Angel', 'えれくとりっく・えんじぇぅ', '电子天使', 'ヤスオP', '初音ミク', 2008, 'ja', 150, 4000000, 'Electro Pop', 247),
    
    ('The Disappearance of Hatsune Miku', '初音ミクの消失', '初音未来的消失', 'cosMo@暴走P', '初音ミク', 2008, 'ja', 240, 8000000, 'Rock', 292),
    
    ('Paradichlorobenzene', 'パラジクロロベンゼン', '对二氯苯', 'オワタP', '鏡音レン', 2009, 'ja', 120, 4000000, 'Rock', 235),
    
    ('Remote Controller', 'リモコン', '遥控器', 'じーざすP', '鏡音リン', 2011, 'ja', 165, 5000000, 'Pop', 214),
    
    ('Hatsune Miku no Gekishou', '初音ミクの激唱', '初音未来的激唱', 'cosMo@暴走P', '初音ミク', 2010, 'ja', 200, 4000000, 'Electronic', 277),
    
    ('Bad ∞ End ∞ Night', 'Bad ∞ End ∞ Night', 'Bad ∞ End ∞ Night', 'ひとしずくP', '初音ミク', 2012, 'ja', 160, 5000000, 'Pop', 254),
    
    ('Rokuchounen to Ichiya Monogatari', '六兆年と一夜物語', '六兆年零一夜物语', 'kemu', 'IA', 2012, 'ja', 186, 10000000, 'Rock', 215),
    
    ('Jinsei Reset Button', '人生リセットボタン', '人生重置按钮', 'kemu', 'GUMI', 2012, 'ja', 200, 4000000, 'Rock', 215),
    
    ('Setsuna Trip', '刹那トリップ', '刹那之旅', 'Last Note.', 'GUMI', 2013, 'ja', 145, 3000000, 'Rock', 219),
    
    ('Ringu no Uta', '林檎の唄', '苹果之歌', 'ゆうゆ', '初音ミク', 2013, 'ja', 128, 2000000, 'Pop', 219),
    
    ('Ame to Petora', '雨とペトラ', '雨与佩特拉', 'バルーン', 'flower', 2017, 'ja', 170, 5000000, 'Rock', 210),
    
    ('Charles', 'シャルル', '夏露露', 'バルーン', 'flower', 2017, 'ja', 135, 10000000, 'Pop', 227),
    
    ('Unknown Mother Goose', 'アンノウン・マザーグース', '未知的鹅妈妈', 'wowaka', '初音ミク', 2017, 'ja', 180, 7000000, 'Rock', 262),
    
    ('Teo', 'テオ', 'Teo', 'Omoi', '初音ミク', 2017, 'ja', 160, 5000000, 'Rock', 220),
    
    ('Solar System Disco', '太陽系デスコ', '太阳系迪斯科', 'ナユタン星人', '初音ミク', 2017, 'ja', 150, 7000000, 'Pop', 199),
    
    ('Bring It On', 'ブリング・イット・オン', '放马过来', 'GigaP', '鏡音リン', 2018, 'ja', 135, 4000000, 'Pop', 198),
    
    ('Outer Science', 'アウターサイエンス', '外层科学', 'じん', 'IA', 2013, 'ja', 195, 5000000, 'Rock', 215),
    
    ('Yuukei Yesterday', '夕景イエスタデイ', '夕景昨日', 'じん', 'IA', 2013, 'ja', 130, 4000000, 'Pop', 219),
    
    ('Additional Memory', 'アディショナルメモリー', '附加记忆', 'じん', '初音ミク', 2018, 'ja', 196, 3000000, 'Rock', 234),
    
    ('Young Girl A', '少女A', '少女A', 'Shino', '初音ミク', 2013, 'ja', 140, 4000000, 'Rock', 209),
    
    ('Leia', 'レイア', 'Leia', 'Neru', '初音ミク', 2011, 'ja', 180, 5000000, 'Rock', 195),
    
    ('Law-evading Rock', '脱法ロック', '逃法摇滚', 'Neru', '鏡音レン', 2016, 'ja', 155, 5000000, 'Rock', 196),
    
    # Chinese Vocaloid songs
    ('Common Disco', '普通DISCO', '普通DISCO', 'ilem', '洛天依', 2015, 'zh', 110, 5000000, 'Pop', 223),
    ('Qian Ben Ying', '权御天下', '权御天下', '乌龟Sui', '洛天依', 2015, 'zh', 160, 4000000, 'J-Pop', 255),
    ('Daedeok Hymn', '大氿歌', '大氿歌', 'ilem', '洛天依', 2019, 'zh', 128, 3000000, 'Folk', 244),
    ('Gou on Trial', '勾指起誓', '勾指起誓', 'ilem', '洛天依', 2019, 'zh', 138, 3000000, 'Pop', 223),
    ('Worldly Youth', '世末歌者', '世末歌者', 'COP', '洛天依', 2017, 'zh', 128, 3000000, 'Ballad', 264),
    ('Light Song', '光之歌', '光之歌', '清风疾行', '洛天依', 2016, 'zh', 130, 2000000, 'Pop', 218),
    ('Darkness Six', '黑之六', '黑之六', 'JUSF周存', '洛天依', 2015, 'zh', 175, 2000000, 'Rock', 230),
    ('Tiao Hai', '跳海', '跳海', '西风', '洛天依', 2018, 'zh', 140, 2000000, 'Pop', 233),
    ('Luo Tian Yi', '洛天依投食歌', '洛天依投食歌', 'ilem', '洛天依', 2016, 'zh', 128, 3000000, 'Novelty', 213),
    ('Qing Hua Ci', '青花瓷', '青花瓷', 'COP', '洛天依', 2016, 'zh', 120, 2500000, 'Folk', 262),
    ('Ye Xing Cai', '夜星彩', '夜星彩', 'COP', '洛天依', 2020, 'zh', 140, 1800000, 'Pop', 234),
    ('Chen Xing Yu', '辰星雨', '辰星雨', '乌龟Sui', '洛天依', 2018, 'zh', 145, 2000000, 'Pop', 240),
    ('Hua Xin', '花信', '花信', 'JUSF周存', '洛天依', 2018, 'zh', 132, 1800000, 'Ballad', 256),
    ('Yi Ren Xing', '一人行', '一人行', 'COP', '洛天依', 2019, 'zh', 125, 2200000, 'Pop', 228),
    ('Feng Guo', '风过', '风过', '清风疾行', '洛天依', 2017, 'zh', 136, 1500000, 'Folk', 250),
    ('Tian Xia', '天下', '天下', '乌龟Sui', '洛天依', 2016, 'zh', 155, 3500000, 'J-Pop', 248),
    ('Zui Meng', '醉梦', '醉梦', 'JUSF周存', '洛天依', 2019, 'zh', 118, 1600000, 'Ballad', 270),
    ('Yin He', '银河', '银河', 'ilem', '洛天依', 2020, 'zh', 142, 2800000, 'Pop', 216),
    ('Kong Xiang', '空想', '空想', 'COP', '洛天依', 2021, 'zh', 130, 1900000, 'Pop', 225),
    ('Shi Guang', '时光', '时光', '乌龟Sui', '洛天依', 2017, 'zh', 126, 2400000, 'Ballad', 258),
    
    # More recent hits
    ('Kyoufuu All Back', '強風オールバック', '强风All Back', 'ゆこぴ', '初音ミク', 2023, 'ja', 135, 20000000, 'Pop', 148),
    ('Rabbit Hole', 'ラビットホール', '兔洞', 'DECO*27', '初音ミク', 2023, 'ja', 145, 12000000, 'Pop', 168),
    ('Dame Ningen Da!', 'だめにんげんだ！', '不行人类哒！', 'ピノキオピー', '初音ミク', 2023, 'ja', 170, 6000000, 'Pop', 193),
    ('Show', 'ショウ', 'Show', 'Kanaria', 'GUMI', 2023, 'ja', 160, 7000000, 'Pop', 158),
    
    # Other classics
    ('Freely Tomorrow', 'FREELY TOMORROW', 'FREELY TOMORROW', 'Mitchie M', '初音ミク', 2012, 'ja', 125, 5000000, 'Electro Pop', 252),
    ('Ai Dee', 'アイディ', 'Ai Dee', 'Mitchie M', '初音ミク', 2013, 'ja', 128, 3000000, 'Electro Pop', 219),
    ('Viva Happy', 'ビバハピ', 'Viva Happy', 'Mitchie M', '初音ミク', 2014, 'ja', 128, 4000000, 'Pop', 217),
    ('Seraphim on the Ring', 'リングの熾天使', '擂台上的炽天使', 'Mitchie M', '初音ミク', 2015, 'ja', 140, 2000000, 'Pop', 245),
    
    ('Kokoro', 'ココロ', '心', 'トラボルタP', '鏡音リン', 2008, 'ja', 140, 5000000, 'Pop', 252),
    
    ('Saihate', 'さいはて', '最果', '小林オニキス', '初音ミク', 2008, 'ja', 136, 3000000, 'Pop', 214),
    
    ('Last Night, Good Night', 'Last Night, Good Night', 'Last Night, Good Night', 'kz', '初音ミク', 2008, 'ja', 72, 4000000, 'Ballad', 289),
    
    ('from Y to Y', 'from Y to Y', 'from Y to Y', 'ジミーサムP', '初音ミク', 2009, 'ja', 98, 4000000, 'Ballad', 275),
    
    ('No Logic', 'No Logic', 'No Logic', 'ジミーサムP', '巡音ルカ', 2010, 'ja', 140, 3000000, 'Pop', 247),
    
    ('Calc.', 'Calc.', 'Calc.', 'ジミーサムP', '初音ミク', 2011, 'ja', 86, 3000000, 'Ballad', 261),
    
    ('Starduster', 'Starduster', 'Starduster', 'ジミーサムP', '初音ミク', 2010, 'ja', 105, 3000000, 'Ballad', 378),
    
    ('Hello, How Are You', 'ハロ/ハワユ', 'Hello, How Are You', 'ナノウ', '初音ミク', 2010, 'ja', 95, 4000000, 'Ballad', 293),
    
    ('Ten-Faced', '十面相', '十面相', 'YM', 'GUMI', 2011, 'ja', 144, 4000000, 'Pop', 222),
    
    ('Blessing', 'Blessing', 'Blessing', 'halyosy', '初音ミク', 2014, 'ja', 132, 5000000, 'Pop', 243),
    
    ('Connecting', 'Connecting', 'Connecting', 'halyosy', '初音ミク', 2013, 'ja', 140, 3000000, 'Pop', 260),
    
    ('A Born Coward', '臆病者の譜', '胆小鬼的谱', 'ライブP', '初音ミク', 2012, 'ja', 132, 2000000, 'Pop', 234),
    
    ('Setsuna Plus', 'セツナプラス', '刹那Plus', 'じん', '初音ミク', 2020, 'ja', 200, 3000000, 'Rock', 210),
    
    ('Wah Wah World', 'ワーワーワールド', 'Wah Wah World', 'GigaP', '初音ミク', 2019, 'ja', 150, 3000000, 'Pop', 200),
    
    ('Ready Steady', 'Ready Steady', 'Ready Steady', 'GigaP', '初音ミク', 2020, 'ja', 115, 3000000, 'Pop', 192),
    
    ('Cendrillon', 'サンドリヨン', '灰姑娘', 'Dios/シグナルP', '初音ミク', 2008, 'ja', 147, 4000000, 'Pop', 260),
    
    ('Adolescence', 'アブストラクト・ナンセンス', '抽象废话', 'Neru', '鏡音リン', 2012, 'ja', 200, 3000000, 'Rock', 196),
    
    ('The Disease Called Love', '恋という病', '名为恋爱的病', 'Neru', '鏡音レン', 2017, 'ja', 176, 4000000, 'Rock', 193),
    
    ('EgoRock', 'エゴロック', '自我摇滚', 'すりぃ', '鏡音レン', 2022, 'ja', 225, 6000000, 'Rock', 178),
    
    ('Marshall Maximizer', 'マーシャル・マキシマイザー', '马歇尔最大化器', '柊マグネタイト', '初音ミク', 2021, 'ja', 190, 6000000, 'Rock', 175),
    
    ('Identity', 'アイデンティティ', '身份', 'Kanaria', '初音ミク', 2022, 'ja', 175, 5000000, 'Pop', 159),
    
    ('Lower', 'ロワー', '下层', 'ぬゆり', 'flower', 2021, 'ja', 140, 6000000, 'Rock', 189),
    
    ('Cute na Kanojo', '可愛いあの子', '那个可爱的女孩', 'すりぃ', '初音ミク', 2022, 'ja', 150, 4000000, 'Pop', 182),
    
    ('Zankyou Sanka', '残響散歌', '残响散歌', 'Aimer', '初音ミク', 2022, 'ja', 130, 5000000, 'J-Pop', 200),
    
    ('Umiyuri Kaiteitan', '海百合海底譚', '海百合海底谭', 'n-buna', '初音ミク', 2014, 'ja', 126, 5000000, 'Rock', 223),
    
    ('Shiwa', 'しわ', '皱纹', 'buzzG', 'GUMI', 2012, 'ja', 93, 3000000, 'Ballad', 253),
    
    ('Ring no Uta', '林檎の唄', '苹果之歌', 'ゆうゆ', '初音ミク', 2013, 'ja', 128, 2000000, 'Pop', 219),
    
    ('Shikyou Amanojaku', '死強天邪鬼', '死强天邪鬼', '鬱P', '初音ミク', 2014, 'ja', 200, 2000000, 'Metal', 211),
    
    ('Patchwork Staccato', 'ツギハギスタッカート', '拼凑断奏', 'とあ', '初音ミク', 2015, 'ja', 132, 5000000, 'Pop', 228),
    
    ('Heart a la Mode', 'ハートアラモード', 'Heart a la Mode', 'DECO*27', '初音ミク', 2015, 'ja', 128, 3000000, 'Pop', 201),
    
    ('Alkali Rettousei', 'アルカリレットウセイ', '碱性劣等生', 'かいりきベア', '初音ミク', 2016, 'ja', 192, 6000000, 'Rock', 205),
    
    ('Darling', 'ダーリン', 'Darling', 'MARETU', '初音ミク', 2018, 'ja', 128, 4000000, 'Pop', 210),
    
    ('Mind Brand', 'マインドブランド', '心灵烙印', 'MARETU', '初音ミク', 2017, 'ja', 160, 5000000, 'Rock', 207),
    
    ('Coin Locker Baby', 'コインロッカーベイビー', '投币储物柜宝贝', 'MARETU', '初音ミク', 2015, 'ja', 128, 4000000, 'Rock', 215),
    
    ('Hitorinbo Envy', '独りんぼエンヴィー', '独自嫉妒', 'koyori', '初音ミク', 2012, 'ja', 132, 6000000, 'Pop', 201),
    
    ('Tengaku', '天楽', '天乐', 'ゆうゆ', '鏡音リン', 2010, 'ja', 116, 3000000, 'Rock', 218),
    
    ('Tsugai Kogarashi', '番凩', '番凩', '仕事してP', 'MEIKO', 2009, 'ja', 144, 2000000, 'Folk', 226),
    
    ('Sweet Magic', 'スイートマジック', '甜蜜魔法', 'Junky', '鏡音リン', 2011, 'ja', 135, 4000000, 'Pop', 226),
    
    ('Happy Synthesizer', 'ハッピーシンセサイザ', '快乐合成器', 'EasyPop', 'GUMI', 2011, 'ja', 127, 5000000, 'Electro Pop', 250),
    
    ('Iroha Uta', 'いろは唄', '伊吕波歌', '銀サク', '鏡音リン', 2010, 'ja', 172, 3000000, 'Pop', 205),
    
    ('Suki Kirai', 'スキキライ', '喜欢讨厌', 'HoneyWorks', '鏡音リン', 2011, 'ja', 108, 3000000, 'Pop', 219),
    
    ('Tokyo Summer Session', '東京サマーセッション', '东京夏日Session', 'HoneyWorks', '初音ミク', 2014, 'ja', 160, 4000000, 'Pop', 216),
    
    ('Ai Kotoba', '愛言葉', '爱言叶', 'DECO*27', '初音ミク', 2009, 'ja', 137, 5000000, 'Pop', 252),
    ('Ai Kotoba II', '愛言葉II', '爱言叶II', 'DECO*27', '初音ミク', 2013, 'ja', 137, 4000000, 'Pop', 248),
    ('Ai Kotoba III', '愛言葉III', '爱言叶III', 'DECO*27', '初音ミク', 2018, 'ja', 140, 6000000, 'Pop', 240),
]


def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        title_jp TEXT,
        title_cn TEXT,
        producer TEXT NOT NULL,
        vocaloid TEXT NOT NULL,
        release_year INTEGER,
        language TEXT,
        bpm INTEGER,
        nico_views INTEGER DEFAULT 0,
        nico_sm_id TEXT,
        tier TEXT,
        genre TEXT,
        length_sec INTEGER
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS game_state (
        id INTEGER PRIMARY KEY DEFAULT 1,
        target_song_id INTEGER,
        difficulty TEXT DEFAULT 'normal',
        guesses_used INTEGER DEFAULT 0,
        max_guesses INTEGER DEFAULT 8,
        status TEXT DEFAULT 'playing',  -- playing, won, lost
        FOREIGN KEY (target_song_id) REFERENCES songs(id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS guess_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER DEFAULT 1,
        guess_number INTEGER,
        song_id INTEGER,
        result_json TEXT,
        guess_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (song_id) REFERENCES songs(id)
    )''')
    
    c.execute('SELECT COUNT(*) FROM songs')
    count = c.fetchone()[0]
    if count == 0:
        for s in SEED_SONGS:
            c.execute('''INSERT INTO songs 
                (title, title_jp, title_cn, producer, vocaloid, release_year, language, bpm, nico_views, genre, length_sec)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', s)
    
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM songs')
    print(f"Total songs: {c.fetchone()[0]}")
    conn.close()

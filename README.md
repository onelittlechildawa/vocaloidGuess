# Vocaloid 猜曲子

输入曲名或作者，猜出目标歌曲。参考 CS 猜选手玩法，按作者 / 虚拟歌手 / 发行年份 / 语言 / 级别 / 曲长 逐属性给出颜色反馈，8 次机会内猜中获胜。

## 功能

- 单人模式：日文传说 / 所有传说 / 中文传说 / 中文殿堂 / 所有神话 五个曲库
- 多人联机：BO1/3/5/7 赛制、房间码、观战、准备/开始、单局投降、房主调难度与下一局
- 曲库：4340 首（萌娘百科 + VocaDB + Niconico + B站 真实播放量与时长）
- 搜索支持中文 / 日文 / 英文 / 作者 / 歌姬名

## 启动

```bash
pip install fastapi uvicorn
python3 database.py   # 首次初始化数据库
python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000

## 曲库导入

```bash
python3 import_moegirl.py        # 日文传说/殿堂曲
python3 import_cn_hall_years.py  # 中文殿堂曲（分年）
python3 import_ace.py            # ACE 声库曲
python3 import_ace_cls.py        # ACE 神话/传说曲
python3 enrich_niconico.py       # Niconico 真实播放量 + 时长
python3 populate_views.py        # B站/Niconico 播放量
```

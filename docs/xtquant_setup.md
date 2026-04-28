# xtquant SDK 安装指南

## 方式 1: pip 安装（推荐）

```bash
pip install <QMT安装目录>/bin.x64/xtquant
```

## 方式 2: PYTHONPATH

```bash
export PYTHONPATH="/path/to/QMT/userdata_mini:$PYTHONPATH"
```

## 方式 3: 项目本地 libs/

将 xtquant 解压到项目根目录 `libs/xtquant/`，确保该目录已加入 `.gitignore`。

```bash
cp -r <QMT安装目录>/bin.x64/xtquant libs/xtquant
```

## 验证安装

```bash
python3 -c "from xtquant import xtdata; print(xtdata.get_trading_dates('SH'))"
```

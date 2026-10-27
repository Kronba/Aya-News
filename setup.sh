#!/usr/bin/env bash
# 文々日报（AyaNews）环境一键配置脚本
# 用法：bash setup.sh
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -d .venv ]; then
  echo "[1/4] 创建虚拟环境 .venv ..."
  "$PY" -m venv .venv
  .venv/bin/python -m ensurepip --upgrade
fi

echo "[2/4] 安装依赖（requirements.txt）..."
.venv/bin/python -m pip install -q -r requirements.txt

if [ ! -f config.yaml ]; then
  echo "[3/4] 生成默认配置 config.yaml ..."
  .venv/bin/python -m AyaNews.main --init --config config.yaml
else
  echo "[3/4] config.yaml 已存在，跳过（如需重置可删除后重跑本脚本）"
fi

if [ ! -f .env ]; then
  echo "[4/4] 生成 .env 模板（填入邮箱授权码即可）..."
  printf "CMATH_EMAIL_PASSWORD='把你的QQ邮箱授权码填到这里'\n" > .env
  chmod 600 .env
else
  echo "[4/4] .env 已存在，跳过"
fi

echo
echo "配置完成！接下来："
echo "  1. 编辑 config.yaml：关键词、期刊、收件人等"
echo "  2. 编辑 .env：填入 QQ 邮箱授权码"
echo "  3. 运行："
echo "     set -a && . ./.env && set +a && .venv/bin/python -m AyaNews.main --config config.yaml"

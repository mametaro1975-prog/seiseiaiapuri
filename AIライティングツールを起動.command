#!/bin/bash
# Finder からダブルクリックで AI ライティングツールを起動する

cd "$(dirname "$0")" || exit 1

PORT=8501

# すでに起動していれば、そのままブラウザを開くだけ
if curl -s -m 3 "http://localhost:$PORT/_stcore/health" | grep -q ok; then
  echo "すでに起動しています → http://localhost:$PORT"
  open "http://localhost:$PORT"
  echo "このウィンドウは閉じて大丈夫です。"
  exit 0
fi

echo "AI ライティングツールを起動しています..."
echo "止めるときは、このウィンドウで Ctrl + C を押してください。"
echo

# 起動を待ってからブラウザを開く
(
  for _ in $(seq 1 60); do
    if curl -s -m 2 "http://localhost:$PORT/_stcore/health" | grep -q ok; then
      open "http://localhost:$PORT"
      exit 0
    fi
    sleep 1
  done
) &

exec .venv/bin/streamlit run ai_writer/app.py --server.port "$PORT" --server.headless true

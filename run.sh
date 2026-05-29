#!/bin/bash
set -e

cd "$(dirname "$0")"

if ! command -v streamlit &>/dev/null; then
    echo "安裝套件中..."
    pip3 install -r requirements.txt
fi

if [ -n "$1" ]; then
    export ANTHROPIC_API_KEY="$1"
fi

echo "啟動股票監控系統..."
echo "開啟瀏覽器：http://localhost:8501"
streamlit run app.py --server.headless true

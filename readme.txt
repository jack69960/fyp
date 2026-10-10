# 如果还没有虚拟环境# 激活（每次打开新终端都要执行）
python -m venv .venv


.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install arxiv ollama pydantic tqdm neo4j networkx streamlit pyvis

python arxiv_kg_build.py
配置 Ollama（本地 LLM）:
安装：https://ollama.com/download
安装后重启 VS Code
终端验证：
PowerShellollama --version
ollama pull qwen2.5:3b
test:ollama run qwen2.5:3b "你好"
启动：
cd C:\Users\jack\Desktop\fyp
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install ollama pydantic tqdm
.\.venv\Scripts\python.exe extract_triples.py

cd C:\Users\jack\Desktop\fyp
.\.venv\Scripts\Activate.ps1
pip install neo4j
python import_neo4j.py


streamlit run app.py
然后回车跳过
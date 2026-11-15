# 如果还没有虚拟环境，先建一个
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

# ===== 本地 Neo4j（已装好，不再用云端 Aura）=====
# 数据库：Neo4j Community 5.26 便携版 + JDK 21，都在 C:\Users\jack\neo4j
# 启动数据库（开一个窗口跑着，别关）：
C:\Users\jack\neo4j\start-neo4j.bat
# 停止数据库：
C:\Users\jack\neo4j\stop-neo4j.bat
# 浏览器打开 http://localhost:7474 ，用户名 neo4j，密码 fyp-neo4j-2026
# 连接串：bolt://localhost:7687（app.py / import_neo4j.py 已改好，默认就是它）
# 换连接信息改项目根目录的 .env（NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD / NEO4J_DATABASE）
# 这个 .env 已经在 .gitignore 里，密码不会提交上去
# 想临时切回云端 Aura：把这四行改成 Aura 的连接串就行（旧的 Aura 连接信息在 git 历史里）
# 数据文件在 C:\Users\jack\neo4j\neo4j-community-5.26.0\data，备份就直接复制这个文件夹
# 一键启动（自动拉起数据库 -> 等就绪 -> 拉 Streamlit -> 开浏览器）：
start-app.bat
# 开机自动后台启动（装一次就行，不需要管理员）：
install-autostart.bat
# 取消开机自启：
remove-autostart.bat
# 全部关闭（Streamlit + Neo4j）：
stop-app.bat
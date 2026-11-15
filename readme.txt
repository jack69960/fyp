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

# ===== 远程访问（手机 / 别的电脑）=====
# 同一 Wi-Fi：http://192.168.3.182:8501（本机 WLAN 的 IP，换了网络要重新看 ipconfig）
# 外网：手机装 Tailscale 并登录同一账号后打开 http://100.85.166.111:8501
# 第一次从别的设备进来之前，先双击 allow-remote-access.bat 放行防火墙（点一次「是」就行）
# 端口固定在 8501，绑定 0.0.0.0，配置在 .streamlit/config.toml
# 想用固定 HTTPS 域名（https://laptop-94as84to.taila9417f.ts.net）：需要先在 Tailscale 管理台启用 Serve 一次

# ===== 数据源（app.py 自动选，不用改代码）=====
# 1) 有 st.secrets["neo4j"]（Streamlit Cloud 的 Secrets）：用它连 Aura
# 2) 否则读 .env / 环境变量：连本机 bolt://localhost:7687
# 3) 数据库连不上（比如云端服务器）：自动退回 data/graph_export.json 快照，网页照常可用
# 判断逻辑在 app.py 的 get_driver()；强制用快照测试：FYP_FORCE_JSON=1

# ===== 云端版（Streamlit Community Cloud）=====
# 公开地址：https://enoqqejpomw7a9vjhkwev7.streamlit.app/
# 部署来源：GitHub jack69960/fyp 的 main 分支，push 后自动重新构建
# 云端不连数据库，读的是仓库里的 data/graph_export.json

# ===== 知识图谱有新增内容后，刷新快照 =====
.\.venv\Scripts\python.exe export_graph_json.py
# 然后 git add data/graph_export.json && git commit && git push，云端会重新构建

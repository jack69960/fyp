ACADEMIC KNOWLEDGE GRAPH EXPLORER
Live demo (no installation needed):
    https://enoqqejpomw7a9vjhkwev7.streamlit.app/
download loacl llm：
    https://ollama.com/download
    ollama --version
    ollama pull qwen2.5:3b
    ollama run qwen2.5:3b "hello"  
environment install：
    cd C:\Users\jack\Desktop\fyp
    python -m venv .venv                      (only if .venv does not exist yet)
    .\.venv\Scripts\Activate.ps1
    python -m pip install -U pip
    python -m pip install -r requirements.txt

If `python` is not on PATH (Windows Store placeholder, or Anaconda installed
without PATH), call your interpreter by full path instead, for example:

    D:\anacoda\python.exe -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
auto start:
Then start everything with the one-click launcher:start-app.bat
It starts Neo4j, waits until port 7687 answers, starts Streamlit on port 8501
and opens the browser. To shut everything down:stop-app.bat


mannual start:
Step 1 — collect papers from arXiv
.\.venv\Scripts\python.exe arxiv_kg_build.py 
Step 2 — verify the local LLM
ollama list
Step 3 — extract triples
.\.venv\Scripts\python.exe extract_triples.py
Step 4 — start Neo4j and import the triples
C:\Users\jack\neo4j\start-neo4j.bat
.\.venv\Scripts\python.exe import_neo4j.py（Connect URL : bolt://localhost:7687 Username:neo4j  Password: fyp-neo4j-2026）
Step 5 — export the snapshot used by the cloud deployment
.\.venv\Scripts\python.exe export_graph_json.py
Step 5 — run the website
.\.venv\Scripts\python.exe -m streamlit run app.py-> http://localhost:8501

PREREQUISITES
  * Windows 10/11, PowerShell
  * Python 3.12+ (developed on 3.13). The pinned numpy 2.5.x and pandas 3.0.x
    do not install on older interpreters; if you only have 3.11 or lower,
    relax those two pins in requirements.txt.
  * Neo4j 5.x Community — optional. Without a database the app automatically
    falls back to the bundled snapshot (data/graph_export.json) and still runs.
  * Ollama — only needed if you want to re-extract triples with the local LLM.

ACCESS FROM OTHER DEVICES
Same Wi-Fi:
    http://<this-pc-lan-ip>:8501        e.g. http://192.168.3.182:8501
    (check the current address with `ipconfig`)

Over the internet, through Tailscale (both devices logged into the same
account):
    http://100.85.166.111:8501
Before the first connection from another device, double-click
allow-remote-access.bat once and approve the UAC prompt: it opens TCP 8501 in
Windows Firewall for the private and public profiles.

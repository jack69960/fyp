ACADEMIC KNOWLEDGE GRAPH EXPLORER
===============================
Final Year Project — an interactive knowledge graph of arXiv LLM research,
built from method–task–dataset triples extracted from paper abstracts.

Live demo (no installation needed):
    https://enoqqejpomw7a9vjhkwev7.streamlit.app/

The app answers two kinds of questions:

  1. Graph Explorer
     Browse the subgraph around a research topic, or around one to three
     tasks. A task subgraph has the shape
         Task <- USED_FOR - Method <- PROPOSES - Paper
                                   Method - EVALUATED_ON -> Dataset

  2. Research Gaps
     Heuristic candidate gaps derived from the same graph:
       - rare tasks (only a few methods address them)
       - methods never evaluated on a dataset
       - orphan methods (proposed by a single paper)
       - cross-topic methods (appear in more than one topic)

Snapshot shipped in this repo: 1054 nodes / 1732 relationships
  Paper 208, Method 477, Task 267, Dataset 102
  PROPOSES 556, USED_FOR 558, ADDRESSES 385, EVALUATED_ON 131, USES 102


QUICK START
-----------
    cd C:\Users\jack\Desktop\fyp
    python -m venv .venv                      (only if .venv does not exist yet)
    .\.venv\Scripts\Activate.ps1
    python -m pip install -U pip
    python -m pip install -r requirements.txt

Then start everything with the one-click launcher:

    start-app.bat

It starts Neo4j, waits until port 7687 answers, starts Streamlit on port 8501
and opens the browser. To shut everything down:

    stop-app.bat

To start the app manually instead:

    .\.venv\Scripts\python.exe -m streamlit run app.py
    -> http://localhost:8501


PREREQUISITES
-------------
  * Windows 10/11, PowerShell
  * Python 3.10+ (this project was developed on 3.13)
  * Neo4j 5.x Community — optional. Without a database the app automatically
    falls back to the bundled snapshot (data/graph_export.json) and still runs.
  * Ollama — only needed if you want to re-extract triples with the local LLM.


REBUILDING THE DATASET FROM SCRATCH (reproduction steps)
-------------------------------------------------------
Run the following steps in order from the repository root. Each step writes
into data/, so you can inspect the intermediate files.

Step 1 — collect papers from arXiv

    .\.venv\Scripts\python.exe arxiv_kg_build.py

  Reads the TOPICS table at the top of arxiv_kg_build.py (8 research topics
  such as opd, test_time_compute, moe, llm_agents), fetches up to 30 recent
  papers per topic (last 900 days, MAX_RESULTS_PER_TOPIC / DAYS_BACK), and
  writes data/arxiv_raw/papers_YYYYMMDD_HHMM.json.

Step 2 — install and verify the local LLM

    https://ollama.com/download
    ollama --version
    ollama pull qwen2.5:3b
    ollama run qwen2.5:3b "hello"          (sanity check, then leave with /exit)

Step 3 — extract triples

    .\.venv\Scripts\python.exe extract_triples.py

  Sends every paper title + abstract to qwen2.5:3b with a JSON-schema
  constrained prompt, keeps at most 3 triples per paper, and writes
  data/extracted/triples_YYYYMMDD_HHMM.json (+ an *_unmapped.json of papers
  whose answer could not be parsed). The shipped run produced 624 triples.

Step 4 — start Neo4j and import the triples

    C:\Users\jack\neo4j\start-neo4j.bat          (keep this window open)
    http://localhost:7474                        (user: neo4j)
    .\.venv\Scripts\python.exe import_neo4j.py

  The importer clears the database (CLEAR_DATABASE = True), creates the
  Paper / Method / Task / Dataset nodes and the PROPOSES, USES, USED_FOR,
  ADDRESSES, EVALUATED_ON relationships, and prints the final counts.

Step 5 — export the snapshot used by the cloud deployment

    .\.venv\Scripts\python.exe export_graph_json.py

  Writes data/graph_export.json (about 0.36 MB for the current graph). Commit
  this file when the graph changes — the Streamlit Cloud app reads it.


RUNNING THE APP
---------------
One-click:

    start-app.bat            start Neo4j + Streamlit + open the browser
    stop-app.bat             stop Streamlit and Neo4j
    install-autostart.bat    start the app hidden at every logon
    remove-autostart.bat     undo install-autostart.bat

Manual / for debugging (console output visible):

    C:\Users\jack\neo4j\start-neo4j.bat
    .\.venv\Scripts\python.exe -m streamlit run app.py

The server is pinned to port 8501 and listens on 0.0.0.0, both configured in
.streamlit/config.toml.


ACCESS FROM OTHER DEVICES
-------------------------
Same Wi-Fi:

    http://<this-pc-lan-ip>:8501        e.g. http://192.168.3.182:8501
    (check the current address with `ipconfig`)

Over the internet, through Tailscale (both devices logged into the same
account):

    http://100.85.166.111:8501

Before the first connection from another device, double-click
allow-remote-access.bat once and approve the UAC prompt: it opens TCP 8501 in
Windows Firewall for the private and public profiles.


CLOUD DEPLOYMENT (Streamlit Community Cloud)
-------------------------------------------
  * Source:  GitHub repository jack69960/fyp, branch main
  * URL:     https://enoqqejpomw7a9vjhkwev7.streamlit.app/
  * Data:    the repository copy of data/graph_export.json — no database is
             needed in the cloud
  * Deploy:  every push to main triggers a rebuild; the app sleeps after a
             period of inactivity and wakes up when the URL is opened again

If you ever want the cloud app to query a live Neo4j Aura instance instead,
add a [neo4j] section with uri / username / password / database to the app's
Secrets in Streamlit Cloud. The app prefers those secrets when they exist.


CONFIGURATION
-------------
Data source is selected automatically, in this order:

  1. st.secrets["neo4j"]     Streamlit Cloud secrets (Aura)
  2. .env / environment      local Neo4j Community
  3. data/graph_export.json  snapshot, used when 1 and 2 are unreachable

Environment variables (read from .env in the repository root):

    NEO4J_URI         default bolt://localhost:7687
    NEO4J_USER        default neo4j
    NEO4J_PASSWORD    the password of your local instance
    NEO4J_DATABASE    default neo4j
    FYP_FORCE_JSON=1  ignore the database and use the snapshot (testing)

.env is listed in .gitignore, so credentials are never committed. The command
shown in the sidebar ("Data source: live Neo4j" vs "bundled snapshot") tells
you which path was taken.


REPOSITORY LAYOUT
-----------------
    app.py                    Streamlit UI (graph explorer + research gaps)
    graph_json.py             pure-Python query layer over the JSON snapshot
    export_graph_json.py      Neo4j -> data/graph_export.json exporter
    import_neo4j.py           triples JSON -> Neo4j importer
    extract_triples.py        Ollama extraction of triples from abstracts
    arxiv_kg_build.py         arXiv harvester for paper metadata
    data/arxiv_raw/           raw paper metadata
    data/extracted/           extracted triples
    data/graph_export.json    graph snapshot consumed by the cloud app
    .streamlit/config.toml    server address / port / theme
    start-app.bat ...         one-click launchers (see above)


TROUBLESHOOTING
---------------
  Sidebar says "bundled snapshot" while running locally
      Neo4j is not running or the credentials in .env are wrong. Start it with
      C:\Users\jack\neo4j\start-neo4j.bat and check http://localhost:7474.

  "Could not reach Neo4j and the snapshot ... is missing"
      Neo4j is down and data/graph_export.json was not committed. Run
      export_graph_json.py (or start the database) and reload.

  Port 8501 already in use
      An older Streamlit process is still alive: run stop-app.bat, then
      start-app.bat again.

  Another device cannot open the page
      Run allow-remote-access.bat once (firewall), confirm both devices are
      on the same network (or the same Tailscale account), and check ipconfig.

  Extraction returns many unmapped papers
      qwen2.5:3b occasionally answers with malformed JSON; check the
      *_unmapped.json file next to the triples and re-run extract_triples.py.


NOTES
-----
  * The local Neo4j data lives in C:\Users\jack\neo4j\neo4j-community-5.26.0\data;
    back it up by copying that folder while the database is stopped.
  * data/ is what makes the cloud deployment work without a database — commit
    graph_export.json whenever the graph changes.
  * Never commit .env or any Aura credentials. If a password has ever been
    pushed to a public repository, rotate it in the Neo4j Aura console.

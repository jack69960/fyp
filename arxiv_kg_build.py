import arxiv
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
from tqdm import tqdm

# ==================== Configuration ====================
TOPICS = {
    # ==================== 1. On-Policy Distillation ====================
    "opd": [
        'all:"on-policy distillation"',
        'all:"online policy distillation"',
        'all:"on-policy knowledge distillation"',
        'all:"policy distillation"',
        'all:OPD AND all:distillation',
        'all:"sequence-level distillation"',
        'all:"generalized knowledge distillation"',
        'all:"knowledge distillation" AND all:"reinforcement learning"',
        'all:"self-distillation" AND (all:LLM OR all:reasoning)',
        'all:"teacher-student" AND all:"distillation" AND all:LLM',
        'all:"distillation" AND all:"chain-of-thought"',
    ],

    # ==================== 2. Test-Time Compute ====================
    "test_time_compute": [
        'all:"test-time compute"',
        'all:"test time scaling"',
        'all:"inference-time scaling"',
        'all:"inference scaling laws"',
        'all:"test-time adaptation"',
        'all:"test-time training"',
        'all:"reasoning scaling"',
        'all:"chain-of-thought scaling"',
        'all:"self-consistency" AND all:LLM',
        'all:"best-of-n" AND all:LLM',
        'all:"majority voting" AND all:reasoning',
        'all:"process reward model"',
        'all:"verifier" AND all:"reasoning" AND all:LLM',
        'all:"MCTS" AND all:"language model"',
        'all:"search" AND all:"reasoning" AND all:LLM',
    ],

    # ==================== 3. Mixture of Experts ====================
    "moe": [
        'all:"mixture of experts"',
        'all:"mixture-of-experts"',
        'all:"sparse mixture of experts"',
        'all:"sparse MoE"',
        'all:"soft MoE"',
        'all:"fine-grained MoE"',
        'all:MoE AND (all:language OR all:LLM OR all:transformer)',
        'all:"expert routing"',
        'all:"expert choice" AND all:transformer',
        'all:"load balancing" AND all:MoE',
        'all:"MoE" AND all:"efficient inference"',
        'all:"MoE" AND all:"scaling law"',
    ],

    # ==================== 4. LLM Agents ====================
    "llm_agents": [
        'all:"LLM agent"',
        'all:"language agent"',
        'all:"language model agent"',
        'all:"agentic" AND (all:LLM OR all:"language model")',
        'all:"tool-use" AND all:LLM',
        'all:"function calling" AND all:LLM',
        'all:ReAct AND all:agent',
        'all:"multi-agent" AND all:LLM',
        'all:"computer use" AND all:agent',
        'all:"web agent" AND all:LLM',
        'all:"code agent" AND all:LLM',
        'all:"planning" AND all:"LLM agent"',
        'all:"memory" AND all:"LLM agent"',
        'all:"reflection" AND all:"LLM agent"',
    ],

    # ==================== 5. Multimodal LLM ====================
    "multimodal_llm": [
        'all:"vision-language model"',
        'all:"multimodal LLM"',
        'all:"multimodal large language model"',
        'all:"visual instruction tuning"',
        'all:"vision-language-action"',
        'all:"VLA model"',
        'all:"video LLM"',
        'all:VLM AND all:reasoning',
        'all:"image-text" AND all:"reasoning"',
        'all:"multimodal reasoning"',
    ],

    # ==================== 6. RAG and Long Context ====================
    "rag_long_context": [
        'all:"retrieval-augmented generation"',
        'all:"retrieval augmented generation"',
        'all:RAG AND (all:LLM OR all:"language model")',
        'all:"long context" AND all:LLM',
        'all:"context extension"',
        'all:"long-context reasoning"',
        'all:"needle in a haystack" AND all:LLM',
        'all:"KV cache" AND all:efficient',
        'all:"speculative decoding"',
        'all:"context compression" AND all:LLM',
    ],

    # ==================== 7. Alignment and RLHF ====================
    "alignment_rlhf": [
        'all:"RLHF" AND all:LLM',
        'all:"reinforcement learning from human feedback"',
        'all:"DPO" AND all:alignment',
        'all:"direct preference optimization"',
        'all:"constitutional AI"',
        'all:"RLVR"',
        'all:"GRPO" AND all:reasoning',
        'all:"alignment" AND all:"language model"',
        'all:"reward model" AND all:LLM',
        'all:"jailbreak" AND all:LLM',
        'all:"safety alignment" AND all:LLM',
    ],

    # ==================== 8. Efficient LLM ====================
    "efficient_llm": [
        'all:"parameter-efficient fine-tuning"',
        'all:"LoRA" AND all:LLM',
        'all:"QLoRA"',
        'all:"quantization" AND all:LLM',
        'all:"post-training quantization"',
        'all:"KV cache compression"',
        'all:"flash attention"',
        'all:"sparse attention" AND all:LLM',
        'all:"distillation" AND all:"efficient inference"',
        'all:"pruning" AND all:LLM',
    ],
}

MAX_RESULTS_PER_TOPIC = 30      # Number of papers per topic
DAYS_BACK = 900                 # Only fetch papers from the last N days; None = no limit
OUTPUT_DIR = Path("data/arxiv_raw")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting
PAGE_SIZE = 25
DELAY_SECONDS = 5.0             # Delay between API requests
SLEEP_PER_PAPER = 1.0           # Additional wait per paper
SLEEP_BETWEEN_TOPICS = 10       # Wait between topics
# ============================================================

def build_query(keywords):
    keyword_part = " OR ".join(f"({k})" for k in keywords)
    category_part = "(cat:cs.LG OR cat:cs.AI OR cat:cs.CL OR cat:cs.CV OR cat:stat.ML)"
    return f"({keyword_part}) AND {category_part}"

def fetch_papers(topic_name, keywords, max_results=80):
    print(f"\nFetching topic: {topic_name} ...")
    query = build_query(keywords)
    print(f"Query: {query[:120]}...")

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    client = arxiv.Client(
        page_size=PAGE_SIZE,
        delay_seconds=DELAY_SECONDS,
        num_retries=10
    )

    papers = []
    # Initialize progress bar
    pbar = tqdm(total=max_results, desc=f"Fetching {topic_name}", unit="papers", ncols=100)

    try:
        for result in client.results(search):
            pbar.update(1)

            # Time filter: since results are sorted descending, break early once out of range
            if DAYS_BACK is not None:
                cutoff = datetime.now(result.published.tzinfo) - timedelta(days=DAYS_BACK)
                if result.published < cutoff:
                    print(f"\n  Reached time cutoff ({cutoff.strftime('%Y-%m-%d')}), stopping early for {topic_name}.")
                    break

            # Isolate per-paper parsing errors
            try:
                paper = {
                    "arxiv_id": result.get_short_id(),
                    "title": result.title.strip().replace("\n", " "),
                    "abstract": result.summary.strip().replace("\n", " "),
                    "authors": [a.name for a in result.authors],
                    "published": result.published.isoformat(),
                    "categories": result.categories,
                    "primary_category": result.primary_category,
                    "pdf_url": result.pdf_url,
                    "topic": topic_name,
                }
                papers.append(paper)
            except Exception as parse_e:
                print(f"\n  [Parse Warning] Skipping paper {getattr(result, 'entry_id', 'unknown')}: {parse_e}")
                continue

            if len(papers) >= max_results:
                break

            time.sleep(SLEEP_PER_PAPER)

    except Exception as e:
        print(f"\n  [Fetch Interrupted] Exception: {e}")
        print(f"  Collected {len(papers)} papers so far, will save and continue to next topic.")
    finally:
        pbar.close()

    print(f"-> Topic {topic_name} done, fetched {len(papers)} papers")
    return papers

def main():
    all_papers = []
    seen_ids = set()

    for topic_name, keywords in TOPICS.items():
        papers = fetch_papers(topic_name, keywords, max_results=MAX_RESULTS_PER_TOPIC)
        for p in papers:
            if p["arxiv_id"] not in seen_ids:
                seen_ids.add(p["arxiv_id"])
                all_papers.append(p)

        print(f"Waiting {SLEEP_BETWEEN_TOPICS} seconds before next topic...")
        time.sleep(SLEEP_BETWEEN_TOPICS)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = OUTPUT_DIR / f"papers_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 50)
    print(f"All done! Total unique papers fetched: {len(all_papers)}")
    print(f"Saved to: {output_file}")
    print("=" * 50)

    topic_count = Counter([p["topic"] for p in all_papers])
    print("\nPapers per topic:")
    for t, c in topic_count.most_common():
        print(f"  {t}: {c}")

if __name__ == "__main__":
    main()
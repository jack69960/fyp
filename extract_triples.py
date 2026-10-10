import json
import time
import re
from pathlib import Path
from typing import List, Dict, Optional
import ollama
from pydantic import BaseModel, Field, field_validator
from tqdm import tqdm

# ==================== Configuration ====================
DATA_DIR = Path("data/arxiv_raw")
if not DATA_DIR.exists() or not list(DATA_DIR.glob("papers_*.json")):
    raise FileNotFoundError("No arXiv data found. Please run the first-stage script!")

INPUT_JSON = sorted(DATA_DIR.glob("papers_*.json"))[-1]
print(f"Auto-loaded latest data file: {INPUT_JSON}")

OUTPUT_DIR = Path("data/extracted")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_NAME = "qwen2.5:3b"
MAX_PAPERS = None
MAX_RETRIES = 2
TIMEOUT_SECONDS = 90.0
# ========================================================

client = ollama.Client(timeout=TIMEOUT_SECONDS)


class Triple(BaseModel):
    method: str = Field(description="Specific method, model, or algorithm name")
    task: str = Field(description="Research task or problem")
    dataset: Optional[str] = Field(description="Dataset/benchmark used, or null if not specified", default=None)
    confidence: float = Field(description="Confidence score between 0 and 1", default=0.8)

    @field_validator('dataset')
    @classmethod
    def clean_dataset(cls, v):
        if not v or str(v).strip().upper() in {"N/A", "NA", "NONE", "NULL", "-"}:
            return None
        return str(v).strip()


class ExtractionResult(BaseModel):
    triples: List[Triple]


SYSTEM_PROMPT = """You are a professional academic information extraction assistant. Extract structured triples from the paper title and abstract.

Requirements:
1. method: method, model, or algorithm name (e.g., Flash-OPD, GRPO, LoRA).
2. task: research task (e.g., mathematical reasoning, code generation, language modeling).
3. dataset: dataset name. If not mentioned in the abstract, use null.
4. Extract AT MOST 3 triples. Keep each string short (under 40 characters).
5. Return ONLY content matching the JSON schema, no explanations."""


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.strip('.,;:()[]{}""\'')
    return text


def try_parse_partial_json(raw: str) -> List[Dict]:
    """Salvage complete triples from a truncated JSON string."""
    triples = []
    pattern = re.compile(
        r'\{\s*"method"\s*:\s*"(?P<method>[^"]*)"\s*,\s*'
        r'"task"\s*:\s*"(?P<task>[^"]*)"\s*,\s*'
        r'"dataset"\s*:\s*(?P<dataset>null|"(?:[^"\\]|\\.)*")\s*,\s*'
        r'"confidence"\s*:\s*(?P<confidence>[0-9.]+)\s*\}',
        re.DOTALL
    )
    for m in pattern.finditer(raw):
        ds_raw = m.group("dataset")
        ds = None if ds_raw == "null" else ds_raw.strip('"')
        triples.append({
            "method": m.group("method"),
            "task": m.group("task"),
            "dataset": ds,
            "confidence": float(m.group("confidence"))
        })
    return triples


def extract_from_paper(paper: Dict) -> List[Dict]:
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")

    abstract = abstract.encode('ascii', 'ignore').decode('ascii')
    if len(abstract) > 1200:
        abstract = abstract[:1200] + "..."

    user_content = f"Title: {title}\n\nAbstract: {abstract}\n\nExtract at most 3 triples."

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                format=ExtractionResult.model_json_schema(),
                options={
                    "temperature": 0.1,
                    "num_ctx": 2048,
                    "num_predict": 512
                }
            )

            content = response["message"]["content"]

            triples_data = []
            try:
                result = ExtractionResult.model_validate_json(content)
                for t in result.triples:
                    triples_data.append({
                        "method": t.method,
                        "task": t.task,
                        "dataset": t.dataset,
                        "confidence": t.confidence
                    })
            except Exception:
                salvaged = try_parse_partial_json(content)
                if not salvaged:
                    raise ValueError("JSON invalid and no triples could be salvaged")
                triples_data = salvaged

            triples = []
            for t in triples_data:
                triples.append({
                    "method": normalize_text(t["method"]),
                    "task": normalize_text(t["task"]),    # keep raw task
                    "dataset": normalize_text(t["dataset"]) if t.get("dataset") else None,
                    "confidence": round(float(t.get("confidence", 0.8)), 2),
                    "arxiv_id": paper.get("arxiv_id"),
                    "title": title,
                    "topic": paper.get("topic", "unknown")
                })
            return triples

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"\n[Retry {attempt+1}/{MAX_RETRIES}] {paper.get('arxiv_id')} failed: {e}")
                time.sleep(2)
                continue
            else:
                print(f"\n[Failed] {paper.get('arxiv_id')}: {e}")
                return []


def main():
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        papers = json.load(f)

    if MAX_PAPERS is not None:
        papers = papers[:MAX_PAPERS]

    print(f"Loaded {len(papers)} papers. Starting triple extraction with {MODEL_NAME}...\n")

    all_triples = []
    failed_ids = []
    success_count = 0

    for paper in tqdm(papers, desc="Extraction progress", ncols=100):
        triples = extract_from_paper(paper)
        if triples:
            all_triples.extend(triples)
            success_count += 1
        else:
            failed_ids.append(paper.get("arxiv_id", "unknown"))

        time.sleep(0.2)

    timestamp = time.strftime("%Y%m%d_%H%M")
    output_file = OUTPUT_DIR / f"triples_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_triples, f, ensure_ascii=False, indent=2)

    if failed_ids:
        failed_file = OUTPUT_DIR / f"failed_{timestamp}.txt"
        with open(failed_file, "w", encoding="utf-8") as f:
            f.write("\n".join(failed_ids))

    print("\n" + "="*55)
    print(f"Extraction complete!")
    print(f"Papers processed successfully : {success_count} / {len(papers)}")
    print(f"Total triples extracted       : {len(all_triples)}")
    if failed_ids:
        print(f"Failed papers                 : {len(failed_ids)}")
    print(f"Results saved to              : {output_file}")
    print("="*55)


if __name__ == "__main__":
    main()
# NaijaBiz AI: ML service

The "AI Business Brain". A FastAPI service the backend calls to turn voice, receipt photos and text into
**proposed actions**, answer questions about the business, and generate insights and forecasts.

**Golden rule:** this service never writes to the database. It returns proposals; the backend asks the
merchant to confirm and then saves.

## Run it

```bash
cd ml_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8080
# docs: http://localhost:8080/docs
pytest
```

## Cache models on Modal

`modal_models.py` downloads the configured ASR repositories and N-ATLaS into the persistent
`ml-service-models` Modal Volume. Hugging Face gated-model access must be approved for the account
behind the token. Create a Modal Secret named `huggingface-secret` containing `HF_TOKEN`, then run:

```bash
cd ml_service
pip install -r requirements-modal.txt
modal run modal_models.py
```

The downloader commits each repository to the Volume as it finishes, so a later failure does not
discard earlier downloads. Use `--model-repos` with a comma-separated list to choose different repos.
The files are stored in the standard Hugging Face cache at `/models/hf`; a Modal service using the
same Volume should mount it at `/models` and set `HF_HOME=/models/hf` to reuse that cache. The LLM
client in this service currently calls an OpenAI-compatible server; caching N-ATLaS here does not
start or configure an LLM inference server.

## Deploy the API on Modal

`modal_service.py` serves this FastAPI app on a T4 GPU, mounts `ml-service-models` at `/models`, and
sets `ASR_BACKEND=transformers` so ASR loads from the populated cache. Before deployment, create a
Modal Secret named `ml-service-api` containing `ML_API_KEY` with the same value configured for the
backend. The existing `huggingface-secret` is attached separately for Hugging Face access.

```bash
cd ml_service
modal deploy modal_service.py
```

The Modal deployment output includes the API URL. The T4 is allocated when the service handles
requests; ASR models load lazily and remain in memory while the container is warm. N-ATLaS is cached
in the Volume, but the LLM still requires a separately hosted OpenAI-compatible inference server.

With the defaults (`LLM_BACKEND=mock`, `ASR_BACKEND=mock`, `OCR_BACKEND=mock`) everything runs offline:
the parser uses rules, speech returns a demo phrase and receipts return the demo invoice. This lets the
backend and frontend integrate **today**, while you plug in the real models.

## Endpoints

| Endpoint | Input | Output |
| --- | --- | --- |
| `POST /transcribe` | audio file + `language` (en, yo, ha, ig) | transcript |
| `POST /interpret` | `{text, language, catalogue}` | `ActionProposal` |
| `POST /interpret/audio` | audio file + `language` | transcript parsed into an `ActionProposal` |
| `POST /parse-receipt` | receipt photo | supplier, items, total, warnings |
| `POST /ask` | `{question, language, snapshot or business_id}` | answer + facts used |
| `POST /insights` | `{snapshot}` | alerts |
| `POST /forecast` | `{snapshot, purchase_price?}` | days of stock left, cash flow, health score, affordability |
| `GET /health` | | status and active backends |

All request and response shapes are in `app/schemas.py`. Send the shared secret in `X-API-Key` when `ML_API_KEY` is set.

Try it:

```bash
curl -X POST localhost:8080/interpret -H 'Content-Type: application/json' \
  -d '{"text":"I just bought 50 bags of rice for 4 million naira","language":"en"}'
```

## Layout

```
app/main.py            FastAPI app + API key check
app/config.py          all settings from env vars
app/schemas.py         the shared contract (ActionProposal, ReceiptResponse, BusinessSnapshot...)
app/routers/           one file per endpoint group
app/services/
  asr.py               speech recognition (N-ATLaS)
  llm.py               OpenAI-compatible client (vLLM / hosted), JSON retries
  intent_parser.py     text -> intent + entities (LLM, then rules fix the numbers)
  receipt_reader.py    OCR + LLM -> items, with validation warnings
  product_matcher.py   "coke" -> "Coca-Cola" from the merchant's catalogue
  ask_business.py      question -> real figures -> phrased answer
  insights.py          alert rules
  forecasting.py       days of stock, cash flow, affordability, health score
  language.py          confirmation messages per language
  backend_client.py    read-only calls to the backend
app/prompts/           LLM prompts as markdown files
app/utils/naira.py     "4 million", "120k", "₦80,000" -> numbers
scripts/               eval_asr.py (WER), eval_intent.py, eval_receipt.py
data/eval/             your test phrases, recordings and receipts
tests/                 pytest
```

## Your to-do list (replace the mocks)

1. **Get model access** on Hugging Face (N-ATLaS ASR and N-ATLaS-LLM). Put the real repo ids in `.env`
   (`ASR_MODEL_ID`, `LLM_MODEL`). I could not verify the exact repo names, so check the model pages.
2. **Serve the LLM** with vLLM on a rented GPU (see the hosting notes) and set `LLM_BACKEND=openai_compatible`,
   `LLM_BASE_URL`, `LLM_MODEL`. Keep a hosted API as a backup behind the same settings.
3. **ASR:** set `ASR_BACKEND=transformers`, install `requirements-ml.txt`, and finish the language handling
   in `asr.py` (TODO: how N-ATLaS selects Yoruba, Hausa or Igbo).
4. **Test phrases:** fill `data/eval/phrases.csv` with 10-15 native-speaker phrases per language and record
   matching audio in `data/eval/audio/`. Run the eval scripts and write the accuracy per language below.
5. **Local-language templates:** add reviewed Yoruba, Hausa and Igbo confirmation messages in `language.py`
   (they fall back to English until then).
6. **Parsing strategy:** compare direct local-language parsing vs translate-to-English-first, in `intent_parser.py`.
7. **Receipts:** try Tesseract on real phone photos of your demo invoice (`OCR_BACKEND=tesseract`); add
   pre-processing or switch OCR if accuracy is poor.
8. **Agree the snapshot endpoint** with the backend engineer (`GET /ai/snapshot`, see `backend_client.py`).
9. **Tune thresholds** in `forecasting.py` and `insights.py` against the demo dataset.

## Evaluation results

| Language | ASR WER | Intent accuracy | Notes |
| --- | --- | --- | --- |
| English | | | |
| Yoruba | | | |
| Hausa | | | |
| Igbo | | | |

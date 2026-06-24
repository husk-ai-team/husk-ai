# Husk AI — Tutte le caratteristiche

> Documento di riferimento completo: cos'è Husk, cosa fa **oggi** (feature spedite),
> com'è fatto dentro, e cosa c'è **nella vision / roadmap** (feature future).
> Aggiornato alla versione **v0.4.0**.

---

## 1. Cos'è Husk (vision e posizionamento)

**Husk è il debugger visuale per agenti AI** — *"il Chrome DevTools degli agenti AI"*.

L'idea centrale, lo slogan del prodotto:

> **"Finally, see what your AI is thinking."**
> Cattura ogni passo, riavvolgi qualsiasi decisione, e fai il replay da qualsiasi
> checkpoint con uno stato diverso.

Husk esegue i tuoi agenti AI dentro (o accanto a) uno **Studio locale** e ti mostra
in tempo reale:
- **cosa pensano** (prompt, completamenti, ragionamento passo-passo),
- **dove falliscono** (nodo esatto, eccezione, stack trace),
- **come cambia il comportamento** se cambi un input (modify-and-replay).

Cattura le tracce **OpenTelemetry** dei tuoi agenti e le trasforma in **un'unica
timeline navigabile**, al posto di un muro di log.

### Principi fondanti (la vision di fondo)

| Principio | Cosa significa |
|---|---|
| **Local-first** | Il backend gira sulla tua macchina. I dati dell'agente non la lasciano mai. |
| **No cloud, no signup, no telemetry** | Nessun account, nessun invio di dati, nessuna telemetria. |
| **Husk Cloud è opzionale, mai obbligatorio** | Esiste come opzione, ma il prodotto core è completo offline. |
| **Categoria di prodotto** | *Visual / time-travel state debugger* (come Replay.io per JS o rr di Mozilla), **non** un proxy gateway tipo Helicone né una dashboard di osservabilità cloud. |
| **Osservabilità non invasiva** | I bridge IDE sono *observability-only*: Husk registra, **non blocca mai** l'IDE o l'agente. |
| **Propose, don't apply** | Il debugger propone fix come diff; non applica nulla senza conferma esplicita. |

### Il problema che risolve (la pain validata)

- 66% degli sviluppatori frustrati dal codice AI "quasi giusto" (Stack Overflow 2025).
- 45% riporta che debuggare codice generato da AI **richiede più tempo**.
- 46,2% fatica a integrare l'osservabilità degli agenti nel proprio workflow.
- Tasso di fallimento reale degli agenti multi-step ben sopra il 20% (MAST, SWE-bench, studi RAG).

---

## 2. Feature attuali (spedite) — panoramica

Le quattro caratteristiche di punta annunciate nel README:

1. **Una timeline per ogni passo.** Chiamate LLM, chiamate a tool ed eventi IDE da
   qualsiasi framework finiscono in un unico activity feed con prompt, completamenti,
   conteggio token e costo — invece di un muro di log.
2. **Time-travel / modify-and-replay.** Entri in qualsiasi checkpoint registrato,
   modifichi lo stato, e crei un branch da quel punto per vedere come reagisce
   l'agente — alimentato dal motore di checkpoint/replay **proprietario di Husk**.
3. **Cattura attività IDE.** Modifiche ai file e segnali di stop da Cursor e VS Code
   confluiscono nella timeline insieme agli span dell'agente. Solo osservabilità —
   Husk non blocca mai l'IDE.
4. **Connessione ai tool di coding AI (MCP).** Husk parla il Model Context Protocol,
   così Claude Code, Cursor, Windsurf e Lovable possono interrogare le run, leggere
   tracce, analizzare i costi e fare replay dei checkpoint da dentro l'assistente.

---

## 3. Cattura e osservabilità (tracing)

- **Ingest OpenTelemetry (OTLP/HTTP)** sulla porta `7654`, endpoint `/v1/traces`.
- **Standard GenAI v1.36**: nomi standard per prompt, completamenti, conteggio token, ecc.
- **Una timeline unificata** per run: ogni span (chiamata LLM, chiamata a tool,
  decisione dell'agente) con prompt, completamento, token in/out e **costo**.
- **Zero-friction capture** — una sola riga per strumentare il tuo agente:
  ```python
  from husk_shared import instrument
  instrument(service_name="my-agent")   # punta OTel a http://localhost:7654
  ```
  Import OTel lazy: nessuna nuova dipendenza hard. `llm_span()` imposta gli attributi GenAI.
- **Ricetta generica senza codice** (variabile d'ambiente):
  ```bash
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:7654 python your_agent.py
  ```
- **Le run appaiono nello Studio entro ~2 secondi.**
- **Overhead di ingest** misurato: scrittura su SQLite locale, nessun hop di rete
  (vs LangSmith ~132 ms di round-trip al cloud).

### Framework supportati oggi

- **LangChain** (integrazione OTel)
- **LangGraph** (tracciato come qualunque altra run; usato anche come plugin di osservabilità)
- **OpenAI Agents SDK**
- **AutoGen** (Microsoft)
- **CrewAI**
- **Plain Python + un client LLM** — basta emettere span OTel manualmente.

### Provider / modelli con tabella costi nota

- **OpenAI**: gpt-4o / gpt-4o-mini / gpt-4.1 / gpt-4.1-mini / gpt-4-turbo / gpt-3.5-turbo / o1 / o1-mini / o3 / o3-mini
- **Anthropic**: claude-3.5-sonnet / 3.5-haiku / 3-opus / 3-haiku / claude-opus-4 / sonnet-4 / haiku-4.5 / opus-4.7
- **Groq / Llama / misc**: llama-3.1-8b-instant, llama-3.3-70b-versatile, llama-3.1-70b, llama3-70b/8b-8192, mixtral-8x7b, gemma2-9b
- **OpenRouter**: openai/gpt-oss-20b & 120b, meta-llama/llama-3.1-8b / 3.3-70b / 3.1-70b-instruct

I metadati modello (`model_metadata.py`) forniscono **context window** e **max output**
per dimensionare il budget di contesto del debugger.

---

## 4. Time-travel: modify-and-replay

Il **primitivo core** del prodotto. Tre modalità di replay, in ordine crescente di determinismo:

### 4.1 Re-invoke (default)
Lo Studio re-importa il modulo-grafo dell'agente (il file registrato nella run) e lo
riesegue con lo stato modificato. Esegue codice reale e — se non si usa una cassette —
fa chiamate LLM/tool reali.

### 4.2 Node-skip (motore Husk)
Quando l'agente gira sul **motore di checkpoint proprietario di Husk**
(`husk_shared.engine`), il replay riprende dallo snapshot preso *prima* del nodo di fork
e riesegue **solo quel nodo e i suoi successori**. Il lavoro a monte viene **saltato**:
non emette span e non spende token. **È il percorso misurato dal benchmark.**

- Esecutore lineare framework-agnostic + store di snapshot SQLite locale, posseduto end-to-end.
- Dopo ogni nodo viene persistito uno snapshot dello stato unito.
- `replay_from` ricarica lo snapshot prima del nodo di fork, applica una patch, e riesegue.

### 4.3 Model-free (cassette)
Con `HUSK_REPLAY_CASSETTE=1`, le risposte HTTP del provider registrate vengono servite
da disco — **deterministico, byte-identico, $0**. Una richiesta *cambiata* fallisce il
match e cade sul provider reale, poi viene registrata.

- Cassette registrate al confine del transport `httpx` (condiviso da SDK OpenAI/Anthropic/Groq).
- Keyed da un hash stabile della richiesta.
- Toggle **Model-free** nella vista replay dello Studio, oppure variabile d'ambiente.

### Replay nello Studio (UX)
- Pulsante **"Modify and replay"** sulla run.
- Editor **Monaco** apre lo stato JSON; modifichi un valore (es. `"topic": "Rome"` → `"Tokyo"`).
- **"Run from here"** su un nodo: nasce una nuova run, l'originale è preservata.
- Il replay è **gated**: le run senza graph module mostrano una spiegazione chiara invece di un errore 400.

### Caveat metodologico
**State replay ≠ output determinism.** Il motore garantisce il ripristino perfetto
dello stato JSON al checkpoint; l'LLM al nodo successivo resta stocastico (a meno di
usare il percorso model-free con cassette).

---

## 5. Branch, lineage e diff

- **Branch first-class** — `/api/v1/branches` crea (idempotente) ed elenca i link
  parent→child di replay, ognuno con `token_bypass_pct`, token e costo risparmiati.
  Il branch è registrato automaticamente quando la run figlia viene ingerita.
- **Diff run-vs-run** — `/api/v1/diff` restituisce un diff reale tra due run.
- **Lineage visibile nello Studio** — una run mostra i suoi replay (e il suo parent,
  se è un figlio) con bypass %, token e costo risparmiati, più un diff parent-vs-replay reale.

---

## 6. Debugger automatico LLM (BYOK — Bring Your Own Key)

Introdotto in v0.3.0. Analizza una run fallita e **propone** una causa + un fix.

- **Provider layer BYOK** (`debugger/providers.py`): astrazione su puro `httpx`
  (nessuna nuova dipendenza SDK), implementazioni **Anthropic** e **OpenAI**, registry
  a una riga per aggiungerne altri. L'utente sceglie provider e modello; la context
  window del modello dimensiona il budget di contesto.
- **Gestione chiave local-first** (`debugger/secrets.py`): la chiave vive **solo** in
  `~/.husk/secrets.json` (chmod 0600 su POSIX), con fallback su `ANTHROPIC_API_KEY` /
  `OPENAI_API_KEY`. Non viene mai loggata, mai scritta in tracce o export.
  `GET /api/debugger/config` ritorna solo `has_key`, mai la chiave. Le chiamate al
  provider vanno dal backend locale direttamente al provider, mai attraverso un server Husk.
- **Context assembler focalizzato sul fallimento** (`debugger/context_assembler.py`):
  costruisce l'input LLM dalla run — topologia, percorso eseguito, stato + diff per nodo,
  chiamate a tool, chiamate al modello (prompt/risposta/token), eccezioni/stack trace,
  segnale di recursion-limit. Le tracce grandi vengono *finestrate*: dettaglio pieno
  attorno al fallimento, regioni lontane riassunte o scartate per stare nella window —
  **la regione del fallimento non viene mai tagliata**.
- **System prompt versionato e spedito** (`debugger/system_prompt.py`): ragionamento
  sintomo-vs-causa, risalita alla prima divergenza, classificazione del fallimento,
  output JSON stretto. Validato con schema Pydantic forbid-extra + estrattore tollerante;
  contenuto di traccia inventato e guessing silenzioso sono vietati.
- **Propose, don't apply.** `POST /api/debugger/runs/{id}/analyze` gira on-demand;
  l'auto-analisi delle run fallite è **opt-in e off di default**. Il fix proposto è
  mostrato come diff; applicarlo (`/apply-fix`) richiede conferma esplicita + toggle
  "allow applying fixes" (off di default), scrive un backup `.husk-bak`, ed è atomico
  (apply pulito o niente). I report persistono nella tabella `debug_reports`.
- **UI**: un pannello BYOK nelle Impostazioni; il report del debugger viene sovrapposto
  ai nodi implicati nella vista grafo.

---

## 7. Visualizzazione node-graph

Introdotta in v0.3.0 — strato dati strutturato + UI.

- **Dati strutturali per nodo.** Il motore (`husk_shared/engine.py`) ha un hook di
  telemetria opzionale (no-op di default); l'agente d'esempio emette uno span
  `graph_node` per nodo, con stato before/after, il diff di stato e (su eccezione)
  lo stack trace, con gli span model/tool del nodo annidati sotto. La topologia del
  grafo è scritta sullo span root. **Il dato esiste nella traccia**, non viene ricostruito.
- **API grafo per nodo** — `GET /api/v1/runs/{id}/graph`: nodi con stato
  (success / error / **skipped** / running), stato + diff per nodo, chiamate model e tool,
  token, timing, punto di fallimento rilevato, archi (incluse conditional edge/label
  quando recuperabili), e il report del debugger collegato.
- **UI node-graph**: vista grafo SVG **senza dipendenze** nella pagina di dettaglio run —
  nodi colorati per stato, punto di fallimento evidenziato, archi con frecce/label,
  pannello di contesto per nodo (input/output, prompt/risposta, errori, diff stato
  before/after), toggle **Timeline/Graph**, e report del debugger sovrapposto ai nodi.
- **Nessun bump del formato di registrazione**: `debug_reports` è una tabella nuova;
  `runs`/`spans`/`branches` non cambiano, quindi `RECORDING_FORMAT_VERSION` resta a 1 e
  DB vecchi/nuovi restano mutuamente leggibili.

---

## 8. Studio (la UI React)

SPA React + Vite servita dal backend su `/`. Pagine: **Dashboard, Onboarding, Runs,
RunDetail, Replay, Settings**.

- **Dashboard**: tile di integrazione (Cursor live), tile **Recent failures**, tile
  **Errors** che fa deep-link alla vista filtrata.
- **Runs**: ricerca run + filtri per stato.
- **RunDetail**: timeline + vista grafo (toggle), inspector degli span, lineage e diff.
- **Replay**: editor Monaco dello stato, toggle Model-free, link diretto alla nuova run
  con il suo bypass una volta registrata.
- **Settings**: pannello BYOK per il debugger.
- **Onboarding**: schermata "Welcome to Husk" → "Try free".
- **Auto-build**: al primo `husk-ai start` il backend costruisce automaticamente il
  bundle Studio (`corepack pnpm --filter studio build`) se manca; disattivabile con
  `HUSK_NO_AUTO_BUILD=1`. Senza Node, serve una landing di fallback.
- **Dev server (HMR)** su `:5174` con proxy `/api` → `:7654`.
- **Test unit** dello Studio con vitest.

---

## 9. Connessione ai tool di coding AI (MCP)

Husk include un **server MCP** (Model Context Protocol), così gli agenti di coding —
**Claude Code, Cursor, Claude Desktop, Windsurf, Lovable** — possono leggere run,
ispezionare tracce, analizzare costi e (opt-in) fare replay senza lasciare l'assistente.

- Gira **localmente su stdio** e legge `~/.husk/traces.db` direttamente: i tool di
  lettura funzionano **anche quando `husk-ai start` non è in esecuzione**.
- **Transport HTTP** (`--transport http`, bind `127.0.0.1:7655`, endpoint `/mcp`) per
  client remoti/cloud come Lovable, via tunnel.
- **Auto-config del client**: `husk-ai mcp install --client <claude-code|cursor|claude-desktop|windsurf|lovable>`
  scrive (o stampa) la config e risolve il path assoluto del binario.

**Tool MCP esposti** (lettura): `list_runs`, `get_run`, `get_trace`, `get_span`,
`list_errors`, `cost_breakdown`, `dashboard_summary`, `list_cursor_events`.

**Replay via MCP — off di default.** `replay_run` riesegue il tuo codice, quindi è
gated dietro un flag esplicito (`--enable-replay` / `HUSK_MCP_ENABLE_REPLAY=1`),
inteso solo per uso locale. Tenere **disabilitato** su qualsiasi server HTTP/tunnel.

---

## 10. Integrazioni IDE (bridge di osservabilità)

### Cursor — `husk-cursor-hook` (CLI npm)
- Si iscrive agli hook fire-and-forget di Cursor: **`afterFileEdit`** (ogni file scritto
  dall'agente) e **`stop`** (fine turno dell'agente).
- Scrive `.cursor/hooks.json` nel progetto (`husk-cursor-hook install`); rifiuta di
  sovrascrivere un file esistente.
- Comandi: `install`, `hook`, `ping`. `ping` verifica la raggiungibilità di Husk.
- `dist/cli.js` ~7 KB, **zero dipendenze runtime** (usa il fetch nativo di Node).
- Variabile `HUSK_URL` per puntare a una porta diversa.
- **Observability-only**: non blocca mai l'agente Cursor.

### VS Code / Antigravity — `husk-vscode-hook` (estensione)
- Per **VS Code**, **Antigravity** (fork VS Code di Google) e IDE compatibili.
- Streamma **ogni comando da terminale** lanciato dall'agente AI (Copilot, Continue,
  Cline, Roo, agente nativo di Antigravity) nello Studio, con argomenti e cwd.
- Tagga gli eventi per IDE (vscode / cursor / antigravity).
- Status bar `● Husk` quando vede il backend locale.
- Comandi: `Husk: Open Studio`, `Husk: Reconnect`, `Husk: Toggle Terminal Capture`.
- Settings: `husk.url`, `husk.captureTerminal`.
- **Observability-only**, non blocca l'IDE.

---

## 11. CLI `husk-ai`

| Comando | Cosa fa |
|---|---|
| `husk-ai start` | Avvia il server (porta 7654 default) e apre lo Studio. Auto-build del bundle al primo run. `--port`, `--no-open-browser`. |
| `husk-ai run <command…>` | Esegue il tuo agente e lo cattura in un passo: assicura il backend up, imposta `$OTEL_EXPORTER_OTLP_ENDPOINT`, stampa la run URL. `--no-serve` per CI. |
| `husk-ai demo` | Semina 1 evento IDE + una traccia OTel a 3 span con attributi GenAI v1.36. |
| `husk-ai list` | Elenca le run recenti (id, framework, span count, costo). |
| `husk-ai replay <run_id>` | Replay con stato modificato da terminale/CI. `--set key=value`, `--span <id>` (fork da nodo), `--cassette` (LLM da cassette, $0). |
| `husk-ai export <run_id>` | Esporta una run (run + span + branch, già redatti) in un bundle JSON portabile. `--out FILE`. |
| `husk-ai doctor` | Diagnostica: versione, home `~/.husk/`, path DB, health check. |
| `husk-ai clean` | Pulisce il database locale (run, tracce, auth). Non tocca il repo né il `.venv`. |
| `husk-ai mcp` | Avvia il server MCP. `--transport http`, `--enable-replay`. |
| `husk-ai mcp install --client <name>` | Scrive/stampa la config MCP per connettere un client. |

> L'alias legacy `husk` continua a funzionare nel workspace.

---

## 12. Sicurezza e privacy

- **Tool locale, loopback-only.** Il backend fa bind su `127.0.0.1`; le route che
  cambiano stato (replay, ingest OTel, debugger) **rifiutano peer non-loopback** e
  richieste cross-origin dal browser — così una pagina web visitata non può pilotarle.
- **Guardia condivisa loopback + Origin** (`api/_guard.py`) sui router replay /
  ingest-OTel / debugger.
- **Replay RCE chiuso** (v0.4.0): prima `/api/replay` importava ed eseguiva un path di
  graph-module preso dai dati salvati senza auth. Ora c'è un **allowlist di graph_module**
  (`replay/graph_replay.py`): solo file sotto la tua directory di progetto (o
  `$HUSK_ALLOWED_GRAPH_DIRS`) possono essere importati.
- **Hardening at-rest**: `~/.husk` creato `0700`, `traces.db` `0600`.
- **Redazione segreti in ingest**: scrubbing di chiavi/token comuni (provider key,
  bearer token) da prompt/completamenti/tool I/O prima del salvataggio.
  Disattivabile con `HUSK_NO_REDACT=1`.
- **BYOK = unico punto in cui i dati lasciano la macchina.** Quando lanci il debugger,
  il contesto della run (prompt, completamenti, sorgente dell'agente) va al provider LLM
  che hai configurato. La chiave è locale (`~/.husk/secrets.json`) e mai inviata a un server Husk.
- **Vulnerabilità da segnalare privatamente** (vedi `SECURITY.md`), non via issue pubblica.

### Dove vivono i dati (`~/.husk/`)
- `traces.db` — run e span (prompt, completamenti, tool I/O) come JSON in chiaro.
- `cassettes/` — risposte HTTP registrate per il replay model-free.
- `secrets.json` — chiave BYOK del debugger.
- `auth.json`, `runs/` — stato auth e run.

---

## 13. Formato di registrazione e affidabilità

- **Registrazioni versionate** (`husk_shared.recording`): ogni DB è stampato con
  `RECORDING_FORMAT_VERSION` in `PRAGMA user_version`. All'apertura il backend **rifiuta**
  un DB scritto da una Husk più nuova (`RecordingFormatError`) ed esegue una catena di
  migrazioni per uno più vecchio — invece di leggerlo male in silenzio.
- **Tipi stretti**: `mypy --strict` gira e passa sulla superficie pubblica (no `dict`/`Any` nudi).
- **Determinismo testato**: test che vanno in rosso al drift; una resume riesegue
  *esattamente* il nodo di fork + successori, zero varianza tra ripetizioni.
- **Cassette byte-identiche**: l'SDK OpenAI reale guidato attraverso una cassette tocca
  **zero** rete ed è byte-identico in replay.

---

## 14. Benchmark — i numeri (e come riprodurli)

Case study **completamente riproducibile**: ~500 invocazioni di un agente "Research
Synthesizer" a 5 nodi (`query_expansion → retrieve → analyze → synthesize → cite_check`)
sul motore di Husk, con **chiamate LLM reali** e query reali da **TriviaQA**
(OpenRouter Llama-3.3-70B + 3.1-8B, 500 parent / 118 replay, seed 42).

| Metrica | Valore (95% CI) |
|---|---|
| **Token bypass medio** | **42,1%** [35,7, 48,8] (token-weighted 55,0%) |
| **Speed-up wall-time del replay** | **mediana 6,9×** (right-skewed; media 47,9×) |
| **Successo replay** | **100%** (118/118), Wilson [96,9, 100] |
| **Max bypass singolo replay** | **90,7%** |
| Costo list-price dei token registrati | ≈ $0,58 (spesa reale ≈ $0,6) |

**Riproduzione offline, senza API key, senza rete:**
```bash
uv run python benchmark/reproduce.py
```
Ricostruisce un DB SQLite da `benchmark/fixtures/canonical_run/` e **asserisce** che i
numeri combacino con `benchmark/hero_metrics.json`. Ogni hero number è regenerabile offline.

Ogni metrica porta un **Bootstrap BCa 95% CI** in puro Python (`benchmark/bootstrap.py`,
auto-validato contro Efron-Tibshirani 1993); il successo replay usa un intervallo Wilson.

---

## 15. Architettura / layout del repo

```
husk/
├── apps/
│   └── studio/                 UI di prodotto (build + servita dal backend su /)
│       └── client/src/         React/TS: pages, components (graph, debugger, inspector, timeline, ui), hooks, lib
├── packages/
│   ├── husk-cli/               CLI `husk-ai`: start · run · demo · list · replay · export · doctor · clean · mcp
│   ├── husk-shared/            schemi Pydantic + tabella costi + engine + recording + state_diff + tracing + model_metadata
│   ├── husk-studio-backend/    backend FastAPI su :7654 — ingest OTel, replay engine, debugger, serve lo Studio
│   └── husk-sandbox/           cassette HTTP + provider (openai/anthropic) per il replay model-free
├── packages-npm/
│   ├── husk-cursor-hook/       bridge Cursor SDK Hooks (CLI npm)
│   └── husk-vscode-hook/       estensione VS Code / Antigravity
├── benchmark/                  harness riproducibile + fixture canonica + reproduce.py
└── examples/                   husk_thread.py · langchain_agent.py · otel-autogen.py
```

### Superficie API del backend (FastAPI, `:7654`)
- `otel.py` — ingest OTLP/HTTP (`/v1/traces`)
- `runs.py`, `spans.py`, `dashboard.py` — lettura run/span/dashboard
- `graph.py` — `GET /api/v1/runs/{id}/graph`
- `replay.py` — `/api/replay` (gated, allowlist graph_module)
- `branches.py` — `/api/v1/branches` (lineage)
- `diff.py` — `/api/v1/diff`
- `debugger.py` — analyze / apply-fix / config (BYOK)
- `cursor.py`, `integrations.py` — eventi IDE e tile di integrazione
- `auth.py`, `_guard.py` — auth e guardia loopback+Origin

### Requisiti
- **Python 3.11+** (usa `StrEnum`; pinnato via `.python-version`, fetchato da `uv`).
- **Node.js 20+** con `corepack` — solo per buildare la UI la prima volta; API e CLI girano senza.
- **uv 0.4+**, **git 2.x+**.
- **API key LLM opzionale** — solo il debugger BYOK ne usa una, e resta sulla macchina.
- OS: Windows 10/11 (PowerShell), macOS 12+, Linux (Ubuntu 22.04+/Fedora 38+/WSL2).

---

## 16. Licenza e modello di rilascio

- **Source-available** sotto **Business Source License 1.1 (BUSL 1.1)**; converte a una
  licenza open-source dopo la change date.
- **Husk Cloud è opzionale, mai richiesto.**
- Rilasci via tag `vX.Y.Z` (GitHub Release).

---

## 17. Storico versioni (highlight)

- **v0.4.0 — Security hardening, dead-code removal, terminal/CI workflow**
  Replay RCE chiuso (guardia + allowlist), hardening at-rest + redazione ingest,
  rimozione riferimenti `husk.dev`. `instrument()` one-line, `husk run`/`replay`/`export`
  in shell e CI. Studio: ricerca + filtri stato, tile Recent failures, replay gated.
  Pulizia: rimosso il vecchio path sandbox `husk run` (~8k LOC), 50 componenti + 35
  dipendenze frontend inutilizzate. 110 test passano.
- **v0.3.0 — Debugger automatico LLM (BYOK) + node-graph**
  Provider layer BYOK su httpx (Anthropic/OpenAI), chiave local-first, context assembler
  failure-focused, system prompt versionato, propose-don't-apply. API grafo per nodo + UI
  SVG senza dipendenze. 94 test.
- **v0.2.0 — Motore di replay proprietario di Husk**
  Engine checkpoint/replay framework-agnostic (`husk_shared.engine`), core de-LangGraphed
  (`/api/replay`, telemetria `husk.*`), benchmark ri-misurato sul motore Husk (42,07%).
  LangChain/LangGraph restano come integrazioni di osservabilità.
- **v0.1.0 — Hardening pass**
  Hero number riproducibili offline (fixture committata), test di determinismo, cassette
  HTTP model-free, registrazioni versionate, branch/diff first-class, mypy strict, CI completa.

---

## 18. Vision / Roadmap (feature future, non ancora spedite)

Elementi esplicitamente marcati come *roadmap / non ancora disponibili* nella documentazione:

| Feature | Stato | Dove |
|---|---|---|
| **Pubblicazione npm di `husk-cursor-hook`** | ⏳ roadmap (oggi: install da sorgente; `npm i -g husk-cursor-hook` dà 404) | README, packages-npm/husk-cursor-hook/README |
| **Pubblicazione PyPI / `pip install husk-ai`** | ⏳ roadmap (oggi: install da clone sorgente) | packages/husk-cli/README |
| **Estensione VS Code: raggruppare comandi per run / agent thread** | ⏳ roadmap | packages-npm/husk-vscode-hook/README |
| **Husk Cloud** | opzionale, esiste come opzione futura non obbligatoria | README / LICENSE |
| **Replay PyPI release del cursor hook** | ⏳ roadmap | packages-npm/husk-cursor-hook/README |

### Direzione di prodotto (vision dichiarata, dal benchmark e dal posizionamento)

- **Restare nella categoria "visual / time-travel state debugger"** — il precedente
  tecnologico è **Replay.io** (record/replay per JS, Serie B da $43M) e **rr** di Mozilla:
  stesso primitivo (time-travel a livello di stato), ecosistema di linguaggio diverso.
- **Scope MVP esplicito**: i grafi sequenziali/diretti (catene RAG, agenti multi-step)
  sono il punto di forza. I **sistemi multi-agente truly-async** con race condition di
  messaggistica sono **fuori scope per l'MVP** — implicitamente sulla traiettoria futura.
- **Output determinism completo** (oltre allo state replay) è già disponibile via percorso
  model-free (cassette + provider mocking); l'estensione naturale è renderlo il default
  per più framework.
- **Più provider nel debugger BYOK**: il registry a una riga è progettato per aggiungerne
  altri oltre Anthropic e OpenAI.

---

### Riferimenti nel repo
- `README.md` — overview, feature, getting started, CLI, MCP, sicurezza
- `CHANGELOG.md` — storico v0.1.0 → v0.4.0
- `benchmark/README.md`, `benchmark/HERO_METRICS.md`, `benchmark/COST_MATRIX.md` — numeri e metodologia
- `SECURITY.md`, `LICENSE`, `CONTRIBUTING.md`
- `packages-npm/husk-cursor-hook/README.md`, `packages-npm/husk-vscode-hook/README.md` — bridge IDE

# LexMind — Agent Visualization, Datasets & Query Guide

> A complete reference for understanding how the 5 specialist agents work,
> what data to feed them, what queries to ask, and where the platform goes next.

---

## 1. How the 5 Agents Work — Full Visualization

Every user query travels through the following pipeline before a response is returned.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          USER QUERY (via UI or API)                         │
│   "Analyze the indemnification clause for risks in my SaaS agreement"       │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 1 — Intent Classification Node                      │
│                                                                             │
│  GPT-4o (temp=0) reads the query and outputs:                               │
│    • intent: "contract_review"                                              │
│    • sub_tasks: ["identify indemnification clause", "assess risk level",    │
│                  "check governing law", "flag missing clauses"]             │
│    • confidence: 0.97                                                       │
│                                                                             │
│  Possible intents:                                                          │
│    contract_review | case_research | compliance_check |                     │
│    drafting | litigation_risk                                               │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
              ┌──────────────────▼──────────────────┐
              │    STEP 2 — Conditional Router       │
              │                                     │
              │  Intent → Agent(s) mapping:         │
              │  contract_review  → [contract_analyst]           │
              │  case_research    → [case_researcher]            │
              │  compliance_check → [compliance_monitor]         │
              │  drafting         → [legal_drafter +             │
              │                      contract_analyst]           │
              │  litigation_risk  → [litigation_risk +           │
              │                      case_researcher]            │
              └──────────────────┬──────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
┌───────────────┐      ┌─────────────────┐     ┌─────────────────────┐
│  AGENT A      │      │  AGENT B        │     │  AGENT C            │
│  Contract     │      │  Case           │     │  Compliance         │
│  Analyst      │      │  Researcher     │     │  Monitor            │
│               │      │                 │     │                     │
│  • Retrieves  │      │  • Retrieves    │     │  • Retrieves matter │
│    contract   │      │    case law +   │     │    context from     │
│    clauses    │      │    precedents   │     │    vector DB        │
│    from Qdrant│      │  • Reranks via  │     │  • Fetches LIVE     │
│  • Identifies │      │    FlashRank    │     │    regulatory docs  │
│    risk levels│      │  • Structures   │     │    from Federal     │
│    per clause │      │    findings +   │     │    Register API +   │
│  • Flags      │      │    citations    │     │    SEC EDGAR        │
│    missing    │      │                 │     │  • AI relevance     │
│    clauses    │      │                 │     │    classifier       │
│  • Runs guard │      │  • Runs guard   │     │  • Runs guard       │
└───────┬───────┘      └────────┬────────┘     └──────────┬──────────┘
        │                       │                         │
        ▼                       ▼                         ▼
┌───────────────┐      ┌─────────────────┐     ┌─────────────────────┐
│  AGENT D      │      │  AGENT E        │     │                     │
│  Legal        │      │  Litigation     │     │   (Runs in parallel │
│  Drafter      │      │  Risk           │     │    when routed)     │
│               │      │                 │     │                     │
│  • Takes      │      │  • Pulls from   │     │                     │
│    sub-tasks  │      │    BOTH matter  │     │                     │
│    + context  │      │    corpus AND   │     │                     │
│  • Generates  │      │    global       │     │                     │
│    clause     │      │    caselaw      │     │                     │
│    drafts     │      │    collection   │     │                     │
│  • Returns    │      │  • Outputs win  │     │                     │
│    versioned  │      │    probability  │     │                     │
│    draft text │      │    + settlement │     │                     │
│               │      │    range        │     │                     │
└───────┬───────┘      └────────┬────────┘     └─────────────────────┘
        └───────────────────────┴─────────────────────┐
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     STEP 3 — Synthesis Node                                 │
│                                                                             │
│  Senior analyst LLM (GPT-4o, temp=0.1) receives:                           │
│    • All agent_outputs (merged JSON from every agent that ran)              │
│    • Top 10 reranked retrieved chunks from the vector DB                    │
│    • Original user query                                                    │
│                                                                             │
│  Produces:                                                                  │
│    • Structured markdown response with headers and citations                │
│    • Actionable recommendations                                             │
│    • Source chunk references (by chunk_id)                                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  STEP 4 — Mandatory Hallucination Guard                     │
│                                                                             │
│  GPT-4o (temp=0) evaluates the synthesis output against source chunks       │
│    confidence ≥ 0.70  →  PASS  →  Output delivered to user                 │
│    confidence < 0.70  →  FAIL  →  Routed to Human Review Queue             │
│                                                                             │
│  Attorney actions in Review Queue:                                          │
│    ✅ Approve  →  Stored as complete, delivered to user                     │
│    ✏️ Correct  →  Correction re-ingested as high-weight chunk              │
│    ❌ Reject   →  Session flagged, query may be rerun                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agent Output Structure (what each agent returns)

| Agent | Output Schema |
|---|---|
| **Contract Analyst** | `clauses[]` with `risk_level`, `risk_explanation`, `recommended_action`, `missing_standard_clauses`, `overall_risk` |
| **Case Researcher** | `cases[]` with `citation`, `holding`, `relevance_score`, `distinguishing_factors`, `legal_principles[]` |
| **Compliance Monitor** | `alerts[]` with `regulation_title`, `delta_summary`, `severity`, `effective_date`, `action_required` |
| **Legal Drafter** | `draft_clauses[]` with `clause_type`, `draft_text`, `rationale`, `alternatives[]` |
| **Litigation Risk** | `win_probability`, `confidence_interval`, `key_factors[]`, `analogous_cases[]`, `settlement_range` |

---

## 2. Where to Fetch Datasets

The platform is designed to ingest **real legal documents**. Here are the best free and paid sources:

### 🆓 Free Datasets (Recommended for Testing)

#### Contracts & Agreements
| Source | URL | What You Get |
|---|---|---|
| **SEC EDGAR** | https://www.sec.gov/cgi-bin/browse-edgar | Public company contracts filed as exhibits (10-K, 10-Q, 8-K filings) — thousands of real NDAs, SaaS agreements, employment contracts, M&A agreements |
| **EDGAR Full-Text Search** | https://efts.sec.gov/LATEST/search-index | Searchable full-text of all SEC filings |
| **EDGAR Sample (already in /dataset)** | `/dataset/*.pdf` | Two real SEC exhibit PDFs already ship with the repo |
| **Contract Understanding Atticus Dataset (CUAD)** | https://huggingface.co/datasets/cuad | 510 commercial contracts with 13,000+ expert-labeled clauses — **perfect for testing Contract Analyst** |
| **MultiLegalPile** | https://huggingface.co/datasets/joelniklaus/multi_legal_pile | Multi-jurisdictional legal texts |

#### Case Law & Precedents
| Source | URL | What You Get |
|---|---|---|
| **CourtListener** | https://www.courtlistener.com/api/ | Free API — millions of US court opinions (SCOTUS, Circuit, District courts) |
| **Harvard Caselaw Access Project** | https://case.law | 6.5 million cases bulk download (requires free account) |
| **Supreme Court Oral Arguments** | https://huggingface.co/datasets/HuggingFaceFW/fineweb | SCOTUS transcripts and opinions |
| **Free Law Project Bulk Data** | https://free.law/projects/recap | PACER court documents |

#### Regulations & Compliance
| Source | URL | What You Get |
|---|---|---|
| **Federal Register API** | https://www.federalregister.gov/api/v1/ | Already integrated! Live regulatory updates fetched automatically |
| **Code of Federal Regulations** | https://www.ecfr.gov/api/ | Full CFR in JSON — great for seeding the compliance corpus |
| **SEC Guidance** | https://www.sec.gov/rules/final.shtml | Final rules and interpretive releases |

### 💰 Premium / Paid Sources (Production)
- **Westlaw** / **LexisNexis** — Full case law database (law firm standard)
- **Bloomberg Law** — Regulatory tracking + dockets
- **Practical Law** — Standard form contracts and practice notes

### 📁 How to Ingest Documents into LexMind

```bash
# 1. Get a JWT token first
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"email":"attorney@yourfirm.com","password":"yourpassword"}' \
  | jq -r '.data.access_token')

# 2. Create a matter (one matter = one case/project)
MATTER_ID=$(curl -s -X POST http://localhost:8000/api/matters \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"SaaS Contract Review","matter_type":"contract","jurisdiction":"Delaware"}' \
  | jq -r '.data.id')

# 3. Upload any PDF — the pipeline handles chunking, embedding, and Qdrant ingestion
curl -X POST http://localhost:8000/api/matters/$MATTER_ID/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your/contract.pdf"

# 4. Upload the two sample PDFs already in the /dataset folder
curl -X POST http://localhost:8000/api/matters/$MATTER_ID/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$(pwd)/../dataset/Flora Growth Corp._ Exhibit 10.1 - Filed by newsfilecorp.com.pdf"

curl -X POST http://localhost:8000/api/matters/$MATTER_ID/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@$(pwd)/../dataset/sec.gov_Archives_edgar_data_1726711_000121390021059330_f10q0921ex10-10_aditxtinc.htm.pdf"

# 5. Check ingestion status
curl http://localhost:8000/api/matters/$MATTER_ID/documents \
  -H "Authorization: Bearer $TOKEN" | jq '.data[].ingestion_status'
```

---

## 3. Query Cheat Sheet — By Agent

### 🔵 Contract Analyst
*Triggered when: your query mentions contracts, clauses, terms, agreements, risks in documents*

```
# Risk Analysis
"Analyze the indemnification clause for risks in this agreement."
"What are the most dangerous clauses in this SaaS contract?"
"Is the limitation of liability clause enforceable under Delaware law?"
"Flag any one-sided or unusual clauses compared to market standard."
"Does this agreement have adequate IP ownership provisions?"

# Clause-Specific
"Summarize the termination provisions and what triggers automatic termination."
"What are the payment terms and what penalties apply for late payment?"
"Identify all representations and warranties made by each party."
"Does this contract include a non-compete clause? Is it enforceable?"
"What data privacy obligations does the vendor have under this agreement?"

# Missing Clauses
"What standard clauses are missing from this contract?"
"Does this agreement lack a dispute resolution mechanism?"
"Is there a force majeure clause? Does it cover pandemics?"

# Multi-document
"Compare the indemnification clauses across all uploaded contracts."
"Which of my contracts has the most aggressive auto-renewal terms?"
```

### 🟢 Case Researcher
*Triggered when: your query involves case law, legal precedents, court decisions, legal standards*

```
# Precedent Research
"Find precedents for breach of fiduciary duty in Delaware corporations."
"What is the legal standard for tortious interference with contract?"
"Has any court upheld a non-compete clause exceeding 2 years in California?"
"Find cases where SaaS limitation of liability clauses were struck down."
"What is the current circuit split on personal jurisdiction for online businesses?"

# Jurisdiction-Specific
"What is the majority rule for implied covenant of good faith in New York?"
"Find SDNY cases on securities fraud materiality from 2020 onwards."
"How do Texas courts treat arbitration clauses in employment contracts?"

# Standard of Review
"What is the business judgment rule and when does it apply?"
"Find cases applying the entire fairness standard in Delaware M&A."
```

### 🟠 Compliance Monitor
*Triggered when: your query involves regulations, compliance, regulatory changes, legal requirements*

```
# Real-Time Regulatory Monitoring
"Are there any new SEC regulations affecting our fintech client's data practices?"
"What recent CFPB changes affect our mortgage lending clients?"
"Has OSHA issued any new guidance on workplace safety in the last 90 days?"
"What new privacy regulations affect companies doing business in California?"
"Check for recent FTC rule changes on non-compete agreements."

# Practice Area Monitoring
"Monitor for new employment law changes in New York and California."
"What AML/BSA regulatory updates affect our banking clients?"
"Are there new FDA guidance documents affecting our pharma client?"
"Check for HIPAA enforcement actions and new guidance this quarter."

# Client-Specific Compliance
"What regulations should our healthcare SaaS client be aware of?"
"Does this contract comply with current GDPR requirements?"
"What are the new ESG disclosure requirements from the SEC?"
```

### 🟣 Legal Drafter
*Triggered when: your query asks to write, draft, revise, generate, or create legal text*

```
# Drafting New Clauses
"Draft a balanced indemnification clause for a SaaS vendor agreement."
"Write a limitation of liability clause that caps damages at 12 months of fees."
"Generate a data processing agreement (DPA) compliant with GDPR and CCPA."
"Draft a non-solicitation clause for a senior employee in New York."
"Write a force majeure clause that explicitly covers supply chain disruptions."

# Revising Existing Text
"Redline this indemnification clause to make it more balanced."
"Suggest improvements to the dispute resolution section in my uploaded contract."
"Rewrite the termination clause to give our client more flexibility."

# Standard Documents
"Draft a mutual NDA for a software partnership."
"Create a consulting services agreement with a clear IP assignment clause."
"Write a master services agreement template for a B2B SaaS company."
```

### 🔴 Litigation Risk
*Triggered when: your query involves litigation probability, trial strategy, case outcome prediction, settlement*

```
# Risk Assessment
"What is the probability of success if we pursue breach of contract litigation?"
"Assess the litigation risk of our trade secret misappropriation claim."
"What is our exposure if the plaintiff's negligence claim succeeds?"
"Evaluate the strength of our summary judgment motion on contract interpretation."

# Settlement Strategy
"What is a reasonable settlement range for a $5M breach of contract claim?"
"Should we settle or litigate? What do analogous cases suggest?"
"What factors most affect outcome prediction in our employment discrimination case?"

# Precedent Analysis
"Find cases where defendants successfully argued implied license in IP disputes."
"What is the typical damages award in wage and hour class actions in California?"
"How have courts ruled on consequential damages waivers in software contracts?"
```

### ⚡ Multi-Agent Queries (Litigation Risk + Case Research together)
```
"Analyze our breach of contract claim, identify relevant precedents,
 and assess our win probability before the December 1 deadline."

"Review this employment agreement for risks, then assess our litigation
 exposure if we terminate for cause under these terms."
```

---

## 4. Suggested New Features to Add

### 🚀 Tier 1 — High Impact, Feasible Now

#### A. Document Comparison Engine (Red-Line Diff)
- **What:** Upload two versions of a contract. The system automatically highlights additions, deletions, and material changes with AI-powered risk commentary on each delta.
- **Value:** Paralegals spend hours doing this manually. Automates a core task.
- **Tech:** Diff algorithm (difflib/Myers) + Contract Analyst on changed clauses only.

#### B. Clause Library / Playbook Builder
- **What:** A curated searchable library of pre-approved clause language. Attorneys can save "approved" versions of clauses (e.g., "Firm-Standard Indemnification"). When reviewing contracts, LexMind flags when a clause deviates from the playbook.
- **Value:** Enforces negotiation standards across all attorneys at the firm.
- **Tech:** Separate Qdrant collection `firm_playbook` with access control.

#### C. Timeline & Deadline Extractor
- **What:** Automatically parse all dates and deadlines from uploaded contracts (renewal dates, notice periods, payment due dates, termination windows) and export them to a calendar or send proactive alerts.
- **Value:** Missed deadlines are malpractice. This is a direct risk-reduction tool.
- **Tech:** GPT-4o date extraction → CalDAV / Google Calendar API integration.

#### D. Matter Cost Estimator
- **What:** Based on matter type, jurisdiction, document complexity, and query history, give the attorney an estimated billable hours forecast.
- **Value:** Helps attorneys scope engagements and provide fee estimates to clients.
- **Tech:** Train a simple regression model on matter metadata + historical session data.

---

### 🔬 Tier 2 — Advanced Capabilities

#### E. Multi-Jurisdiction Compliance Checker
- **What:** Given a contract, automatically check it against the specific laws of every jurisdiction named in it (e.g., a vendor in Texas, client in New York, governed by Delaware). Show a heat-map of jurisdiction-specific risk.
- **Value:** Critical for multi-state and international deals.

#### F. Deposition Preparation Assistant
- **What:** Given a case file and a list of witnesses, generate a structured deposition outline with suggested questions, anticipated objections, and relevant document exhibits.
- **Value:** Litigators spend days building deposition outlines. This compresses it to hours.
- **Tech:** New `deposition_prep` agent in LangGraph + Litigation Risk + Case Research agents working together.

#### G. Client-Facing Summary Generator
- **What:** Generate a plain-English, non-legalese summary of any document or analysis — specifically formatted for the end client (not the attorney). "What does this contract mean for me?"
- **Value:** Eliminates the "translation" work attorneys do when explaining complex terms to clients.

#### H. Precedent Graph Visualization
- **What:** Using the Neo4j graph database (already running), visualize relationships between cases — "Case A overruled Case B," "Case C distinguished Case A," "All cases citing statute X."
- **Value:** Gives litigators a visual map of the case law landscape, instantly revealing the strongest and weakest precedents.
- **Tech:** Neo4j is already integrated in the stack; this adds a D3.js/Nivo graph component to the frontend.

#### I. AI Contract Negotiation Simulator
- **What:** Given a draft contract, simulate a negotiation. The user plays the role of one party; LexMind plays the opposing counsel, proposes counter-clauses, and explains the legal rationale for each counter-proposal.
- **Value:** Helps junior associates practice negotiation in a safe, AI-driven environment.

---

### 🌐 Tier 3 — Enterprise & Scale

#### J. Multi-Firm White-Label Mode
- **What:** Allow LexMind to be deployed as a white-labeled product for multiple law firms, with full data isolation between firms (Qdrant collection isolation is already built in).
- **Value:** Enables LexMind to be sold as a SaaS product.

#### K. Billing & Time-Tracking Integration
- **What:** Auto-generate time entry descriptions from query logs. Integrate with Clio, MyCase, or PracticePanther to push time entries.
- **Value:** Attorneys waste 10-15% of time on administrative billing tasks. This eliminates it.

#### L. Adversarial Red-Team Mode
- **What:** After the Contract Analyst finds risks from the client's perspective, run a second "adversarial" agent that argues the opposing counsel's position — revealing how the other side would exploit every flagged clause.
- **Value:** Gives attorneys a 360° view before entering negotiations.

---

## 5. Quick Reference — API Endpoints

```bash
# Auth
POST   /api/auth/register        # Create new user account
POST   /api/auth/token           # Get JWT

# Matters
GET    /api/matters              # List all matters
POST   /api/matters              # Create a new matter
GET    /api/matters/:id          # Get matter details

# Documents
POST   /api/matters/:id/documents   # Upload a PDF (triggers background ingestion)
GET    /api/matters/:id/documents   # List documents + ingestion status

# Queries (Agent Pipeline)
POST   /api/queries              # Submit a query → returns session_id immediately
GET    /api/queries/:session_id  # Poll for final result
WS     /api/queries/:session_id/stream  # Stream real-time agent progress

# Review Queue
GET    /api/review               # List sessions pending human review
POST   /api/review/:session_id/approve  # Attorney approval
POST   /api/review/:session_id/correct  # Submit correction (re-ingested as training data)

# Compliance
GET    /api/alerts               # List all compliance alerts
```

---

*Generated from LexMind source code — backend/agents/, backend/rag/, backend/api/*

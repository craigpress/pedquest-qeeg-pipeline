---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/design
---

# Data Flow Figures

These figures are intended for review docs, protocols, and publication supplements. Keep them synchronized with `ARCHITECTURE.md` and `STATISTICAL_METHODS_AND_AUDIT.md`.

## System Workflow

```mermaid
flowchart LR
    subgraph Inputs
        EEG["Real EEG recording"]
        MMX["MMX XML reference"]
        CSV["Persyst Trends CSV"]
        CLIN["Clinical metadata"]
        CORR["EEG correction CSV"]
    end

    subgraph Backend
        PARSE["Parse CSV"]
        SCHEMA["Resolve I-code schema"]
        ALIGN["ROSC/date alignment"]
        MERGE["Semantic segment merge"]
        FILTER["Artifact and seizure masks"]
        FEATURES["Derived qEEG features"]
        BINS["Time-bin summaries"]
        CACHE["Parquet cache"]
        EXPORT["Research exports"]
    end

    subgraph Review
        UI["Workbench"]
        AUDIT["Audit bundle"]
        STATS["R/Python/Stata analysis"]
    end

    EEG -->|"processed by Persyst using MMX"| CSV
    MMX -->|"defines panels/trends/statistics"| CSV
    CSV --> PARSE
    MMX --> SCHEMA
    PARSE --> SCHEMA
    CLIN --> ALIGN
    CORR --> ALIGN
    SCHEMA --> MERGE
    ALIGN --> MERGE
    MERGE --> FILTER
    FILTER --> FEATURES
    FEATURES --> BINS
    FEATURES --> CACHE
    BINS --> CACHE
    CACHE --> UI
    CACHE --> EXPORT
    EXPORT --> AUDIT
    EXPORT --> STATS
```

## Multi-Segment Patient Flow

```mermaid
flowchart TD
    A["Segment CSV 1"] --> B["Parse segment 1"]
    C["Segment CSV 2..N"] --> D["Parse segment 2..N"]
    E["MMX config reference"] --> F["Per-segment schema"]
    B --> F
    D --> F
    F --> G["Rename raw I-codes to common-name slugs"]
    G --> H["Union timestamp index"]
    H --> I["Rank ordered fill by non-NaN density"]
    I --> J["Merged ParsedExport with semantic columns"]
    J --> K["Single patient pipeline"]
```

> Note: raw CSV I-codes are not portable across panel exports. The MMX-derived schema is the reference for trend identity and statistics whenever an MMX is available.

## Audit Trail

```mermaid
flowchart TD
    A["Raw inputs"] --> B["Full SHA-256 hashes"]
    C["Code commit and dependency lock"] --> D["Run manifest"]
    E["PipelineConfig"] --> D
    F["MMX identity"] --> D
    G["Clinical/correction rows"] --> D
    B --> D
    D --> H["Pipeline outputs"]
    H --> I["Epoch parquet"]
    H --> J["Bin summary"]
    H --> K["Data dictionary"]
    H --> L["Validation report"]
    I --> M["Independent recomputation"]
    J --> M
    M --> N["Tolerance comparison"]
```

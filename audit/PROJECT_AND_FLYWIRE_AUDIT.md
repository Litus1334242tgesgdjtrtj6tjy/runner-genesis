# RUNNER GENESIS Ω — Phase 0 / Phase 1 Audit

Date: 2026-09-24

## A. Project audit

No prior RUNNER GENESIS source repository was present in the supplied files. The supplied archive `flywire_annotations-main.zip` is a FlyWire annotation repository, not the trading bot. Therefore there was no prior bot code that could be safely claimed as implemented/reusable. This delivery creates a new reference implementation without overwriting any unknown prior project.

The supplied master specification requires BACKTEST / REPLAY / LIVE_SHADOW / PAPER compatibility and keeps LIVE trading off by default. The reference implementation follows that rule.

## B. FlyWire data audit

All supplied compressed tables were opened and their CSV schemas inspected. Row counts below refer to parsed data rows where parsed counts were available; for the four very large tables the line count was streamed directly through gzip and schema was parsed separately.

| File | Compressed MB | Rows | Columns / key schema | Missing / duplicates audit | Join keys | Usefulness |
|---|---:|---:|---|---|---|---|
| `connections_princeton.csv.gz` | 65.285 | 5,342,446 | 5: `pre_root_id, post_root_id, neuropil, syn_count, nt_type` | 0 empty fields in full stream; exact full-row duplicate sort not run | pre/post → `root_id` | Primary filtered directed weighted connectivity; production Fly reservoir candidate |
| `connections_princeton_no_threshold.csv.gz` | 262.909 | 22,285,323 | same 5 columns | 0 empty fields in full stream; exact full-row duplicate sort not run | pre/post → `root_id` | Research/full connectivity; much heavier |
| `connections_buhmann_no_threshold.csv.gz` | 202.269 | 16,847,997 | same 5 columns | 0 empty fields in full stream; exact full-row duplicate sort not run | pre/post → `root_id` | Alternative connectivity source / robustness comparison |
| `synapse_coordinates.csv.gz` | 302.142 | 34,156,320 | 5: `pre_root_id, post_root_id, x, y, z` | 65,482,006 empty fields across streamed rows; many rows have unattached pre/post IDs; exact duplicate sort not run | pre/post → `root_id` | Individual synapse geometry; offline research only |
| `neuropil_synapse_table.csv.gz` | 4.458 | 134,181 | 321: root ID + total input/output synapses/partners and per-neuropil breakdowns | 0 missing; 0 exact duplicate rows | `root_id` | Compact neuron-level connectivity/neuropil descriptors |
| `synapse_attachment_rates.csv.gz` | 0.003 | 162 | 5: `neuropil, count_total, count_proof, proof_ratio, side` | 0 missing; 0 duplicates | neuropil | Data-quality / proofread attachment priors |
| `coordinates.csv.gz` | 5.068 | 238,909 | 3: `root_id, position, supervoxel_id` | 0 missing; 13,321 exact duplicate rows; 139,255 unique root IDs | `root_id`, `supervoxel_id` | Anchors / multiple coordinate records per neuron |
| `connectivity_tags.csv.gz` | 0.608 | 134,437 | `root_id, connectivity_tag` | 0 missing; 0 duplicates | `root_id` | Graph motifs/tags such as reciprocal/rich-club/feedforward-loop |
| `processed_labels.csv.gz` | 0.971 | 100,091 | `root_id, processed_labels` | 0 missing; 0 duplicates | `root_id` | Processed annotation labels |
| `labels.csv.gz` | 4.550 | 160,045 parsed rows | 9 incl. `root_id,label,user_id,position,supervoxel_id,label_id,date_created,user_name,user_affiliation` | 1,363 missing (650 user_name, 713 affiliation); 0 duplicate rows; root IDs repeat by design | `root_id`, `supervoxel_id` | Human annotation provenance; not a semantic numeric feature by ID |
| `column_assignment.csv.gz` | 0.441 | 45,528 | 8: root, hemisphere, type, column_id, x,y,p,q | 0 missing; 0 duplicates | `root_id` | Optic column geometry/type |
| `visual_neuron_types.csv.gz` | 0.602 | 95,079 | root, type, family, subsystem, category, side | 8,477 missing (mostly subsystem); 0 duplicates | `root_id` | Visual-system typing |
| `neurons.csv.gz` | 1.602 | 139,255 | root, group, `nt_type`, confidence + DA/SER/GABA/GLUT/ACH/OCT averages | 19,658 missing `nt_type`; 0 duplicates | `root_id` | Neurotransmitter prediction features |
| `names.csv.gz` | 1.127 | 139,255 | root, name, group | 0 missing; 0 duplicates | `root_id` | Stable names/groups; IDs are join keys, not semantic features |
| `cell_stats.csv.gz` | 2.410 | 139,246 | root, length_nm, area_nm, size_nm | 0 missing; 0 duplicates | `root_id` | Morphology-size descriptors available without skeletons |
| `classification.csv.gz` | 0.891 | 139,255 | root, flow, super_class, class, sub_class, hemilineage, side, nerve | 302,034 missing values across sparse hierarchy; 0 duplicates | `root_id` | Hierarchical neuron classification |
| `consolidated_cell_types.csv.gz` | 0.860 | 138,327 | root, primary_type, additional_type(s) | 124,371 missing additional types; 0 duplicates | `root_id` | Consolidated cell types |

### `flywire_annotations-main.zip`

Archive compressed size: 11.588 MB. It contains the FlyWire annotation repository plus five supplemental data files. The README identifies the data as the public FlyWire female adult brain connectome release/materialization `783`. The changelog in the supplied snapshot includes annotation release `3.1.0`; no standalone LICENSE/COPYING file is present in the ZIP, so `CONNECTOME_LICENSE` must not be invented and is recorded as `UNSPECIFIED_IN_SUPPLIED_ARCHIVE` until a license is obtained from the authoritative distribution.

Supplemental parsed audit:

| Supplemental file | Rows | Cols | Missing | Exact duplicate rows | Key use |
|---|---:|---:|---:|---:|---|
| `Supplemental_file1_neuron_annotations.tsv` | 139,248 | 31 | 1,554,047 | 0 | `root_id`, `supervoxel_id`; full annotation hierarchy, top NT, side, VFB/FBbt, status, dimorphism, etc. |
| `Supplemental_file2_non_neuron_annotations.tsv` | 841 | 27 | 11,344 | 0 | non-neuronal objects |
| `Supplemental_file3_summary_with_ngl_links.csv` | 205 | 25 | 858 | 0 | hemilineage summary, NGL links, ID collections |
| `Supplemental_file4_hemilineages_clustering.csv` | 24,406 | 8 | 6,181 | 0 | `root_id`; persistent morphology cluster / hemilineage grouping |
| `Supplemental_file5_hemibrain_meta.csv` | 25,397 | 16 | 105,954 | 0 | hemibrain bodyId metadata for comparative analysis |

### What is present

- root/neuron IDs and directed connectivity
- connection synapse counts and neuropil labels
- neurotransmitter predictions
- individual synapse coordinates (with attachment gaps)
- neuron anchor coordinates
- neuron size/length/area descriptors
- classifications, cell types, visual types, labels and connectivity tags
- supplemental hemilineage clustering and metadata

### What is **not** present in the supplied files

- complete neuron skeleton files
- NBLAST score matrices
- a declared license file in the supplied ZIP
- any mapping from fly-neuron IDs to financial semantics (and no such mapping should be fabricated)
- evidence that FlyWire topology adds trading edge

The repository README explicitly states that skeletons/NBLAST are too large for GitHub and are distributed separately. Therefore the current implementation does not invent branch-count/arborization features from absent skeletons.

## C. Concrete implementation architecture

`MarketEvent` → strict mint verification → point-in-time state → feature engines → Genesis/World/Persistence → executable alpha → AI Paper Trader → Risk Governor → realistic Paper Execution → portfolio ledger → post-trade research.

Real-time/fast path: Capital Surprise, wallet quality cache, funding recency, actor/co-buy state, market acceleration, token risk, compact Hawkes, compact hypergraph/sequence state, trained/distilled Genesis model, Risk Governor.

Deep path: larger actor graph, full/filtered FlyWire reservoir, quantum-inspired active subgraph features, historical analogues, future-state/world-model outputs. Deep path is optional and cannot block the fast path.

## D. Dependency graph

- ingestion → domain events
- event state → wallet/token point-in-time histories
- Capital Surprise / wallet quality / funding / actor graph / acceleration / token risk → Genesis features
- actor graph → cluster, flow, optional quantum graph
- event sequence → Hawkes, temporal sequence, Jump-state
- FlyWire preprocessing → sparse adjacency artifact → FlyWire reservoir
- all feature engines → Genesis + World Model + Persistence
- Genesis + Persistence + execution assumptions → Executable Alpha
- Executable Alpha + portfolio state → AI Paper Trader
- proposal + token/account state → Risk Governor
- approved proposal → Paper Execution → Portfolio
- closed trade → Post-Trade Review → candidate hypothesis only

## E. Compute plan

FAST PATH: Python asyncio/API process, cached wallet statistics, stateful token engines, small active graphs.

DEEP PATH: optional worker/research process. Full FlyWire preprocessing is offline; production defaults to a top weighted-degree sparse induced reservoir (`max_nodes=20,000`) and can be enlarged after profiling.

OFFLINE: FlyWire preprocessing, historical feature building, model training/calibration, walk-forward, ablations, analogue index building.

REAL-TIME: normalized Solana/Helius events, state updates, inference, paper decisions/execution.

## F. Implementation delivered in this package

Implemented and executable now:
- normalized event schema / Event Digital Twin core
- point-in-time series guard
- Capital Surprise
- wallet quality from resolved-only histories
- actor/co-buy graph and funding recency
- temporal sequence features
- market acceleration
- token risk
- marked-Hawkes-style cascade baseline
- graph-flow-inspired capital features
- typed temporal hyperedge store
- latent irregular jump-state baseline
- elite/runner-holder retention and smart-capital consensus state
- optional quantum-inspired active-graph features
- real FlyWire sparse-reservoir preprocessing/loader
- Genesis trainable model interface + conservative untrained baseline
- World Model interface + baseline
- Persistence
- Executable Alpha proxy
- AI Paper Trader actions PASS/WATCH/ENTER/ADD/HOLD/REDUCE/EXIT/KEEP_RUNNER_BAG
- Risk Governor
- deterministic realistic paper execution model
- portfolio accounting
- replay/backtest
- Helius webhook/Parsed Events normalizers
- FastAPI API
- React/Vite dashboard
- chronological training script and walk-forward fold utility
- Windows scripts
- tests

Not falsely claimed as trained/validated:
- calibrated runner probabilities on real historical memecoin data
- a fitted graph-neural Jump-SDE
- DSHN/sheaf neural network
- proven Hawkes branching threshold for runners
- proven FlyWire edge
- proven quantum-inspired edge
- full skeleton morphology features
- production-grade protocol decoder coverage for every Pump/Raydium/Jupiter variant
- live-money execution (intentionally disabled)

## G. Main technical risks

1. Future leakage in wallet/actor/caller reputation: resolved timestamps must be availability timestamps.
2. Survivorship/backfill bias in wallet histories and token universe.
3. Event-order differences between RPC sources; replay must store slot/signature/order.
4. Asset mismatch: symbol/name fallback is forbidden; mint verification is mandatory.
5. Protocol decoder drift as Solana programs upgrade.
6. Sparse graph memory: never densify FAFB or large actor graphs.
7. FlyWire overfitting: compare REAL vs shuffled/rewired/degree-preserved/random reservoirs.
8. Hyperparameter/multiple-testing overfit across cohort/sequence mining.
9. Paper optimism: latency, partial fills, failures, MEV-like adverse execution, sellability and price impact must stay in evaluation.
10. Model probability calibration drift; score is not probability until verified OOS.

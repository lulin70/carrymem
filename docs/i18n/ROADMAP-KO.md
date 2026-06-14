# CarryMem 제품 로드맵

**최종 업데이트**: 2026-05-29
**제품 포지셔닝**: AI 신원 레이어 — 기억 + 규칙 + 지식
**버전 체계**: v0.2.x (증분) → v0.3.0 (GA 마일스톤)

---

## 버전 전략

```
v0.1.7 ─── Memory Layer Enhancement (Session + Supersession + Time Reasoning) ✅
  │
  ├── v0.2.0  Scene Detection      (Pattern Recognition from Memories)   ✅
  ├── v0.2.1  Rules Engine Alpha   (Manual CRUD + FTS5 Match + Security) ✅
  ├── v0.2.2  Rules Engine Alpha+  (Performance + Conflict Detection)    ✅
  ├── v0.2.3  Rules Engine Alpha+  (Export/Import + Interactive CLI)     ✅
  ├── v0.2.5  Auto-Promotion       (Memory → Rule Candidate Generation)  ✅
  ├── v0.2.6  Experience Learning   (Failure → Avoidance Rules)          ✅
  ├── v0.2.7  Q&A Refinement       (Multi-turn Rule Abstraction)         ✅
  ├── v0.2.8  Rules Engine Beta    (Context Engineering + Hardened)      ✅
  │
  ├── v0.3.0  GA Release           (Production Ready + Knowledge Adapter) ✅
  ├── v0.4.0  Protocol & Maturity Sprint (Scopes + Skill + Merge + VS Code)     ✅
  └── v0.4.1  Core Loop Fix        (Auto Rule Suggestion + Security)      ✅
```

**버전 관리 규칙**:
- 세 번째 자리: 단계 내 증분 업데이트
- 두 번째 자리: GA 마일스톤 (API 안정성 보장)
- "v1.0.0 점프" 없음 — 실제 프로덕션 사용으로 획득

> **참고**: 위에 나열된 v0.3.0–v0.4.1 버전은 프로젝트의 개발 이력을 나타냅니다. 현재 버전은 v0.2.5이며, 자동 백업, 암호화 .carry 파일, 동시성 안전, E2E 테스트, **PrefEval 83.0%** (200샘플, 3조건 정식), 상태/이벤트 버전 체인, 보안 강화, 선호 주입 최적화, context.py 모듈화, 통합 스케줄링 등을 포함합니다. 다음 마일스톤: v0.3.0 (GA).

---

## 제품 비전

### 3계층 신원 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│                    CarryMem 신원 레이어                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Layer 3: Rules (HOW to act)        ← v0.2.x 완료         │
│  ┌──────────────────────────────────────────────────┐    │
│  │  "When X happens, do Y"                          │    │
│  │  • Manual rules (v0.2.1)                         │    │
│  │  • Auto-promoted from patterns (v0.2.5)          │    │
│  │  • Learned from failures (v0.2.6)                │    │
│  │  • Refined through dialogue (v0.2.7)             │    │
│  │  • Context-anchored injection (v0.2.8)           │    │
│  └──────────────────────────────────────────────────┘    │
│              ↑ reads from          ↑ injects into         │
│  Layer 2: Memory (WHO you are)     ← v0.3.0 안정          │
│  ┌──────────────────────────────────────────────────┐    │
│  │  "You prefer X, decided Y, corrected Z"          │    │
│  │  • 7 memory types + 4-tier hierarchy             │    │
│  │  • Cross-language semantic recall (FTS5)          │    │
│  │  • Session-aware storage + knowledge supersession (v0.1.7)   │    │
│  │  • Time reasoning + structured prompt injection (v0.1.7)     │    │
│  │|  •  3244 tests passing, 80%+ coverage           ││    │
│  └──────────────────────────────────────────────────┘    │
│              ↑ reads from          ↑ injects into         │
│  Layer 1: Knowledge (WHAT you know) ← v0.3.0 계획         │
│  ┌──────────────────────────────────────────────────┐    │
│  │  "Your Obsidian vault, your docs, your notes"    │    │
│  │  • Obsidian Markdown adapter (existing)          │    │
│  │  • Memory + Knowledge joint retrieval            │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Retrieval Priority: Rules(override) > Memory > Knowledge │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 핵심 차이점

| 레이어 | 답변 | 형태 | 트리거 | 예시 |
|-------|------|------|--------|------|
| **Memory** | "Who are you?" | 선언적 | 수동 (context-relevant) | "I prefer PostgreSQL" |
| **Rules** | "How do you act?" | 조건 → 행동 | 능동 (scene-matched) | "When choosing DB, use PostgreSQL" |
| **Knowledge** | "What do you know?" | 참조 | 요청 시 (retrieved) | "PostgreSQL vs MySQL comparison" |

---

## 컨텍스트 엔지니어링 인사이트 (신규 — v0.2.8)

### Lost-in-the-Middle 효과와 규칙 주입

LLM 주의력은 U자형 곡선을 따름: **시작과 끝에서 높고, 중간에서 낮음** (10-40% 리콜 하락). 이는 규칙 주입 신뢰도에 직접적인 영향.

**현재 문제** (v0.2.1-v0.2.7):
```
## Personal Rules (from CarryMem)
Rule A (relevance=0.92, override=true)   ← 시작: 높은 주의력
Rule B (relevance=0.88, override=false)  ← 중간: 주의력 붕괴
Rule C (relevance=0.85, override=true)   ← 중간: 가장 중요한 규칙 무시!
Rule D (relevance=0.80, avoid)           ← 끝: 2차적 주의력
```

**v0.2.8 해결책**: 앵커링 레이아웃 모드
```
## Personal Rules (from CarryMem)

### Absolute Prohibitions (never violate)
- [forbid] Never cite competitor data without verification     ← HEAD ANCHOR

### Recommended
- [always] Confirm inventory by phone for Hamburg warehouse
- [avoid] Prefer domestic warehouses for cross-border transfers

### Mandatory Actions (never skip)
- [always] All external quotes must include validity period     ← TAIL ANCHOR
```

### 컨텍스트 예산 모니터링

규칙 주입이 컨텍스트 윈도우의 70%를 초과하면 자동 압축:
- 우선순위: override=true 규칙 유지, avoid 규칙을 요약으로 압축
- 임계값 초과: 규칙당 한 줄 요약, 출처 정보 없음

### DDD 언어 뷰

CarryMem 개념을 DDD 개념에 매핑하여 엔터프라이즈 아키텍트 대화 지원:

| CarryMem | DDD | 관계 |
|----------|-----|------|
| trigger | Bounded Context | 범위 정의 |
| rule_type (forbid/avoid/always) | Aggregate Consistency Constraint | Invariant ≈ forbid, Guarantee ≈ always |
| override | Invariant | 더 높은 우선순위로 재정의 불가 |
| source_memories | Event Sourcing Chain | 규칙을 원래 경험까지 추적 가능 |
| refine process | Ubiquitous Language Refinement | 구체 → 일반 추상화 |

구현: `format_rules_as_prompt()` 내 `style="ddd"` 파라미터, 표시 전용, 저장소 변경 없음.

---

## 마일스톤 계획

### ✅ v0.2.0 (완료)

상세 이력은 CHANGELOG.md 참조.

---

### ✅ v0.2.5 — Auto-Promotion (완료)

**구현된 기능**:
- [x] PromotionPipeline: 5단계 파이프라인 (Collect→Detect→Generate→Queue→Confirm)
- [x] 감사 추적: `promotion_audit` 테이블에 전체 작업 로깅
- [x] CLI: `promote-rules`, `review-promotions`, `promotion-log`
- [x] 큐 크기 제한 (50), 설정 가능한 만료 (7일)
- [x] `_count_pending()` 효율적 COUNT 쿼리

---

### ✅ v0.2.6 — Experience Learning (완료)

**구현된 기능**:
- [x] FailureExperienceExtractor: 5가지 신호 유형 (mistake/regret/negative_outcome/lesson_learned/correction_from_failure)
- [x] 이중언어 패턴 매칭 (EN + ZH)
- [x] ExperienceRuleBridge: 확인 워크플로우 + `experience_audit` 테이블
- [x] 도메인 추론: 7개 도메인
- [x] CLI: `learn-experience`, `review-lessons`, `lesson-log`

---

### ✅ v0.2.7 — Q&A Refinement (완료)

**구현된 기능**:
- [x] RuleRefiner: 4단계 정제 (Scope→Generality→Exception→Confirm)
- [x] 특이성 분석: 프로젝트/도구/시간별 규칙 탐지
- [x] RefinementSessionManager: 세션 지속성 + 대화 추적
- [x] CLI: `refine-rule`, `refinement-sessions`
- [x] 최대 5라운드, 자동 강제 확인

---

### ✅ v0.2.8 — Rules Engine Beta (Context Engineering + Hardened)

**테마**: 프로덕션 강화 + 컨텍스트 엔지니어링 최적화
**LLM 의존성**: 없음 (핵심 기능 LLM 없이 작동)

**P0 — Context Engineering (최적화 메모에서)**:
- [x] `format_rules_as_prompt()` 앵커링 레이아웃 모드
  - 헤드 앵커: override=true + forbid 규칙
  - 중간: 관련성 순 일반 규칙
  - 테일 앵커: override=true + always 규칙
- [x] `format_rules_as_prompt()` style="ddd" 출력
  - DDD 용어: "Personal Context → Invariant/Consistency/Soft Constraint"
  - 표시 전용, 저장소 레이어 변경 없음

**P1 — Production Hardening**:
- [x] 컨텍스트 예산 모니터링 (token 인식 압축)
- [x] 테스트 커버리지 ≥ 80% (현재: 80.70%, 68.61%에서 상승)
- [x] CLI 커버리지 ≥ 70% (현재: ~77%)
- [x] 보안 감사: 모든 입력 경로 검토 (InputValidator가 CLI/MCP/import에 통합)
- [x] API 안정성 보장 (v0.3.x에서 호환성 깨짐 없음) — API_STABILITY.md 참조
- [x] `carrymem doctor` 종합 건강 검사 (14항목 + JSON 출력 + --fix)
- [x] 문서 완료 (API_REFERENCE가 v0.2.8과 동기화됨)

**P2 — Quality Improvements**:
- [ ] source_memories confidence 상태 (active/overridden/superseded)
- [ ] Rule effectiveness metrics (trigger count, user satisfaction)

---

### 🎉 v0.3.0 — GA Release (Production Ready) ✅ **DONE**

**테마**: 최초 프로덕션 준비 릴리스 + Knowledge Adapter
**LLM 의존성**: 선택 사항 (핵심 기능 LLM 없이 작동)

**P0 — Knowledge Adapter Enhancement**:
- [x] ObsidianAdapter CJK 전문 검색 업그레이드
  - `unicode61` 토크나이저를 `trigram`으로 교체하여 CJK 문자 수준 매칭
  - 콘텐츠 잘라내기: 500 → 설정 가능 (기본값 2000 문자, `full_content=True`로 전체)
  - 기존 데이터베이스의 `unicode61` → `trigram` 자동 마이그레이션
- [x] Knowledge relevance scoring
  - 점수 기준: FTS5 rank (60%) + tag overlap (25%) + wiki-link proximity (15%)
  - `relevance_score` 필드를 recall 결과에 포함
- [x] Knowledge + Rules + Memory 3계층 검색 오케스트레이션
  - 검색 우선순위: Rules(override) > Memory > Knowledge
  - `build_context()` 통합 예산 배분: Rules 30% / Memory 45% / Knowledge 25%
  - `build_system_prompt()` 구조화 출력: Rules → Memory → Knowledge
  - `recall_all()`에 `rules` 레이어 포함 (`include_rules=True` 사용)

**P1 — Production Hardening (v0.2.8 P2에서)**:
- [x] `trigger_count` 활성화 — `increment_trigger_count()`를 `RuleEngine.match()`에 연결
  - `RuleStorage.increment_trigger_count(rule_id)` 원자적 DB 업데이트
  - `batch_increment_trigger_counts()` 다중 규칙 효율화
  - matcher의 빈도 보너스 이제 동작
- [x] Rule effectiveness metrics
  - `engine.get_effectiveness_report()` — trigger 통계, confidence 분포, override 사용량
  - 유형별 분할, 유출 출처, top-triggered/never-triggered 목록
- [x] source_memories confidence 상태
  - `validate_source_memories(rule_id)` — 소스 기억이 여전히 존재하는지 확인
  - 상태 추적: active / deleted / superseded
  - 자동 계산 confidence 조정 페널티

**P2 — API Stability & Governance**:
- [x] Rules Engine API를 Experimental → Stable로 승격
  - `RuleEngine` CRUD + match + inject: `@stable`
  - Promotion/Refinement/Experience: `@experimental` 유지
- [x] Stable API용 TypedDict 반환 타입 (dict 호환)
- [x] Community governance: CONTRIBUTING.md, issue templates, PR checklist

**Existing Foundation** (이미 작동 중):
- ObsidianAdapter: 읽기 전용 FTS5 인덱스 + 검색 + wiki-link + frontmatter ✅
- `recall_all()`: memory + knowledge 통합 검색 ✅
- `build_context()` / `build_system_prompt()`: knowledge 주입 ✅
- DevSquadAdapter: Protocol-based integration ✅
- API_STABILITY.md: Stable/Experimental/Internal 계층 ✅

---

## v0.4.0 Protocol & Maturity Sprint — DONE ✅

### v0.4.0 — Protocol & Maturity Sprint

**테마**: 멀티 스코프 규칙, 휴대 가능 Skill 형식, 에디터 통합
**선행 조건**: v0.3.0 GA 릴리스

**P0 — Rule Scope Dimension**:
- [x] Rule model: `scope` 필드 추가 (`personal` / `company` / `negotiated`)
  - `RuleScope` enum: personal (사용자 생성), company (조직 강제), negotiated (회사에서 적응)
  - 기본값: `personal` (하위 호환)
  - 저장소: SQLite rules 테이블에 새 `scope` 컬럼
  - 마이그레이션: 기존 규칙 기본값 `personal`
- [x] Scope-aware matching and injection
  - `RuleEngine.match()`에 `scopes` 필터 수용 (기본값: all)
  - `RuleInjector` 출력에 scope 라벨 주석
  - 우선순위: 충돌 시 `company(override) > negotiated > personal`
- [x] Scope-aware CRUD
  - `add_rule(scope="personal")` — 기본값
  - `list_rules(scope="company")` — scope로 필터
  - Company 규칙: 비관리자 사용자 변경 불가 (adapter 레이어에서 강제)

**P1 — Rule Skill Format**:
- [x] Skill manifest specification (`carrymem-skill-v1`)
  - 메타데이터: name, author, version, description, dependencies, scope
  - 구조: rules + templates + config 단일 JSON 번들
  - 서명: 무결성 검증용 콘텐츠 해시
- [x] Skill CLI 명령어
  - `carrymem skill-pack <path>` — 규칙을 Skill 번들로 내보내기
  - `carrymem skill-install <path>` — Skill import 및 scope 할당
  - `carrymem skill-verify <path>` — Skill 무결성 검증
- [x] Skill export/import 업그레이드
  - 기존 `export_rules()` / `import_rules()`를 Skill 형식으로 확장
  - 하위 호환: `carrymem-rules-v1` import 지원

**P2 — Rule Merge Protocol ("Customs Clearance")**:
- [x] Scope-aware merge engine
  - `RuleMergeEngine` with strategies: `company_overrides`, `negotiate`, `keep_both`
  - 충돌 탐지: company rule vs personal rule on same trigger
  - 자동 협상: personal rule을 company 제약 위반하지 않도록 조정
- [x] "Customs clearance" flow
  - Company 규치이 personal 공간 진입 시: review → adapt → confirm
  - `engine.review_incoming_rules(rules, scope="company")` — 충돌 미리보기
  - `engine.accept_rules(rule_ids, merge_strategy="negotiate")` — 적응 후 수락
- [x] Merge audit trail
  - 모든 병합 결정에 이유, 타임스탬프, 원본 값 기록

**P3 — VS Code Extension (stretch goal)**:
- [x] Extension scaffold (TypeScript)
  - Webview rule editor panel
  - Sidebar: rule list with scope badges
  - Commands: add/edit/delete/toggle rule
- [x] Backend communication via CarryMem CLI
  - CarryMemClient: subprocess-based communication
  - All CRUD + match + effectiveness + skill operations
- [x] Inline rule suggestions
  - On command: match rules to current file type/context
  - QuickPick with matched rules and scores

**Existing Foundation** (이미 작동 중):
- `export_rules()` / `import_rules()` with 3 conflict modes ✅
- Rule templates (10 predefined) ✅
- Memory namespace isolation (reusable pattern) ✅
- `validate_namespace()` (reusable for scope validation) ✅
- Rule conflict detector (detect-only, extensible) ✅
- MCP HTTP Server (reusable for VS Code backend) ✅

### v0.4.1 — Core Loop Fix (Product初心 Review)

**테마**: 깨진 핵심 루프 수정 — memory→rule→injection 파이프라인
**선행 조건**: v0.4.0 enterprise features

**P0 — Core Loop Repair** (product from unusable → usable):
- [x] `_auto_suggest_rules()` implementation — memory→rule candidate generation
  - PatternDetector + CandidateRuleGenerator integration
  - Trigger extraction from natural language (tech keyword detection)
  - Rule type inference from memory type (correction→avoid, decision→always)
- [x] MCP rule tools target fix — shared RuleEngine instance
  - Handlers init creates shared RuleEngine with correct db_path
  - Rule tools target changed from None to self._rule_engine
- [x] `get_system_prompt` auto-inject without context
  - No-context path lists all active rules and formats them
  - Global rules always injected into AI prompt
- [x] User management MCP tools: `my_rules`, `delete_rule`
- [x] Rule injection security filter — INJECTION_DANGER_PATTERNS regex
- [x] Natural conversation preference extraction tests (23 cases)
- [x] E2E user journey tests (conversation→store→rule→inject→verify)

**P1 — Experience Optimization** (product from usable → good):
- [x] Correction auto-updates old memories/rules (`_handle_correction`)
- [x] `update_rule` MCP tool
- [x] `my_profile` MCP tool — complete user identity view
- [x] `onboard` MCP tool — first-time user guidance (EN/ZH/JA)
- [x] Rule application feedback — `applied_rules` field in build_context
- [x] Rule conflict detection on add_rule — `_conflict_warnings`
- [x] FTS5 rank score optimization — `search_with_rank()` method
- [x] MCP config auto-inject settings — `CARRYMEM_AUTO_INJECT` env var

**P2 — Smart Enhancement** (product from good → smart):
- [x] Rule expiry mechanism — `expires_at` field + `is_expired()` method
- [x] CLI rule management enhancement — `--format table/compact/detail`
- [x] `carrymem doctor` enhancement — rules engine + auto-inject checks
- [x] Chinese tokenization optimization (jieba) — jieba segmentation with n-gram fallback
- [x] Conditional preference support — `condition` field for if-then rules
- [x] Implicit preference inference — `_detect_implicit_preferences()` from memory patterns

**MCP Tools** (27 tools):
- Core (3): classify_message, get_classification_schema, batch_classify
- Storage (3): classify_and_remember, recall_memories, forget_memory
- Knowledge (3): index_knowledge, recall_from_knowledge, recall_all
- Profile (2): declare_preference, get_memory_profile
- Prompt (2): get_system_prompt, summarize_and_store
- Consolidation (3): consolidate_memories, schedule_consolidation, stop_consolidation
- Rules (11): add_rule, list_rules, match_rules, inject_rules, my_rules, delete_rule, suggest_rules, promote_rules, update_rule, my_profile, onboard

### v0.1.7 — Memory Layer Enhancement (Intelligent Memory Layer) ✅

**테마**: 검색 시스템에서 지능형 기억 레이어로
**LLM 의존성**: 없음 (모든 기능 LLM 없이 작동)

**Phase 1: Session-Aware Storage + Knowledge Supersession**:
- [x] `classify_and_remember(session_id=...)` — 세션 식별자로 cross-session 인식
- [x] Auto-supersession — `superseded_at`/`supersedes` 필드, 모순 탐지, 업데이트 마커
- [x] `recall_aggregated()` — 모든 세션에서 유형별 기억 집계
- [x] `recall_timeline(topic)` — 주제별 시간순 기억 리콜
- [x] New filter keys: `session_id`, `created_before`, `include_superseded`, `_order_oldest`

**Phase 2: Time Reasoning + Context Rebuild**:
- [x] `_parse_time_expressions()` — 쿼리에서 시간 제약 추출 (zero LLM)
- [x] `_rebuild_context()` — 사용자 프로필의 관련 단어로 FTS5 쿼리 확장
- [x] `_order_oldest` filter — "first/earliest" 쿼리 지원

**Phase 3: Structured Prompt + Knowledge Updates**:
- [x] Priority labels: `[MANDATORY]`, `[IMPORTANT]`, `[OUTDATED]`
- [x] `_build_superseded_notes()` — 지식 업데이트 추적
- [x] Structured prompt sections: Mandatory → Important → Context → Outdated → Knowledge Updates
- [x] `build_context()` safe access for `__new__()` created objects

**Benchmark Results (LongMemEval 100-question sample)**:
- temporal-reasoning: 0.110 → 0.127 (+15%)
- single-session-assistant: 0.196 → 0.200
- knowledge-update: 0.055 → 0.057
- Overall: 0.107 → 0.105 (stable, value in new capabilities)

**Next**: Phase 4 — Session Summary + Semantic Aggregation (requires LLM)

### v0.5.0 — Intelligence Enhancement (Partially Complete)
> **상태**: 부분 완료 — Consolidation Engine과 PrefEval은 pre-reset 주기에서 달성됨. 나머지 항목은 v0.6.0+로 연기.
- [x] Consolidation Engine (P0: dedup+decay, P1: pattern→rules, P2: semantic merge)
- [x] PrefEval 96.0% preference adherence (50 items, ICLR 2025 Oral)
- [x] 27 MCP tools (added consolidate_memories)

> **PrefEval 수치 참고**: 샘플 크기와 seed에 따라 결과가 다릅니다. 정식 결과는 **83.0%** (200 items, 3-condition comparison: CarryMem 83.0% > reminder 80.0% > zero-shot 71.5%)이며, README에 문서화되어 있습니다. 그 외 수치(85.0%, 87.9%, 96.0%)는 다른 평가 설정을 반영하며 직접 비교해서는 안 됩니다.
- [ ] Consolidation scheduled trigger (auto dedup+decay)
- [ ] Motive memory type (pending→activated→completed lifecycle)
- [ ] PrefEval evaluation standardization (reproducible scripts + report template)
- [ ] Vector-based semantic matching (optional embedding model)
- [ ] Rule recommendation engine
- [ ] Cross-user rule sharing (with anonymization)
- [ ] Ontology-based trigger matching

### ✅ v0.2.2 — PrefEval Violation Optimization + Version Chain

**테마**: PrefEval 최적화 + 상태/이벤트 버전 체인 + 보안 강화
**원칙**: #3 PrefEval focus + #1 Lightweight

**P0 — Violation Rate Optimization** (DONE):
- [x] PrefEval 200-sample violation case 분석
- [x] Fix coreference replacement text injection vulnerability (security)
- [x] Preference token budget 40%→60%, preventing preference truncation
- [x] PrefEval 200-sample: CarryMem **87.9%** (single-condition peak)
- [x] Update README PrefEval progress table (EN/CN/JP)
> *Historical note: Peak single-condition result. Canonical: **83.0%** (3-condition).*

**P0 — Version Chain** (DONE):
- [x] Add `memory_nature`(state/event) + `version_chain_id` + `version_number` fields
- [x] State memory: auto-supersede old version on write, maintain version chain
- [x] Event memory: no merge, full retention, no versioning
- [x] Query: state→latest version only (superseded filtered by default), event→chronological
- [x] Backward compatibility: __post_init__ auto-infer, SQLite migration v0.90 with backfill
- [x] 27 version chain tests all passing

**P1 — context.py Modularization** (DONE):
- [x] Split context.py (910 lines) into: selection.py, scope.py, format.py, prompt.py
- [x] Each module < 250 lines, original API preserved via re-export

### v0.2.0 — Auto-Maintenance + Evaluation Standardization ✅

**테마**: Consolidation scheduling + reproducible PrefEval + non-technical user reach
**원칙**: #1 Lightweight — auto-maintenance reduces manual burden

**P0 — PrefEval Fair Benchmark** (DONE):
- [x] 200-sample, 3-condition comparison (zero-shot/reminder/carrymem)
- [x] CarryMem **85.0%** > reminder 83.0% > zero-shot 69.5% (seed=42)
- [x] SQLite "database is locked" fix (busy_timeout + _auto_supersede commit)
- [x] PrefEval script: force_type + no noise + include_question=True + max_tokens=500
> *Historical note: seed=42 fair comparison result. Canonical: **83.0%** (latest run).*

**P1 — Consolidation Scheduling** (DONE):
- [x] `schedule_consolidation(interval_hours=1)` method
- [x] CLI: `carrymem consolidate --schedule 1h`

**P2 — Non-Technical User Reach** (DONE):
- [x] README scenario entry points (EN/CN/JP)
- [x] `carrymem pack` / `carrymem unpack` CLI (gzip .carry format)
- [x] `carrymem setup-mcp --global` (one install, all agents share CarryMem)
- [x] `carrymem mcp` subcommand (stdio transport)
- [x] GitHub About/topics/description updated

**P3 — Technical Debt Cleanup** (DONE):
- [x] Unified path management (constants.py replaces hardcoded paths)
- [x] Empty except:pass → debug/warning logging (35+ locations)
- [x] pyproject.toml fail_under 55→75
- [x] README data conflict resolved
- [x] .gitignore updated (*.carry)

**Remaining**:
- [ ] Integration with APScheduler (optional dependency)
- [ ] McNemar statistical significance test

### v1.0.0 — Autonomous Identity
- Fully automatic rule learning
- Predictive rule suggestion
- Multi-agent coordination
- Identity portability standard

---

## Post-Beta Roadmap — Competitive Intelligence Absorption

> **출처**: DevSquad 4-role review (Architect + PM + Security + DevOps)
> **날짜**: 2026-06-02 | **검토 프로젝트**: Lum1104/Understand-Anything (v2.7.3) + rtk-ai/rtk (v0.40.0)
> **규칙**: Beta frozen — release 전 코드 변경 없음. 이 항목들은 v0.2.5+ 계획용으로 기록.

### Analysis Summary

| 차원 | Understand-Anything | rtk | CarryMem Current |
|------|---------------------|-----|------------------|
| **Positioning** | Code → Knowledge Graph | Token-saving proxy | AI Memory Layer |
| **Languages** | 8 (EN/ZH-CN/ZH-TW/JA/KO/ES/TR/RU) | 7 (EN/FR/ZH/JA/KO/ES/PT) | 3 (EN/CN/JP) |
| **Platforms** | 14 (Plugin + install.sh) | 14 (Hook + Plugin) | 9 (MCP stdio) |
| **Tech Stack** | TypeScript + Tree-sitter + LLM | Rust (single binary) | Python + SQLite |
| **Key Differentiator** | Visual Dashboard + Guided Tour | `rtk gain` value metrics | Zero-LLM classification (88%) |

### ✅ Consensus: ABSORB (4/4 roles agreed)

#### P0-1: Multi-Language Expansion (KO + ZH-TW)

| Role | Verdict | Rationale |
|------|---------|-----------|
| Architect | ✅ Feasible (5/5) | i18n template exists, translation-only effort |
| PM | ✅ High Value (9/10) | Korean = Asia AI hub, ZH-TW = Taiwan/HK market |
| Security | ✅ Zero Risk | Documentation only, no code change |
| DevOps | ✅ Low Cost | MD files only, no CI impact |

**Target**: ~~v0.2.5 (post-Beta patch) or v0.3.0~~ → **✅ Completed in v0.2.5**
**Scope**: Add `README-KO.md` + `README-ZH-TW.md` + update language switcher in all READMEs
**Status**: ✅ Done — Korean (README-KO.md) and Traditional Chinese (README-ZH-TW.md) published. All 5 language switchers updated.

---

#### P1-1: `carrymem stats --value` (Value Perception Command)

**Inspired by**: rtk's `rtk gain` — real-time token savings analytics

| Role | Verdict | Rationale |
|------|---------|-----------|
| Architect | ✅ Reuse existing (4/5) | Extends `stats` command, adds value metrics |
| PM | ✅ ROI Driver (9/10) | Users who see value → retain 3x longer |
| Security | ✅ Low Risk | Read-only stats, no data exposure |
| DevOps | ✅ Zero Infra | No new dependencies |

**Proposed Output**:
```
$ carrymem stats --value
╭─────────────────────────────────────────╮
│ CarryMem Value Report                   │
├─────────────────────────────────────────┤
│ Memories Stored:        147             │
│ Rules Active:           23              │
│ Sessions Remembered:    12              │
│ Repetitions Avoided:    ~340 est.       │
│ Tokens Saved (est.):    ~17,000         │
│ Identity Coverage:      87%             │
│ Days Since First Use:   23              │
╰─────────────────────────────────────────╯
```

**Target**: ~~v0.2.5~~ → **✅ Completed in v0.2.5**
**Status**: ✅ Done — `carrymem stats --value` implemented with 7-metric value perception report (box-drawing text output + JSON format support).

---

#### P1-2: `.carry` Team Sharing Workflow Enhancement

**Inspired by**: UA's "commit knowledge graph to Git" pattern

| Role | Verdict | Rationale |
|------|---------|-----------|
| Architect | ✅ Already Works (5/5) | `.carry` files are git-friendly by design |
| PM | ✅ Differentiator (8/10) | Competitors can't do encrypted portable memory |
| Security | ✅ AES-128 Protected | Encryption already verified |
| DevOps | ✅ No Change Needed | Just documentation enhancement |

**Action**: Add "Team Sharing" section to README / USER_GUIDE:
```bash
# Share your identity with teammates (encrypted):
carrymem pack --output team-identity.carry
git add team-identity.carry && git commit -m "share identity"

# Teammate imports:
carrymem unpack team-identity.carry
```

**Target**: v0.2.5 (released)

---

### ✅ Completed in v0.2.5 Sprint (2026-06-07)

#### P0-A: Preference Injection Fix
- **Status**: ✅ Done
- **What**: Fixed confidence gap between classifier (0.5-0.8) and prompt_builder (≥0.9)
- **How**: Active contextual fetch with scope filtering for 0.5-0.9 conf preferences
- **Result**: 14/14 E2E tests passing (was 7 xfail)

#### P0-B: SQL Injection Hardening
- **Status**: ✅ Done
- **What**: session_id LIKE pattern escape for `"`, `\`, `%`, `_`
- **Impact**: Prevents metadata corruption from special characters in session IDs

#### P2-A: CLI Modularization
- **Status**: ✅ Done
- **What**: cli.py 4031→8 modules + 17-line facade (_base/_memory/_io/_stats/_mcp/_backup/_rules)
- **Result**: Max module size ~1060 lines (rules.py), 99% backward compatible

#### P2-B: Security Test Coverage
- **Status**: ✅ Done
- **What**: 83 new tests in test_security_extended.py
- **Result**: Coverage 22% → 80%+ (encryption 79%, redaction 90%, input_validator 82%, audit 88%)

#### P2-C: MCP Server Timeout
- **Status**: ✅ Done
- **What**: 3-layer timeout (stdin 300s / request 30s / tool call 30s)
- **Config**: CARRYMEM_REQUEST_TIMEOUT env var, default 30s

---

### ⚠️ Consensus: CONDITIONAL ABSORB (needs further discussion)

#### P2-1: Web Dashboard (Optional Dependency)

**Inspired by**: UA's interactive knowledge graph dashboard

| Role | Verdict | Condition |
|------|---------|-----------|
| Architect | ⚠️ Feasible but heavy | Requires Streamlit/FastAPI as optional dep |
| PM | ⚠️ Nice-to-have | Visual users love it; CLI purists don't care |
| Security | ⚠️ New attack surface | Web server = new vuln vector |
| DevOps | ⚠️ Deployment complexity | Docker already solves this |

**Decision**: Defer to **v0.3.0 GA** as optional `carrymem[dashboard]` extra.
**Condition**: Must be opt-in (`pip install carrymem[dashboard]`), never auto-enabled.

---

#### P2-2: Git Post-Commit Auto-Consolidation Hook

**Inspired by**: UA's `--auto-update` post-commit hook

| Role | Verdict | Condition |
|------|---------|-----------|
| Architect | ⚠️ Simple implementation | `carrymem hook install --post-commit` wrapper |
| PM | ⚠️ Power user feature | Most Beta users won't use this |
| Security | ⚠️ Hook execution risk | Must validate hook script integrity |
| DevOps | ✅ Low complexity | Just a .git/hooks file template |

**Decision**: Defer to **v0.3.0**, implement as opt-in hook only.

---

### ❌ Consensus: DO NOT ABSORB (4/4 roles agreed)

| Feature | Source | Reason to Skip |
|---------|--------|----------------|
| **Rust rewrite** | rtk | Python ecosystem is our strength; SQLite/MCP integration is Python-native |
| **Tree-sitter integration** | UA | Out of scope — we do memory, not code analysis |
| **Karpathy Wiki parser** | UA | Niche feature; Obsidian adapter covers our knowledge use case |
| **Hook-based command rewriting** | rtk | MCP protocol is our integration layer; hooks are platform-specific |
| **Single binary distribution** | rtk | Docker image (Glama) already provides this; pip is our primary channel |
| **Persona-adaptive UI** | UA | We serve AI agents, not humans directly; rules engine is our "persona" system |

---

## Test Coverage Progress

| Version | Total Tests | Coverage | Key Addition |
|---------|-------------|----------|--------------|
| v0.3.0 (pre-reset) | 490 | 57.6% | Memory layer |
| v0.2.5 (pre-reset) | 746 | ~77% | +auto-promotion |
| v0.2.6 (pre-reset) | 793 | ~59% | +experience learning (new modules lower %) |
| v0.2.7 (pre-reset) | 884 | ~68% | +Q&A refinement + cleanup |
| v0.2.8 (pre-reset) | 1709 | ~81% | +Anchored injection +DDD view +security audit |
| v0.2.9 (pre-reset) | 1800+ | ~82% | +DevSquad integration adapter |
| v0.3.0 (pre-reset) | 1900+ | ~85% | +Knowledge CJK +relevance scoring |
| v0.4.0 (pre-reset) | 1814 | ~77% | +Rule Scopes +Skill Format +VS Code Extension |
| v0.4.1 (pre-reset) | 2056 | 79% | +Core Loop Fix +Auto Rule Suggestion +Security |
| **v0.2.5 (current)** | **3244 tests** | **79%+** | **+Recall Purity +Scope Injection +PrefEval **83.0%** +8-client MCP** |

---

## Security Strategy (Defense in Depth)

### Layer 1: Input Validation (v0.2.1 ✅)
- Prompt injection pattern detection (10+ patterns)
- SQL injection character blocking
- Template injection prevention
- HTML/XSS tag stripping
- Length limits (trigger: 200, action: 500)

### Layer 2: Usage Limits (v0.2.1 ✅)
- Global rule cap: max 3 trigger="*"
- Total rule cap: max 200
- Rate limiting: 20/hr, 50/day

### Layer 3: Auto-Promotion Safety (v0.2.5 ✅)
- Auto-promotion requires explicit user action
- All auto-generated rules start as `override=false`
- Unconfirmed candidates expire after 7 days
- Queue size limit (50 pending)

### Layer 4: Experience Learning Safety (v0.2.6 ✅)
- Duplicate memory detection (skip already-processed)
- Sanitizer validates all extracted triggers/actions
- Audit trail for all experience→rule actions

### Layer 5: Refinement Safety (v0.2.7 ✅)
- Max 5 rounds per session
- Session expiry (7 days)
- All refined rules go through sanitizer

### Layer 6: Context Engineering Safety (v0.2.8 ✅)
- Context budget monitoring prevents prompt overflow
- Anchored layout ensures critical rules are never lost-in-middle
- Compression strategy preserves override=true rules

### Layer 7: Knowledge Injection Safety (v0.3.0 PLANNED)
- Knowledge content length limits before injection
- Source vault path validation (no path traversal)
- Knowledge recall results sanitized through InputValidator

---

## Priority Matrix

| Feature | Impact | Effort | Priority | Version |
|---------|--------|--------|----------|---------|
| **Anchored layout mode** | **Critical** | **Low** | **P0** | **v0.2.8 ✅** |
| **DDD style output** | **High** | **Low** | **P0** | **v0.2.8 ✅** |
| **Context budget monitoring** | **High** | **Medium** | **P1** | **v0.2.8 ✅** |
| **Test coverage ≥ 80%** | **High** | **Medium** | **P1** | **v0.2.8 ✅** |
| **Obsidian CJK trigram search** | **High** | **Low** | **P0** | **v0.3.0** |
| **Knowledge relevance scoring** | **High** | **Medium** | **P0** | **v0.3.0** |
| **Three-layer retrieval orchestration** | **Critical** | **Medium** | **P0** | **v0.3.0** |
| **trigger_count activation** | **High** | **Low** | **P1** | **v0.3.0** |
| **Rule effectiveness metrics** | **Medium** | **Medium** | **P1** | **v0.3.0** |
| **source_memories confidence** | **Medium** | **Medium** | **P1** | **v0.3.0** |
| **Rules API Stable promotion** | **High** | **Low** | **P2** | **v0.3.0 ✅** |
| **TypedDict return types** | **Medium** | **Medium** | **P2** | **v0.3.0 ✅** |
| **Rule scope dimension** | **Critical** | **Medium** | **P0** | **v0.4.0** |
| **Scope-aware matching/injection** | **High** | **Medium** | **P0** | **v0.4.0** |
| **Skill manifest specification** | **High** | **Medium** | **P1** | **v0.4.0** |
| **Skill CLI commands** | **Medium** | **Medium** | **P1** | **v0.4.0** |
| **Rule merge protocol** | **High** | **High** | **P2** | **v0.4.0** |
| **VS Code extension** | **Medium** | **High** | **P3** | **v0.4.0** |
| **Ontology trigger matching** | **Medium** | **High** | **P3** | **v0.5.0** |
| **Community directory: mcp.directory ✅ + Glama ✅** | **High** | **Low** | **P1** | **v0.3.0** |
| **mcp-marketplace.io** | — | — | **Dropped** | Scanner rejects custom MCP impl (no SDK import) |
| **Smithery (requires .mcpb bundle or HTTP transport)** | **Medium** | **High** | **P2** | **v0.4.0** |
| **WorkBuddy/CodeBuddy internal MCP Market (requires Plugin format)** | **Medium** | **Medium** | **P2** | **v0.4.0** |
| **SSE/HTTP transport for MCP server** | **Critical** | **High** | **P2** | **v0.4.0** |
| **Cloud MCP Server** | **High** | **Very High** | **P2** | **v0.5.0** |

---

**Next Milestone**: v0.3.0 GA (General Availability)
**Status**: ✅ **v0.2.5 complete (3244 tests, 80%+ coverage, Memory + Rules + Knowledge + Enterprise)**

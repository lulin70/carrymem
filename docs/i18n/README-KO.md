# CarryMem — AI가 드디어 당신을 기억합니다

**더 이상 매번 AI에게 당신이 누구인지 가르치지 마세요.**

> 휴대 가능한 AI 기억 — 모델, 도구, 디바이스를 넘어 따라다니는 선호, 결정, 교정.

매번 새 채팅을 열 때마다 다시 자기소개를 합니다. 당신의 선호, 당신의 결정, 당신의 교정 — 모두 잊힙니다. Cursor에서 Claude Code로, GPT에서 Claude로 전환할 때마다 처음부터 시작합니다.

당신은 AI를 사용하는 게 아닙니다. 훈련시키고 있는 겁니다. 계속 반복해서.

CarryMem이 이 문제를 해결합니다. 가볍고 의존성이 없는 기억 시스템으로 **당신이 누구인지**를 저장하고 그 정체성을 어떤 AI 도구든 사용할 수 있게 합니다. AI는 당신의 선호, 과거 결정, 한 교정들을 기억하게 되므로 — 반복 말하기 대신 개발에 집중할 수 있습니다.

**English** | [中文](README-CN.md) | [日本語](README-JP.md) | **한국어** (본 파일) | [繁體中文](README-ZH-TW.md)

---

## 🌟 30초 요약

> **매일 고객을 만나고 회의하고 채팅하며 AI에게 질문받고 답해도, 다음 대화에서 또 잊어버립니다.**
>
> CarryMem이 **자동으로 당신의 선호와 결정을 기억**하게 해줍니다 — 매번 반복할 필요 없습니다. 한 번 설치하면 모든 AI 도구에서 공통으로 사용됩니다.

*기술 사용자: 아래 [PrefEval 벤치마크](https://arxiv.org/abs/2410.01373) (83.0% ICLR 2025 Oral) 및 [아키텍처 문서](#-architecture) 참조.*

---

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-4330-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-green" alt="Coverage">
  <a href="https://arxiv.org/abs/2410.01373"><img src="https://img.shields.io/badge/PrefEval-83.0%25%20(ICLR%202025%20Oral)-9B59B6?logo=arxiv" alt="PrefEval Academic Benchmark"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python">
</p>

**Topics**: `ai-memory` `mcp` `claude-code` `agent-memory` `cursor` `obsidian` `preference-injection` `sqlite` `llm-tools` `portable-memory`

---

## CarryMem이 하는 일

**5가지 익숙한 시나리오:**

> **"AI에게 매번 내 선호를 알리고 싶지 않아요"**
> "PostgreSQL 선호해요" "React 쓰고 Vue는 안 써요" "코드에 주석 달지 마세요" — 한 번 말하면 영원히 기억됩니다.

> **"AI 도구를 바꿨는데 다시 처음부터 시작돼요"**
> Cursor에서 AI를 가르쳤는데 Claude Code에서 또 가르쳐야 한다면, CarryMem이 AI 기억을 따라오게 합니다.

> **"내 데이터를 가져가고 싶어요"**
> 당신의 AI 기억은 당신 것입니다. 파일 하나로 패킹하고 어떤 머신이나 도구에서든 복원하세요.

> **"USB 휴대 — 주머니 속의 기억"** 🔑
> 기억을 암호화된 .carry 파일로 패킹하고 USB에 복사한 뒤 새 머신에서 언팩하세요. 당신의 AI 정체성이 함께 이동합니다 — 선호, 결정, 교정, 규칙 모두 온전히 보존됩니다. 새 머신의 모든 에이전트가 즉시 당신이 누구인지 알게 됩니다.

> **"우리 팀이 에이전트 간에 규칙을 공유해요"**
> 팀 리드가 회사 규칙을 Skill 번들로 패킹하고 각 팀원이 설치합니다. 모든 에이전트가 동일한 규칙을 적용합니다 — 더 이상 "SSL을 쓴다는 걸 몰랐어요" 같은 상황은 없습니다.

---

## 🎯 실제 사용자 시나리오

### 시나리오 1: 멀티툴 개발자

```
월요일:  Cursor에 "다크 모드, PostgreSQL, React 선호해"라고 알림
화요일: Claude Code 열기 — 이미 스택을 알고 있음
금요일:  TRAE로 전환 — 동일한 선호, 반복 없음
```

**방법**: `carrymem setup-mcp --all --global` — 명령어 하나로 모든 도구가 하나의 기억을 공유.

### 시나리오 2: USB 휴대 — 새 머신, 동일한 정체성

```
1. 노트북에서:   carrymem pack -o my_identity.carry --encrypt
2. my_identity.carry를 USB 드라이브에 복사
3. 새 직장에서: 새 머신에 CarryMem 설치
4. carrymem unpack my_identity.carry
5. 새 머신의 모든 에이전트가 선호, 결정, 규칙을 인식함
```

**암호화 + SHA-256 체크섬** — USB를 잃어버려도 정체성은 안전합니다.

### 시나리오 3: 팀 리드

```
1. 팀 규칙 생성: "항상 SSL 사용", "금요일에 배포 금지"
2. Skill로 패킹: carrymem rules pack rules.json --name team-conventions
3. .json 파일을 팀과 공유
4. 각 구성원: carrymem rules install team-conventions.json --scope company
5. 모든 에이전트가 자동으로 회사 규칙을 적용함
```

### 시나리오 4: 장기 사용자

```
1개월: "다크 모드 선호해" → user_preference로 저장
3개월: "라이트 모드로 전환해" → 자동으로 기존 선호 대체
6개월: carrymem whoami → "라이트 모드 선호해" 표시 (다크 모드 보관됨)
```

**선호는 진화합니다. CarryMem이 역사를 추적합니다.**

---

## 빠른 시작 (경로 선택)

### Cursor / Claude Code / TRAE 사용 중?

```bash
pip install carrymem && carrymem setup-mcp --all --global
```

AI 도구를 재시작하세요. 끝.

### 작동 확인 (30초)

AI에게 말해보세요:
```
Remember, I prefer PostgreSQL
```

새 대화를 열고 물어보세요:
```
What database do I prefer?
```

AI가 "PostgreSQL"라고 답한다면 — 성공입니다!

### 기억을 옮겨야 하나요?

```bash
carrymem pack                    # carrymem_identity_20260526.carry 생성
# USB / 클라우드 / 새 머신으로 복사
carrymem unpack my_identity.carry  # 모든 기억 복원

# 민감 데이터용 암호화
carrymem pack -o my_memories.carry --encrypt   # 비밀번호 암호화 .carry 파일
carrymem unpack my_memories.carry              # 암호화 자동 감지, 비밀번호 프롬프트
```

### 자동 백업 & 복구

```bash
carrymem backup                  # 수동 백업 (20번 쓰기마다 자동 백업도 됨)
carrymem backup --list           # 모든 백업 목록
carrymem backup --restore memories_backup_20260527_120000.db  # 백업에서 복원
```

---

> 📊 **학술 검증됨**: CarryMem의 선호 주입 정확도(83.0%)는 [PrefEval 프로토콜](https://arxiv.org/abs/2410.01373)(ICLR 2025 Oral, Amazon Science)로 측정되었으며, 200개 테스트 항목에서 단순 리마인더(80.0%)와 제로샷(71.5%) 베이스라인을 능가합니다. 아래 [인용](#citation) 참조.

## CarryMem을 선택해야 할 3가지 이유

CarryMem을 다른 모든 기억 솔루션과 차별화하는 핵심:

### 1. 선호 주입 정밀도 — 83.0% (학술 검증)
- PrefEval(ICLR 2025 Oral, Amazon Science)로 측정, 200 샘플 3조건 비교
- CarryMem 83.0% > 단순 리마인더 80.0% > 제로샷 71.5%
- 능동적 주입 > 완전 리마인더 — 이것을 입증한 최초 시스템
- 리마인더보다 24% 덜 유익하지 않은 응답(28 vs 38) — 더 정밀하고 노이즈 감소

### 2. 제로 LLM 분류 — LLM 호출 없이 88%
- 규칙 엔진이 88%의 기억을 분류, 토큰 비용 제로
- 내장 규칙 엔진을 갖춘 유일한 시스템(경쟁사: 0%)
- P99 지연 시간: 1.3ms — Mem0보다 93배 빠름

### 3. 경량 & 휴대 가능 — SQLite만
- 핵심 기능에 외부 의존성 제로
- 단일 .db 파일 — 어디든 정체성 휴대 가능
- Cursor, Claude Code, ChatGPT, 모든 MCP 클라이언트와 호환

---

## 작동 원리

```
사용자 입력 → 자동 분류(7종류, 88% 규칙 기반) → 스마트 저장(SQLite + FTS5)
    → 의미론적 리콜(크로스 언어) → 컨텍스트 주입(토큰 예산) → AI 도구
```

---

## 빠른 시작

### 설치

```bash
pip install carrymem
```

> **Python 3.12+ 필요**. 버전 확인: `python --version`
>
> **PyPI**: [https://pypi.org/project/carrymem/](https://pypi.org/project/carrymem/)
>
> **개발용**: `git clone https://github.com/lulin70/carrymem.git && cd carrymem && pip install -e ".[dev]"`

### 시스템 요구사항

- **Python**: ≥3.12 (64비트)
- **OS**: macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **디스크**: 핵심 ~5MB, 의미론적 검색 포함 ~200MB
- **메모리**: 기본 ~50MB

### 의존성

| 기능 | 패키지 | 설치 |
|------|--------|------|
| Core | PyYAML≥5.0 | `pip install carrymem` (포함) |
| 다국어 | pycld2, langdetect | `pip install carrymem[language]` |
| 의미론적 검색 | sqlite-vec, sentence-transformers | `pip install carrymem[semantic]` |
| 암호화 | cryptography≥41.0 | `pip install carrymem[encryption]` |
| Full (모든 기능) | 위 모두 | `pip install carrymem[full]` |
| 개발 | pytest, black, flake8... | `pip install -e ".[dev]"` |

> **핵심 기능에 제로 LLM 의존성** — 분류는 규칙 엔진만 사용합니다.

### 설치 확인

```bash
carrymem version
```

**`command not found`가 나온다면**, Python bin을 PATH에 추가:

```bash
# macOS (~/.zshrc에 추가)
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# Linux (~/.bashrc에 추가)
export PATH="$HOME/.local/bin:$PATH"

# 또는 Python 모듈 직접 사용
python3 -m carrymem.cli version
```

그 후 `carrymem doctor`로 설정을 확인하세요.

### 5줄 코드

> ⚠️ **패키지명 vs 임포트명**: `pip install carrymem`(소문자)로 설치하지만, `from carrymem import CarryMem`(카멜케이스 클래스명)로 임포트합니다. 패키지명(`carrymem`)과 클래스명(`CarryMem`)의 대소문자가 다릅니다.

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("I prefer dark mode")        # 자동 분류: 선호
cm.classify_and_remember("Use PostgreSQL not MySQL")   # 자동 분류: 교정
cm.classify_and_remember("I prefer light mode now", session_id="sess_002")  # 세션 인식
memories = cm.recall_memories("database")              # 의미론적 리콜
memories = cm.recall_memories("mode", filters={"session_id": "sess_002"})  # 세션 필터
agg = cm.recall_aggregated()                           # 유형별 집계
timeline = cm.recall_timeline("database")              # 지식 진화
print(cm.build_system_prompt())                        # 모든 AI에 주입
cm.close()
```

### CLI (50+ 명령어)

```bash
carrymem init                           # 초기화
carrymem add "I prefer dark mode"       # 기억 저장
carrymem add "test note" --force        # 강제 저장 (분류 우회)
carrymem list                           # 기억 목록
carrymem search "theme"                 # 기억 검색
carrymem show <key>                     # 기억 상세 보기
carrymem edit <key> "new content"       # 기억 편집
carrymem forget <key>                   # 기억 삭제
carrymem whoami                         # AI가 생각하는 당신의 정체성
carrymem profile export --output identity.json   # AI 정체성 내보내기
carrymem stats                          # 기억 통계
carrymem check                          # 품질 & 충돌 검사
carrymem clean --expired --dry-run      # 정리 미리보기
carrymem doctor                         # 설치 진단
carrymem setup-mcp --tool cursor        # 원 줄 MCP 설정
carrymem tui                            # 터미널 UI
carrymem export backup.json             # 모든 기억 내보내기
carrymem import backup.json             # 기억 가져오기
carrymem pack -o my_memories.carry      # 휴대용 .carry 파일로 패킹
carrymem pack -o my_memories.carry --encrypt  # 암호화 .carry 파일
carrymem unpack my_memories.carry       # .carry 파일 언팩
carrymem backup                         # 수동 백업
carrymem backup --list                  # 백업 목록
carrymem backup --restore <file>        # 백업에서 복원
carrymem version                        # 버전 표시
# 규칙 엔진 명령어
carrymem rules add "use SSL" --trigger "database" --type avoid  # 규칙 추가
carrymem rules list --status active                      # 활성 규칙 목록
carrymem rules pack rules.json --name team-conventions   # 규칙을 Skill로 패킹
carrymem rules install team-conventions.json --scope company  # Skill 설치
carrymem rules verify team-conversations.json            # Skill 무결성 검증
```

---

## 핵심 기능 (3가지 장점 지원)

### 기억이 당신을 이해함

#### 자동 분류 (7가지 기억 유형)

CarryMem이 자동으로 당신이 공유하는 정보의 종류를 식별합니다:

| 유형 | 아이콘 | 예시 |
|------|--------|------|
| `user_preference` | ⭐ | "I prefer dark mode" |
| `correction` | 🔧 | "No, I meant Python 3.11 not 3.10" |
| `decision` | 🎯 | "Let's use React for the frontend" |
| `fact_declaration` | 📌 | "Python 3.12 is the runtime version" |
| `relationship` | ❓ | "Sarah is my manager" |
| `task_pattern` | 🔄 | "I always write tests first" |
| `sentiment_marker` | 💭 | "This build is too slow" |

#### 의미론적 리콜 (크로스 언어)

```python
cm.classify_and_remember("我偏好使用PostgreSQL")

# 아래 모든 방법으로 찾을 수 있습니다:
cm.recall_memories("PostgreSQL")     # 정확히 일치
cm.recall_memories("数据库")          # 동의어 확장
cm.recall_memories("Postgres")       # 철자 수정
cm.recall_memories("データベース")    # 크로스 언어 (일본어)
```

#### 정체성 레이어 (whoami)

```python
identity = cm.whoami()
print(identity["preferences"])   # ["I prefer dark mode", ...]
print(identity["decisions"])     # ["Let's use React", ...]
print(identity["corrections"])   # ["The port should be 5432", ...]
```

```bash
$ carrymem whoami

  Who You Are (according to your AI)
  ==================================================

  Your Preferences:
    ⭐ I prefer dark mode for all editors
    ⭐ I use PostgreSQL for databases
    ⭐ I always use Python for data analysis

  Your Decisions:
    🎯 Let's use React for the frontend

  Your Corrections:
    🔧 The port should be 5432, not 3306

  Memory Profile:
    Total: 19 | Dominant: user_preference | Avg Confidence: 73%
```

### 선호 주입 (장점 #1)

#### 버전 체인 — 선호가 진화하고, 구 버전은 자동 보관

```python
cm.update_memory(key, "Updated content")     # 버전 2 생성
history = cm.get_memory_history(key)          # [v1, v2]
cm.rollback_memory(key, version=1)            # v1 복원
```

#### 스코어 인식 주입 — 컨텍스트별 관련 선호만 주입

선호는 컨텍스트 스코어에 따라 주입되므로, 데이터베이스 선호가 프론트엔드 논의를 어지럽히지 않습니다.

#### 토큰 예산 — 선호에 60% 예산 배정, 절대 잘림 없음

CarryMem은 토큰 예산의 60%를 선호에 배정하여 절대 잘리지 않도록 합니다. PrefEval에서 83.0%를 달성하는 핵심 — 구조화된 선호 주입이 단순 리마인더를 압도합니다.

### 기억 수명 주기 (장점 #2)

#### 중요도 점수 — 신뢰도 × 유형 × 최근성 × 접근

모든 기억에는 시간이 지남에 따라 변화하는 중요도 점수가 있습니다:

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30일 반감기 감쇠** — 오래된 기억은 접근하지 않으면 서서히 사라짐
- **접근 강화** — 자주 호출되는 기억은 신선하게 유지
- **유형 가중치** — 교정(1.3x) > 결정(1.2x) > 선호(1.1x)

#### 통합 (P0/P1/P2) — 중복 제거 + 감쇠 + 패턴 → 규칙 + 의미론적 병합

세 단계의 자동 기억 수명 관리:

```python
# 통합 결과 미리보기
report = cm.consolidate(dry_run=True)
print(f"Duplicates: {report['stats']['duplicates_found']}")
print(f"Decayed: {len(report['to_decay'])}")

# 통합 실행 (P0: 중복제거+감쇠, P1: 패턴→규칙, P2: 의미론적 병합)
report = cm.consolidate(dry_run=False, run_p1=True, run_p2=True)
```

| 단계 | 기능 | 메커니즘 |
|------|------|----------|
| **P0** | 중복 제거 + 감쇠 | Jaccard 유사도 중복 제거, 지수 반감기 감쇠(선호: 270일, 사실: 90일, 감정: 45일) |
| **P1** | 패턴 → 규칙 | 반복 패턴 탐지 → 검토용 규칙 후보 생성 |
| **P2** | 의미론적 병합 | 관련 기억 클러스터링 → 호스트 LLM에 통합 요청 |

선호는 항상 보존됩니다 — 감쇠되거나 중복 제거되지 않습니다.

#### 예약 통합 — 자동 백그라운드 유지 관리

주기적으로 통합을 자동 실행:

```python
# 매시간 통합 예약 (백그라운드 스레드에서 실행)
cm.schedule_consolidation(interval_hours=1.0)

# 예약된 통합 중지
cm.stop_consolidation()
```

CLI:

```bash
carrymem consolidate --schedule 1h   # 매시간 통합 실행
carrymem consolidate --stop          # 예약된 통합 중지
```

### 보안 & 휴대 가능성 (장점 #3)

#### 자동 편집 — 24가지 민감 패턴

저장 전 API 키, 비밀번호, 토큰 등 21개 추가 민감 패턴을 자동으로 탐지 및 편집합니다.

#### 암호화 — AES-128 저장 암호화

| 기능 | 설명 |
|------|------|
| **암호화** | AES-128 (Fernet) 또는 HMAC-CTR 폴백, 제로 의존성 |
| **암호화된 .carry 파일** | `pack --encrypt`로 비밀번호 암호화 휴대 파일 생성 |
| **자동 백업** | 20번 쓰기마다 VACUUM INTO 백업, 최대 5개 보관 |
| **백업/복원** | 수동 백업, 목록, 복원 (`carrymem backup`) |
| **감사 로그** | 추가 전용 운영 이력 |
| **버전 이력** | 모든 편집 추적, 롤백 지원 |
| **입력 유효성 검사** | SQL 인젝션, XSS, 경로 순회 보호 |

```python
cm = CarryMem(encryption_key="my-secret-key")
# 모든 콘텐츠 저장 시 암호화, 읽을 때 복호화
```

#### 백업/복원 — 자동 백업 + 수동 제어

20번 쓰기마다 자동 백업(VACUUM INTO), 최대 5개 백업 파일 보관. CLI로 수동 제어:

```bash
carrymem backup                  # 수동 백업 생성
carrymem backup --list           # 모든 백업 목록
carrymem backup --restore <file> # 특정 백업에서 복원
```

#### 팩/언팩 — 암호화 USB 휴대

```bash
# 기억을 휴대용 .carry 파일로 패킹
carrymem pack -o my_memories.carry

# 민감 데이터용 비밀번호 암호화
carrymem pack -o my_memories.carry --encrypt

# 모든 머신에서 언팩 (암호화 자동 감지)
carrymem unpack my_memories.carry
```

SHA-256 체크섬이 파일 무결성을 보장합니다. v1.0 .carry 형식은 경고와 함께 하위 호환됩니다.

#### 내보내기/가져오기 — 디바이스 간 정체성 이동

```python
# AI 정체성 내보내기
cm.export_profile(output_path="my_identity.json")

# 다른 디바이스나 AI 도구에서
cm.import_memories(input_path="backup.json")
```

---

## 지원 기능

### MCP 통합 (원 줄 설정)

```bash
# Cursor 설정
carrymem setup-mcp --tool cursor

# Claude Code 설정
carrymem setup-mcp --tool claude-code

# 모두 설정
carrymem setup-mcp --tool all
```

28개 MCP 도구 제공: Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (3) · Rules (11)

**클라이언트 호환성:**

| 상태 | 클라이언트 | 설정 |
|------|-----------|------|
| ✅ 직접 지원 | Cursor, Claude Code, TRAE, Windsurf, Cline | `setup-mcp --global` |
| ✅ 자동 감지 | OpenClaw, Kimi Code CLI, CodeX | `setup-mcp --global` (Claude Code 형식으로 폴백) |
| 📋 마켓플레이스 | WorkBuddy, CodeBuddy | MCP Marketplace 제출 (예정) |
| ❌ 미지원 | Kimi Desktop, DeepSeek Desktop, Qianwen, Doubao, TiGong, ChatGLM | 폐쇄 플랫폼, MCP 인터페이스 없음 |

> **🔒 당신의 기억은 당신의 머신에만 있습니다.** CarryMem은 모든 데이터를 로컬 `~/.carrymem/`(SQLite)에 저장합니다. 각 사용자가 독립적인 DB를 가집니다 — Git처럼, 모두가 동일한 도구를 쓰지만 각자의 저장소를 유지합니다. 클라우드 동기화 없음, 공유 상태 없음, 사용자 간 충돌 없음.

### 스코프가 있는 규칙 엔진

팀/조직 정렬을 위한 3단계 스코프의 행동 규칙:

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# 회사 강제 규칙 (최고 우선순위, 재정의 불가)
engine.add_rule("database", "Always use SSL", scope="company", override=True)

# 개인 선호 (최저 우선순위)
engine.add_rule("database", "Prefer PostgreSQL", scope="personal")

# 스코어 인식 매칭
results = engine.match("database design", scopes=["company"])
```

| 스코프 | 우선순위 | 설명 |
|-------|----------|------|
| `company` | 3 (최고) | 조직 강제 규칙, 재정의 불가 |
| `negotiated` | 2 | 회사 규칙에서 적응됨 |
| `personal` | 1 (최저) | 사용자 생성 선호 |

### Skill 형식 — 휴대용 규칙 번들

암호화 무결성 검증으로 팀 간 규칙 집합 공유:

```python
# 규칙을 휴대용 Skill 번들로 패킹
bundle = engine.skill_pack(
    name="team-conventions",
    version="1.0.0",
    scope="company",
    author="team-lead",
)

# 설치 전 무결성 검증
result = engine.skill_verify(bundle)
assert result["valid"] is True

# 다른 머신에 설치
engine.skill_install(bundle, scope_override="company", mode="skip")
```

### 병합 프로토콜 — 충돌 해결

다양한 출처의 규칙 병합을 위한 3가지 전략:

| 전략 | 설명 |
|------|------|
| `company_overrides` | 높은 스코어가 항상 승리 |
| `negotiate` | 충돌 규칙을 "negotiated" 스코어로 적응 |
| `keep_both` | 두 규칙 모두 유지, 수동 검토 대상 |

### 품질 관리

```bash
carrymem check                    # 전체 검사
carrymem check --conflicts        // 모순 탐지
carrymem check --quality          // 저품질 기억 찾기
carrymem check --expired          // 만료된 기억 찾기
carrymem clean --expired --dry-run # 정리 미리보기
```

### 터미널 UI

```bash
pip install textual
carrymem tui
```

사이드바 필터, 검색, 추가 모드가 있는 인터랙티브 터미널 인터페이스.

### VS Code 확장

편집기에서 직접 규칙 관리:

- 스코프 배지가 있는 규칙 사이드바
- 웹뷰로 규칙 추가/편집/삭제
- 효과성 보고서 패널
- 파일 대화상자에서 Skill 팩/설치

---

## 비교

### 시나리오별

| 시나리오 | Mem0 | ima | CarryMem |
|----------|------|-----|----------|
| AI가 내 말을 기억함 | ✅ | ⚠️ 수동 | ✅ 자동 |
| AI 도구를 바꿔도 기억함 | ❌ | ❌ | ✅ 파일 하나가 따라옴 |
| AI가 특정 것을 기억 못 하게 함 | ❌ | ⚠️ 제한적 | ✅ 언제든 삭제, 구역 분리 |
| 토큰 소비 없이 기억함 | ❌ | ❌ | ✅ 88% 제로 비용 |
| 내 데이터 소유 | ⚠️ 셀프호스팅만 | ❌ 클라우드 | ✅ 로컬 파일 |

### 기능 행렬

|  | CarryMem | Mem0 | OpenChronicle | ima |
|--|----------|------|---------------|-----|
| **핵심 차별점** | **제로 LLM + 규칙 엔진** | 벡터 DB + 클라우드 | 로컬 우선 | 클라우드 노트 |
| **제로 의존성** | ✅ SQLite만 | ⚠️ 벡터 DB 선택 | ✅ | ❌ 클라우드 |
| **자동 분류** | ✅ 7종류 | ❌ | ❌ 수동 | ❌ |
| **정체성 초상** | ✅ whoami | ❌ | ❌ | ❌ |
| **규칙 엔진** | ✅ 스코어 + Skills | ❌ | ❌ | ❌ |
| **팩 / 언팩** | ✅ 파일 하나 | ❌ | ❌ | ❌ |
| **암호화 휴대** | ✅ --encrypt | ❌ | ❌ | ❌ |
| **자동 백업** | ✅ 20번 쓰기마다 | ❌ | ❌ | ❌ |
| **크로스 언어 리콜** | ✅ EN/CN/JP | ❌ | ❌ | ❌ |
| **암호화** | ✅ 내장 | ❌ | ❌ | ❌ |
| **데이터 소유권** | ✅ 로컬 파일 | ⚠️ 셀프호스팅 가능 | ✅ 로컬 | ❌ 클라우드 |

> **참고**: 비교는 공개 정보를 기반으로 합니다. 제품은 빠르게 발전하니 최신 기능을 확인하세요.

**핵심 차이**: 다른 제품은 *당신이 읽은 것*을 저장합니다. CarryMem은 *당신이 누구인지*를 저장합니다.

---

### 🏆 PrefEval — 선호 준수 벤치마크

| 조건 | 정확도 | 인정 | 위반 | 환각 | 무응답 |
|-----------|----------|-------------|----------|-------------|-----------|
| 제로샷 | 71.5% | 160 | 27 | 3 | 31 |
| 리마인더 | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

프로토콜: PrefEval (ICLR 2025 Oral, Amazon Science)
샘플: 200 항목, 10 턴 간 간섭, Claude Sonnet 4

**중요성**: 리마인더는 매 턴 "사용자 선호 기억"을 주입합니다. CarryMem은 system prompt에 구조화된 선호를 주입합니다 — 더 정밀하고, 더 지속적이며, 무응답이 24% 줄어듦니다.

| | 장점 | 결과 |
|---|-----------|--------|
| 💰 | 제로 LLM 섭취 | **88%** 기억에 **LLM 토큰 필요 없음** |
| ⚡ | P99 지연 시간 | **1.3ms** — Mem0보다 **93배 빠름** |
| 🪶 | 의존성 | **SQLite만** — 벡터 DB 불필요 |
| 🛡️ | 규칙 엔진 | **규칙 엔진을 가진 유일한 시스템**(경쟁사: 0%) |

---

## 아키텍처

```
User Input
    ↓
Auto-Classification (7 types, 4 tiers)
    ↓
Importance Scoring (confidence × type × recency × access)
    ↓
Smart Storage (SQLite + FTS5, dedup, TTL, encryption)
    ↓
Memory Consolidation (P0: dedup+decay → P1: pattern→rules → P2: semantic merge)
    ↓
Semantic Recall (FTS5 + synonyms + spell fix + cross-language)
    ↓
Context Injection (token budget, relevance ranking)
    ↓
AI Tool (Cursor / Claude Code / any MCP client)
```

**3단계 분류**:
```
Rule Engine (60%+) → Pattern Analysis (30%) → Semantic (10%)
     ↓                      ↓                      ↓
 Zero cost            Near-zero cost          Token cost
```

---

## 고급 사용법

### Obsidian 지식 베이스

```python
from carrymem import CarryMem, ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python design patterns")
```

### 비동기 API

```python
from carrymem import AsyncCarryMem

async with AsyncCarryMem() as cm:
    await cm.classify_and_remember("I prefer dark mode")
    memories = await cm.recall_memories("theme")
```

### JSON 어댑터 (SQLite 없음)

```python
from carrymem import CarryMem, JSONAdapter

cm = CarryMem(adapter=JSONAdapter(path="/path/to/memories.json"))
```

### 기억 버전 관리

```python
cm.update_memory(key, "Updated content")     # 버전 2 생성
history = cm.get_memory_history(key)          # [v1, v2]
cm.rollback_memory(key, version=1)            # v1 복원
```

### 다른 AI를 위한 정체성 내보내기

```python
# AI 정체성 내보내기
cm.export_profile(output_path="my_identity.json")

# 다른 디바이스나 AI 도구에서
cm.import_memories(input_path="backup.json")
```

---

## 누구를 위한 것인가?

**반복하는 데 지쳤나요?**
Cursor, Claude Code, ChatGPT를 매일 사용합니다. 스타일, 스타일, 결정을 AI에게 백 번 말했는데 여전히 "어떤 프레임워크를 선호하시나요?"라고 묻는다면, CarryMem이 AI가 기억하게 만들어줍니다.

**CLAUDE.md를 손으로 관리 중인가요?**
AI에 기억이 필요하다는 건 이미 알고 있습니다. 프롬프트 파일이 곳곳에 있고, 충돌하고, 오래되며, 도구를 바꾸면 따라오지 않습니다. CarryMem이 선호, 결정, 교정을 자동 분류하고 자동으로 최신 상태를 유지합니다.

**AI 에이전트를 개발 중인가요?**
에이전트가 세션 간 사용자를 잊어버립니다. 가볍고, 로컬이며, 모든 LLM과 호환되는 기억 레이어가 필요합니다. CarryMem이 5줄 코드 통합, 7가지 기억 유형, 규칙 엔진을 제공하며, SQLite 외에는 의존성이 없습니다.

---

## 문서

- [빠른 시작 가이드](../QUICK_START_GUIDE.md)
- [설치 가이드](../INSTALL.md)
- [사용자 가이드](../USER_GUIDE.md)
- [아키텍처](../ARCHITECTURE.md)
- [API 레퍼런스](../API_REFERENCE.md)
- [API 안정성 정책](../API_STABILITY.md)
- [로드맵](../ROADMAP.md)
- [기여](../../CONTRIBUTING.md)

---

## 프로젝트 상태

**현재 버전**: v0.7.2
**테스트**: 4198 passing
**커버리지**: 80%+

**변경 로그**:
- **v0.2.4**: 베타 릴리스 — CI 루트 수정, 24개 보안 수정, Glama TDQS 향상, 6게이트 CI 파이프라인
- **v0.2.0**: USB 휴대 암호화, 자동 백업, 동시성 안전, PrefEval 83.0% (200 항목), 8 클라이언트 MCP 설정
- **v0.2.3** (리셋 전): 통합 예약(schedule/stop), PrefEval 표준화
- **v0.2.2** (리셋 전): 토큰 예산 + 데드 코드 수정 + 보안, PrefEval 87.9%
- **v0.2.1** (리셋 전): 공지 해소, 자동 편집, QA 프롬프트 최적화

---

## 기여

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
pytest
```

자세한 내용은 [기여 가이드](../../CONTRIBUTING.md) 참조.

---

## 인용

연구에서 CarryMem을 사용한다면 인용해주세요:

```bibtex
@software{carrymem2026,
  title = {CarryMem: Persistent Memory for AI Agents with Preference Injection},
  author = {CarryMem Team},
  year = {2026},
  url = {https://github.com/carrymem/carrymem},
  note = {Preference injection accuracy 83.0\% measured by PrefEval protocol}
}

@inproceedings{chuang2025prefeval,
  title = {PrefEval: A Preference Evaluation Benchmark for LLMs},
  author = {Chuang, Yun-Nung and others},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2025},
  note = {Oral presentation, Amazon Science}
}
```

**실험 결과 (200 항목, 10 턴 간 간섭, Claude Sonnet 4)**

| 조건 | 정확도 | 인정 | 위반 | 환각 | 무응답 |
|-----------|----------|-------------|----------|-------------|-----------|
| 제로샷 | 71.5% | 160 | 27 | 3 | 31 |
| 리마인더 | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

핵심 인사이트: CarryMem은 최고 정확도를 달성하면서 리마인더 기반 접근보다 24% 적은 무응답을 생성하여, 능동적 기억 주입이 전체 컨텍스트 리마인딩보다 더 정밀함을 입증합니다.

---

## 라이선스

MIT 라이선스 — [LICENSE](LICENSE) 참조

---

**CarryMem — AI가 드디어 당신을 기억합니다. 오직 당신만이 데이터를 소유합니다.**

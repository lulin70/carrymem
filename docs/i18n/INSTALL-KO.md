# CarryMem 설치 가이드

## 시스템 요구사항

- **Python**: ≥3.12 (64비트)
- **OS**: macOS, Linux, Windows (WSL2 권장)
- **디스크**: 패키지 약 10MB, 데이터베이스당 약 1MB
- **선택 사항**: Node.js 18+ (VS Code 확장용)

## 설치 방법

### 1. PyPI (권장)

```bash
pip install carrymem
```

설치 확인:
```bash
carrymem version
```

**`carrymem: command not found`가 나오면**, pip 스크립트 디렉토리가 PATH에 없습니다. 수정 방법:

**macOS**:
```bash
# Python bin 디렉토리 찾기
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"

# PATH에 추가 (이 줄을 ~/.zshrc에 추가)
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# 다시 로드
source ~/.zshrc

# 확인
carrymem version
```

**Linux**:
```bash
# PATH에 추가 (이 줄을 ~/.bashrc에 추가)
export PATH="$HOME/.local/bin:$PATH"

# 다시 로드
source ~/.bashrc

# 확인
carrymem version
```

**대안 (어디서든 동작)**:
```bash
python3 -m carrymem.cli version
```

> ⚠️ **패키지명 vs 임포트명**: `pip install carrymem`로 설치하고, `from carrymem import CarryMem` 또는 `from carrymem import CarryMem`로 임포트합니다.

### 2. 개발 모드 설치

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
```

테스트 실행:
```bash
pytest
```

### 3. VS Code 확장

```bash
cd extensions/vscode-carrymem
npm install
npm run compile
```

그 후 VS Code에서: Extensions → "VSIX에서 설치" 또는 F5를 눌러 디버그 모드로 실행.

## 설정

### 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `CARRYMEM_DB_PATH` | `~/.carrymem/memories.db` | 데이터베이스 파일 경로 |
| `CARRYMEM_ENCRYPTION_KEY` | None | Fernet 암호화 키 |

### VS Code 설정

```json
{
  "carrymem.dbPath": "~/.carrymem/memories.db",
  "carrymem.autoMatch": false,
  "carrymem.defaultScope": "personal"
}
```

## 검증

설치 검증 테스트 스위트 실행:

```bash
python -m pytest tests/test_rules/test_installation.py -v
```

다음을 검증합니다:
- 모든 모듈을 임포트할 수 있음
- 버전 번호가 올바름
- 데이터베이스가 scope 지원으로 초기화됨
- CLI skill 명령어가 등록되었음
- VS Code 확장 파일이 존재함
- 전체 수명 주기 스모크 테스트 통과

## 문제 해결

### "Module not found: carrymem"

PyPI 패키지명은 `carrymem`이고, 임포트명도 `carrymem`입니다:
```python
from carrymem import CarryMem  # 정상
from carrymem import CarryMem  # 오류
```

### "carrymem command not found"

`~/.local/bin`(또는 동일한 경로)이 PATH에 있는지 확인:
```bash
pip install --user carrymem
export PATH="$HOME/.local/bin:$PATH"
```

### 데이터베이스 권한 오류

데이터베이스 디렉토리에 쓰기 권한이 있는지 확인:
```bash
mkdir -p ~/.carrymem
chmod 755 ~/.carrymem
```

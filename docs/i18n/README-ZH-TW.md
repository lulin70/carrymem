# CarryMem — 你的 AI 終於認識你了

**別再一遍遍教 AI 你是誰了。**

> 你的隨身 AI 記憶 — 偏好、決策和糾正，跨模型、跨工具、跨裝置隨身攜帶。

[English](../../README.md) | [简体中文](README-CN.md) | [日本語](README-JP.md) | [한국어](README-KO.md) | **繁體中文** (本檔案)

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI 版本"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-4322-brightgreen" alt="測試">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-green" alt="覆蓋率">
  <a href="https://arxiv.org/abs/2410.01373"><img src="https://img.shields.io/badge/PrefEval-83.0%25%20(ICLR%202025%20Oral)-9B59B6?logo=arxiv" alt="PrefEval 學術基準"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python">
</p>

---

## CarryMem 做什麼

**5 個你一定遇到過的場景：**

> **"不想每次都告訴 AI 我的偏好"**
> "我偏好 PostgreSQL""用 React 不用 Vue""別寫註解" — 說一次，永遠記住。

> **"換了 AI 工具又要從頭開始"**
> Cursor 裡教 AI 一遍，Claude Code 裡又教一遍。CarryMem 讓你的 AI 記憶跟著你走。

> **"想帶走自己的資料"**
> 你的 AI 記憶是你的。一個檔案打包，新機器、新工具，隨時還原。

> **"USB 攜帶——口袋裡的記憶"** 🔑
> 打包記憶為加密 .carry 檔案，拷到 USB 隨身碟，新機器解包。你的 AI 身份隨身攜帶——偏好、決策、糾正和規則完整保留。新機器上的每個 Agent 立刻認識你。

> **"我的團隊在所有 Agent 上共享規範"**
> 團隊負責人把公司規範打包為 Skill 包，每個成員安裝。所有 Agent 自動執行相同規範——不再有"我不知道我們用 SSL"。

---

## 🎯 真實使用者情境

### 情境 1：多工具開發者

```
週一：告訴 Cursor "我偏好深色模式、PostgreSQL、React"
週二：打開 Claude Code — 它已經知道你的技術堆疊
週五：切換到 TRAE — 同樣的偏好，零重複
```

**方法**：`carrymem setup-mcp --all --global` — 一條指令，所有工具共享一份記憶。

### 情境 2：USB 攜帶——新機器，同一身份

```
1. 在你的筆電上：carrymem pack -o my_identity.carry --encrypt
2. 將 my_identity.carry 拷貝到 USB 隨身碟
3. 在新工作場所：在新機器上安裝 CarryMem
4. carrymem unpack my_identity.carry
5. 新機器上的每個 Agent 都知道你的偏好、決策和規則
```

**加密 + SHA-256 校驗** — 即使 USB 隨身碟遺失，你的身份也是安全的。

### 情境 3：團隊負責人

```
1. 建立團隊規範為規則：「始終使用 SSL」「絕不在週五部署」
2. 打包為 Skill：carrymem rules pack rules.json --name team-conventions
3. 與團隊分享 .json 檔案
4. 每個成員：carrymem rules install team-conventions.json --scope company
5. 所有 Agent 現在自動執行公司規範
```

### 情境 4：長期使用者

```
第 1 個月：「我偏好深色模式」 → 儲存為 user_preference
第 3 個月：「切換到淺色模式」 → 自動取代舊偏好
第 6 個月：carrymem whoami → 顯示「我偏好淺色模式」（深色模式已歸檔）
```

**偏好會演化。CarryMem 追蹤歷史。**

---

## 快速開始

### 系統需求

- **Python**: ≥3.12（64 位元）
- **作業系統**: macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **磁碟空間**: 核心功能約 5MB，語意搜尋約 200MB
- **記憶體**: 基礎約 50MB

### 安裝方式

```bash
# 基礎安裝（僅核心功能）
pip install carrymem

# 完整安裝（含多語言 + 語意搜尋 + 加密）
pip install carrymem[full]

# 開發模式（含測試工具）
git clone https://github.com/lulin70/carrymem.git
cd carrymem && pip install -e ".[dev]"
```

### 相依性說明

| 功能 | 相依套件 | 安裝指令 |
|------|----------|----------|
| 核心功能（含加密） | PyYAML≥5.0, cryptography≥46.0.6 | 自動包含 |
| 多語言偵測 | pycld2, langdetect | `pip install carrymem[language]` |
| 語意搜尋 | sqlite-vec, sentence-transformers | `pip install carrymem[semantic]` |

> **核心功能零 LLM 相依性** — 分類使用內建規則引擎，無需呼叫任何大型模型。

### 用 Cursor / Claude Code / TRAE？

```bash
pip install carrymem && carrymem setup-mcp --all --global
```

重啟 AI 工具。搞定。

### 驗證效果（30 秒）

告訴你的 AI：
```
記住，我偏好 PostgreSQL
```

開一個新對話，問：
```
我用什麼資料庫？
```

AI 回答 "PostgreSQL" — 成功了！

### 需要遷移記憶？

```bash
carrymem pack                    # 打包為 carrymem_identity_20260526.carry
carrymem pack --encrypt          # 加密打包（提示輸入密碼）
# 拷貝到 USB 隨身碟 / 雲端 / 新機器
carrymem unpack my_identity.carry  # 所有記憶還原
```

### 需要備份？

```bash
carrymem backup                  # 建立備份
carrymem backup --list           # 列出所有備份
carrymem backup --restore <path> # 從備份還原
```

---

> 📊 **學術驗證**：CarryMem 的偏好注入精確度（83.0%）使用 [PrefEval 協定](https://arxiv.org/abs/2410.01373)（ICLR 2025 口頭報告, Amazon Science）測量，在 200 條測試項中超過簡單提醒（80.0%）和零樣本（71.5%）基線。詳見下方[引用](#引用)。

## 選擇 CarryMem 的 3 個理由

這些是 CarryMem 區別於其他所有記憶解決方案的關鍵：

### 1. 偏好注入精準度 — 83.0%（學術驗證）
- 由 PrefEval（ICLR 2025 口頭報告, Amazon Science）測量，200 樣本 3 條件對比
- CarryMem 83.0% > 簡單提醒 80.0% > 零樣本 71.5%
- 主動注入 > 全量提醒 — 首個證明這一點的系統
- 比提醒方式減少 24% 無用回答（28 vs 38）— 更精準，更少噪音

### 2. 零 LLM 分類 — 88% 無需呼叫任何 LLM
- 規則引擎分類 88% 的記憶，零 Token 消耗
- 唯一內建規則引擎的系統（競爭對手：0%）
- P99 延遲：1.3ms — 比 Mem0 快 93 倍

### 3. 輕量可攜帶 — 僅 SQLite
- 核心功能零外部相依性
- 單一 .db 檔案 — 身份隨身攜帶
- 支援 Cursor、Claude Code、ChatGPT、任何 MCP 用戶端

---

## 運作原理

```
使用者輸入
    ↓
自動分類（7 種類型，4 層）  ← 88% 零 LLM
    ↓
重要性評分（confidence × type × recency × access）
    ↓
智慧儲存（SQLite + FTS5，去重，TTL，加密）
    ↓
記憶整合（P0: 去重+衰減 → P1: 模式→規則 → P2: 語意合併）
    ↓
語意召回（FTS5 + 同義詞 + 拼寫糾正 + 跨語言）
    ↓
偏好注入（token 預算，相關性排序）  ← 83.0% 精準度
    ↓
AI 工具（Cursor / Claude Code / 任意 MCP 用戶端）
```

---

## 快速開始

### 安裝

```bash
pip install carrymem
```

> **PyPI 位址**: [https://pypi.org/project/carrymem/](https://pypi.org/project/carrymem/)
>
> **開發模式**: `git clone https://github.com/lulin70/carrymem.git && cd carrymem && pip install -e ".[dev]"`

### 驗證安裝

```bash
carrymem version
```

**如果提示 `command not found`**，新增 Python bin 到 PATH：

```bash
# macOS（新增到 ~/.zshrc）
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# Linux（新增到 ~/.bashrc）
export PATH="$HOME/.local/bin:$PATH"

# 或直接使用 Python 模組
python3 -m carrymem.cli version
```

然後執行 `carrymem doctor` 檢查設定。

### 5 行程式碼

> ⚠️ **套件名稱與匯入名稱**：安裝用 `pip install carrymem`（小寫），匯入用 `from carrymem import CarryMem`（駝峰式類別名）。套件名稱（`carrymem`）和類別名稱（`CarryMem`）大小寫不同。

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("我偏好深色模式")              # 自動分類為偏好
cm.classify_and_remember("用 PostgreSQL 不用 MySQL")    # 自動分類為糾正
memories = cm.recall_memories("資料庫")                  # 語意召回
print(cm.build_system_prompt())                          # 注入任何 AI
cm.close()
```

### 指令列（50+ 指令）

```bash
carrymem init                           # 初始化
carrymem add "我偏好深色模式"            # 儲存記憶
carrymem add "測試筆記" --force         # 強制儲存（跳過分類）
carrymem list                           # 列出記憶
carrymem search "主題"                  # 搜尋記憶
carrymem show <key>                     # 查看記憶詳情
carrymem edit <key> "新內容"            # 編輯記憶
carrymem forget <key>                   # 刪除記憶
carrymem whoami                         # AI 認為你是誰
carrymem profile export --output identity.json   # 匯出 AI 身份
carrymem stats                          # 記憶統計
carrymem check                          # 品質與衝突檢查
carrymem clean --expired --dry-run      # 預覽清理
carrymem doctor                         # 診斷安裝
carrymem setup-mcp --tool cursor        # 一行設定 MCP
carrymem tui                            # 終端介面
carrymem export backup.json             # 匯出所有記憶
carrymem import backup.json             # 匯入記憶
carrymem version                        # 顯示版本
# 規則引擎指令
carrymem rules add "始終使用SSL" --trigger "資料庫" --type avoid   # 新增規則
carrymem rules list --status active                      # 列出活躍規則
carrymem rules pack rules.json --name team-conventions   # 打包規則為 Skill
carrymem rules install team-conventions.json --scope company  # 安裝 Skill
carrymem rules verify team-conversations.json            # 驗證 Skill 完整性
# 備份與攜帶
carrymem pack --encrypt                                 # 加密打包身份檔案
carrymem unpack identity.carry                          # 還原身份
carrymem backup                                         # 建立備份
carrymem backup --list                                  # 列出備份
carrymem backup --restore <path>                        # 從備份還原
```

---

## 核心功能

### 記憶理解你

CarryMem 自動辨識你分享的資訊類型，無需手動標註：

| 類型 | 圖示 | 範例 |
|------|------|------|
| `user_preference` | ⭐ | "我偏好深色模式" |
| `correction` | 🔧 | "不對，是 Python 3.11 不是 3.10" |
| `decision` | 🎯 | "前端用 React" |
| `fact_declaration` | 📌 | "我在東京的一家新創公司工作" |
| `task_pattern` | 🔄 | "我總是先寫測試" |
| `relationship` | 👥 | "張三偏好深色模式" |
| `sentiment_marker` | 💡 | "對微服務方案持正面態度" |

語意召回支援跨語言：

```python
cm.classify_and_remember("我偏好使用PostgreSQL")

# 以下查詢都能找到：
cm.recall_memories("PostgreSQL")     # 精確匹配
cm.recall_memories("資料庫")          # 同義詞擴展
cm.recall_memories("Postgres")       # 拼寫糾正
cm.recall_memories("データベース")    # 跨語言（日語）
```

身份層（whoami）：

```python
identity = cm.whoami()
print(identity["preferences"])   # ["我偏好深色模式", ...]
print(identity["decisions"])     # ["前端用 React", ...]
print(identity["corrections"])   # ["連接埠號碼應該是 5432", ...]
```

### 偏好注入

CarryMem 將結構化偏好注入 system prompt，而非簡單提醒：

```python
print(cm.build_system_prompt())   # 自動產生偏好注入 prompt
```

**為什麼偏好注入 > 全量提醒**：reminder 每輪都注入「記住使用者偏好」。CarryMem 在 system prompt 中注入結構化偏好 — 更精準、更持久、無用回答減少 24%。

### 記憶生命週期

每條記憶都有隨時間演化的重要性評分：

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30 天半衰期衰減** — 舊記憶逐漸淡出，除非被存取
- **存取強化** — 頻繁召回的記憶保持新鮮
- **類型加權** — 糾正(1.3x) > 決策(1.2x) > 偏好(1.1x)

品質管理：

```bash
carrymem check                    # 全面檢查
carrymem check --conflicts        # 偵測矛盾
carrymem check --quality          # 發現低品質記憶
carrymem check --expired          # 發現過期記憶
carrymem clean --expired --dry-run # 預覽清理
```

記憶整合（三階段）：

```python
# 預覽整合效果
report = cm.consolidate(dry_run=True)
print(f"重複: {report['stats']['duplicates_found']}")
print(f"衰減: {len(report['to_decay'])}")

# 執行整合（P0: 去重+衰減, P1: 模式→規則, P2: 語意合併）
report = cm.consolidate(dry_run=False, run_p1=True, run_p2=True)
```

| 階段 | 功能 | 機制 |
|------|------|------|
| **P0** | 去重 + 衰減 | Jaccard 相似度去重，指數半衰期衰減（偏好: 270天, 事實: 90天, 情緒: 45天） |
| **P1** | 模式 → 規則 | 偵測重複模式 → 產生規則候選供審查 |
| **P2** | 語意合併 | 叢集相關記憶 → 請求主機 LLM 整合 |

偏好始終保留 — 永不衰減或去重。

### 安全與可攜帶

| 特性 | 說明 |
|------|------|
| **加密** | AES-128 (Fernet) 或 HMAC-CTR 降級，零相依性 |
| **自動備份** | 零停機 SQLite VACUUM INTO，每 20 次寫入操作自動備份 |
| **.carry 加密** | 可攜式身份檔案支援密碼加密 + SHA-256 校驗 |
| **稽核日誌** | 只追加操作歷史 |
| **版本歷史** | 每次編輯追蹤，支援回復 |
| **輸入驗證** | SQL 注入、XSS、路徑走訪防護 |

---

## 輔助功能

### MCP 整合

```bash
# 設定 Cursor
carrymem setup-mcp --tool cursor

# 設定 Claude Code
carrymem setup-mcp --tool claude-code

# 設定所有工具
carrymem setup-mcp --tool all
```

31 個 MCP 工具：Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (3) · Rules (11) · Graph (3) · Health (1)

**用戶端相容性：**

| 狀態 | 用戶端 | 設定方式 |
|------|--------|---------|
| ✅ 直接支援 | Cursor、Claude Code、TRAE、Windsurf、Cline | `setup-mcp --global` |
| ✅ 自動偵測 | OpenClaw、Kimi Code CLI、CodeX | `setup-mcp --global`（自動回退至 Claude Code 格式） |
| 📋 應用程式商店 | WorkBuddy、CodeBuddy | 需提交至 MCP Marketplace（待完成） |
| ❌ 不支援 | Kimi 桌面版、DeepSeek 桌面版、通義千問、豆包、天工、智譜清言 | 封閉平台，無 MCP 介面 |

> **🔒 你的記憶只存在你自己的機器上。** CarryMem 所有資料本地儲存在 `~/.carrymem/`（SQLite）。每個使用者擁有獨立的資料庫——就像 Git，大家用同一個工具，但各自的儲存庫完全獨立。無雲端同步、無共享狀態、無跨使用者衝突。

### 規則引擎

行為規則支援三個作用域層級，實現團隊/組織對齊：

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# 公司強制規則（最高優先權，不可被覆蓋）
engine.add_rule("資料庫", "始終使用SSL連線", scope="company", override=True)

# 個人偏好（最低優先權）
engine.add_rule("資料庫", "偏好PostgreSQL", scope="personal")

# 作用域感知匹配
results = engine.match("資料庫設計", scopes=["company"])
```

| 作用域 | 優先權 | 說明 |
|--------|--------|------|
| `company` | 3（最高） | 組織強制規則，不可被覆蓋 |
| `negotiated` | 2 | 從公司規則適應而來 |
| `personal` | 1（最低） | 使用者建立的偏好 |

合併協定 — 三種策略合併來自不同來源的規則：

| 策略 | 說明 |
|------|------|
| `company_overrides` | 高作用域始終獲勝 |
| `negotiate` | 衝突規則適應為 "negotiated" 作用域 |
| `keep_both` | 兩條規則都保留，使用者手動審查 |

### Skill 格式

透過加密完整性驗證跨團隊共享規則集：

```python
# 打包規則為可攜式 Skill 包
bundle = engine.skill_pack(
    name="團隊規範",
    version="1.0.0",
    scope="company",
    author="團隊負責人",
)

# 安裝前驗證完整性
result = engine.skill_verify(bundle)
assert result["valid"] is True

# 在另一台機器上安裝
engine.skill_install(bundle, scope_override="company", mode="skip")
```

### 終端介面

```bash
pip install textual
carrymem tui
```

互動式終端介面，側邊欄過濾、搜尋、新增模式。

### VS Code 擴充功能

直接在編輯器中管理規則：

- 規則側邊欄，帶作用域徽章
- 透過 Webview 新增/編輯/刪除規則
- 有效性報表面板
- Skill 打包/安裝檔案對話方塊

---

## 競品比較

|  | CarryMem | Mem0 | OpenChronicle | ima |
|--|----------|------|---------------|-----|
| **零相依性** | ✅ 僅 SQLite | ⚠️ 可選向量資料庫 | ✅ | ❌ 雲端 |
| **自動分類** | ✅ 7 種類型 | ❌ | ❌ 手動 | ❌ |
| **身份畫像** | ✅ whoami | ❌ | ❌ | ❌ |
| **規則引擎** | ✅ 作用域 + Skill | ❌ | ❌ | ❌ |
| **Skill 格式** | ✅ SHA-256 簽名 | ❌ | ❌ | ❌ |
| **合併協定** | ✅ 3 種策略 | ❌ | ❌ | ❌ |
| **VS Code 擴充功能** | ✅ | ❌ | ❌ | ❌ |
| **指令列** | ✅ 40+ 指令 | ❌ | ❌ | ❌ |
| **終端介面** | ✅ textual | ❌ | ❌ | ✅ App |
| **加密** | ✅ 內建 | ❌ | ❌ | ❌ |
| **版本歷史** | ✅ 回復 | ❌ | ❌ | ❌ |
| **衝突偵測** | ✅ 內建 | ❌ | ❌ | ❌ |
| **資料所有權** | ✅ 本地檔案 | ⚠️ 自架 | ✅ 本地 | ❌ 雲端 |
| **5 行程式碼接入** | ✅ | ⚠️ 需要 SDK | ❌ | ❌ |
| **跨語言召回** | ✅ 中/英/日 | ❌ | ❌ | ❌ |
| **核心差異** | **記住你是誰** | 儲存你讀了什麼 | 儲存你讀了什麼 | 儲存你讀了什麼 |

> **註**：比較基於公開資訊。產品迭代迅速，請核實最新功能。

---

### 🏆 PrefEval — 偏好遵守率基準測試

| 條件 | 精確率 | 確認遵守 | 違反 | 幻覺 | 無用回答 |
|------|--------|----------|------|------|----------|
| 零樣本 | 71.5% | 160 | 27 | 3 | 31 |
| 簡單提醒 | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

協定：PrefEval（ICLR 2025 口頭報告, Amazon Science）
樣本：200 條，10 輪干擾，Claude Sonnet 4

**為什麼這很重要**：reminder 每輪都注入「記住使用者偏好」。CarryMem 在 system prompt 中注入結構化偏好——更精準、更持久、無用回答減少 24%。

| | 優勢 | 結果 |
|---|------|------|
| 💰 | 零 LLM 攝入 | **88%** 記憶無需 **LLM Token** |
| ⚡ | P99 延遲 | **1.3ms** — 比 Mem0 **快 93 倍** |
| 🪶 | 相依性 | **僅需 SQLite** — 無需向量資料庫 |
| 🛡️ | 規則引擎 | **唯一擁有**規則引擎（競爭對手：0%） |

---

## 架構

```
使用者輸入
    ↓
自動分類（7 種類型，4 層）
    ↓
重要性評分（confidence × type × recency × access）
    ↓
智慧儲存（SQLite + FTS5，去重，TTL，加密）
    ↓
記憶整合（P0: 去重+衰減 → P1: 模式→規則 → P2: 語意合併）
    ↓
語意召回（FTS5 + 同義詞 + 拼寫糾正 + 跨語言）
    ↓
上下文注入（token 預算，相關性排序）
    ↓
AI 工具（Cursor / Claude Code / 任意 MCP 用戶端）
```

---

## 進階用法

### Obsidian 知識庫

```python
from carrymem import CarryMem, ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python 設計模式")
```

### 非同步 API

```python
from carrymem import AsyncCarryMem

async with AsyncCarryMem() as cm:
    await cm.classify_and_remember("我偏好深色模式")
    memories = await cm.recall_memories("主題")
```

### JSON 配接器（無需 SQLite）

```python
from carrymem import CarryMem, JSONAdapter

cm = CarryMem(adapter=JSONAdapter(path="/path/to/memories.json"))
```

### 加密

```python
cm = CarryMem(encryption_key="my-secret-key")
# 所有內容靜態加密，讀取時解密
```

### 記憶版本管理

```python
cm.update_memory(key, "更新後的內容")     # 建立版本 2
history = cm.get_memory_history(key)      # [v1, v2]
cm.rollback_memory(key, version=1)        # 回復到 v1
```

### 匯出身份給其他 AI

```python
# 匯出你的 AI 身份
cm.export_profile(output_path="my_identity.json")

# 在另一台裝置或 AI 工具上
cm.import_memories(input_path="backup.json")
```

---

## 適合誰？

**厭倦了反覆自我介紹？**
你每天用 Cursor、Claude Code、ChatGPT。你的技術堆疊、編碼風格、架構決策，你告訴 AI 一百遍了，它還在問「你偏好什麼框架？」CarryMem 讓你的 AI 記住這些，不用再說第二遍。

**在手動維護 CLAUDE.md？**
你已經知道 AI 需要記憶。你到處都是 prompt 檔案，它們互相矛盾，會過時，而且換工具就失效。CarryMem 自動分類你的偏好、決策和糾正，並自動保持更新。

**在開發 AI Agent？**
你的 Agent 在會話之間會忘記使用者。你需要一個輕量、本地、相容任何 LLM 的記憶層。CarryMem 提供 5 行程式碼接入、7 種記憶類型和規則引擎，除了 SQLite 外零相依性。

---

## 文件

- [快速入門指南](../QUICK_START_GUIDE.md)
- [安裝指南](../INSTALL.md)
- [使用者指南](../USER_GUIDE.md)
- [架構設計](../ARCHITECTURE.md)
- [API 參考](../API_REFERENCE.md)
- [API 穩定性策略](../API_STABILITY.md)
- [路線圖](ROADMAP-CN.md)
- [貢獻指南](../../CONTRIBUTING.md)

---

## 專案狀態

**目前版本**：v0.8.0
**測試**：4198 passing
**覆蓋率**：80%+

**更新日誌**：
- **v0.2.0**：USB 攜帶加密、自動備份、並行安全、PrefEval 83.0%（200 條）、8 用戶端 MCP 設定
- **v0.2.3**（重置前）：定時整合（schedule/stop）、PrefEval 標準化
- **v0.2.2**（重置前）：Token 預算 + 死程式碼修正 + 安全加固、PrefEval 87.9%
- **v0.2.1**（重置前）：共指消解、自動脫敏、QA 提示最佳化

---

## 貢獻

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
pytest
```

詳見 [貢獻指南](../../CONTRIBUTING.md)。

---

## 引用

如果你在研究中使用 CarryMem，請引用：

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

**實驗結果（200 條樣本，10 輪干擾，Claude Sonnet 4）**

| 條件 | 精確率 | 確認遵守 | 違反 | 幻覺 | 無用回答 |
|------|--------|----------|------|------|----------|
| 零樣本 | 71.5% | 160 | 27 | 3 | 31 |
| 簡單提醒 | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28****

核心發現：CarryMem 在達到最高精確率的同時，比簡單提醒方式減少 24% 的無用回答，證明主動記憶注入比全量上下文提醒更精準。

---

## 授權條款

MIT 授權條款 — 詳見 [LICENSE](../../LICENSE)

---

**CarryMem — 你的 AI 終於認識你了。只有你擁有資料。**

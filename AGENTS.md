# AGENTS.md

## Project
Name: `Reversing-Offline-Search-Web`

Build an offline-first Korean reverse-engineering wiki/search website for CTF and wargame use. The primary user is a reversing beginner who will use it on a Windows competition PC with no Internet connection.

The final site MUST work by double-clicking:

```text
dist/index.html
```

No local server may be required.

## Highest priorities
1. Offline operation.
2. Search quality.
3. Beginner-friendly "what do I do next?" guidance.
4. Correctness and practical usefulness.
5. Exactly 1,000 useful searchable entries, with a large long-form core.
6. Tool manuals, installation instructions, shortcuts and command references.
7. Assembly instruction dictionary searchable by mnemonic.
8. Durable progress logs so another AI can resume after interruption.
9. Large local SSD usage is acceptable.
10. Visual design only needs to be clean, readable and fast.

## GitHub
Create and use a private GitHub repository with GitHub CLI:

```bash
mkdir Reversing-Offline-Search-Web
cd Reversing-Offline-Search-Web
git init
git branch -M main
gh repo create Reversing-Offline-Search-Web --private --source=. --remote=origin
```

First checkpoint:

```bash
git add .
git commit -m "chore: initialize offline reversing knowledge base"
git push -u origin main
```

Do not force-push `main`.

For large work:
- create `feat/<topic>` branch,
- commit meaningful checkpoints,
- merge only after validation.

## Recovery protocol
The AI may stop at any moment.

Maintain:
- `DEVELOPMENT_LOG.md`
- `state/progress.json`
- `content/manifest.json`
- `research/sources.json`
- Git commits

Update `DEVELOPMENT_LOG.md`:
- after every 10 articles,
- after every major feature,
- before architecture changes,
- before stopping,
- when a blocker appears.

At startup read in this order:
1. `AGENTS.md`
2. `REQUIREMENTS.md`
3. `state/progress.json`
4. last 100 lines of `DEVELOPMENT_LOG.md`
5. `git status`
6. `git log --oneline -15`

Never throw away recoverable work.

## Architecture
Prefer static HTML/CSS/JavaScript.

Development/build tools may use Python or Node, but `dist/` must have no runtime dependency on:
- Node
- Python
- localhost
- Internet
- CDN
- remote API
- remote fonts
- remote images
- service workers

Essential local content MUST NOT depend on `fetch()` because `file://` restrictions vary.

Preferred:
```html
<script src="./assets/search-index.js"></script>
<script src="./assets/search.js"></script>
```

Generate a local JS search index at build time.

## Content scale
Milestone 1 target: exactly 1,000 searchable entries.

Do NOT make 1,000 repetitive long-form posts.

Use this mix:
- 500 long-form guides/tutorials
- 250 reference/cheatsheet/dictionary entries
- 250 troubleshooting/error/pattern entries

Long-form guides should normally be substantial enough to use without Internet:
- practical overview
- real workflow
- concrete examples
- commands/shortcuts
- screenshots/diagrams where useful
- common mistakes
- "stuck next step" section
- related entries
- source notes

Avoid artificial word-count padding and duplicate explanations.

## Search architecture
Support Korean + English mixed searches.

Index:
- title
- headings
- body
- aliases
- keywords
- symptom keywords
- assembly mnemonics
- registers
- flags
- tools
- binary format
- platform
- architecture
- API names
- constants

Ranking:
1. exact title
2. exact mnemonic / keyword / symptom
3. heading
4. aliases
5. body
6. fuzzy / partial match

Add Korean-friendly tokenization. At minimum use normalized whitespace plus 2-gram/3-gram indexing so searches such as:
- `call`
- `call 명령어`
- `함수 호출`
- `cmp jnz`
- `main 어디`
- `signed 음수`
- `xref 문자열`
still produce useful results.

## Assembly Dictionary
This is mandatory.

Create a dedicated index/category where typing a mnemonic alone immediately returns a useful reference.

Minimum mnemonics:
`MOV`, `MOVZX`, `MOVSX`, `LEA`, `XCHG`,
`PUSH`, `POP`, `PUSHF`, `POPF`,
`ADD`, `SUB`, `INC`, `DEC`, `IMUL`, `MUL`, `IDIV`, `DIV`, `NEG`,
`AND`, `OR`, `XOR`, `NOT`, `TEST`,
`SHL`, `SAL`, `SHR`, `SAR`, `ROL`, `ROR`,
`CMP`,
`JMP`, `JE/JZ`, `JNE/JNZ`, `JG/JNLE`, `JGE/JNL`, `JL/JNGE`, `JLE/JNG`,
`JA/JNBE`, `JAE/JNB`, `JB/JNAE`, `JBE/JNA`,
`CALL`, `RET`, `LEAVE`, `NOP`,
`CMOVcc`, `SETcc`,
`SYSCALL`, `SYSENTER`, `INT`,
`REP`, `MOVS`, `STOS`, `LODS`, `SCAS`, `CMPS`,
`CPUID`, `RDTSC`.

Each instruction article must explain:
- one-line meaning,
- Intel syntax,
- operands,
- destination/source direction,
- register/memory effects,
- flags changed,
- flags NOT changed when that distinction matters,
- signed/unsigned implications,
- stack/RSP/RIP change,
- common compiler pattern,
- how it appears in IDA/Ghidra pseudocode,
- reversing significance,
- common beginner mistake,
- 2-4 assembly examples,
- equivalent or approximate C,
- related instructions,
- aliases and searchable Korean keywords.

For `CALL`, explicitly cover:
- pushes return address,
- transfers control to target,
- direct vs indirect call,
- stack and return address,
- calling conventions,
- Windows x64 RCX/RDX/R8/R9,
- SysV x64 RDI/RSI/RDX/RCX/R8/R9,
- how to inspect arguments before a CALL,
- imports/API calls,
- what to do when target is a register or memory operand,
- CALL xrefs,
- Step Into vs Step Over.

## Article format
Markdown sources:

```text
content/articles/<category>/<slug>.md
```

Frontmatter:

```yaml
id: REV-0001
title: "..."
slug: "..."
category: "..."
difficulty: "beginner|basic|intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA]
keywords: []
aliases: []
symptom_keywords: []
source_ids: []
last_verified: "YYYY-MM-DD"
```

Recommended body:
1. 한 줄 요약
2. 언제 검색해야 하나
3. 핵심 개념
4. 화면/코드에서 보이는 징후
5. 가장 먼저 할 것
6. 단계별 절차
7. 명령어/단축키
8. 출력 해석
9. 흔한 실수
10. 막혔을 때 다음 체크
11. 미니 예제
12. 관련 글
13. 출처/검증

## Writing policy
Assume the reader knows only basic C and very little assembly.

Never say only:
- "follow xref"
- "patch branch"
- "break here"
- "inspect stack"

Always explain:
- where to click,
- what key to press,
- what command to type,
- what output to expect,
- what the output means,
- what to try next.

## Research
Search aggressively across:
1. official documentation,
2. official repositories,
3. vendor manuals,
4. reputable reversing/security references,
5. CTF writeups,
6. educational blogs.

Use current information when tool UI/version changed.

For factual articles:
- at least one strong source,
- preferably two for tricky topics.

Record every source in `research/sources.json`.

## Copyright / copying / images
The repository is private, but source licensing still matters.

Direct copying and local mirroring are allowed when:
- content is user-owned,
- public domain,
- license explicitly permits redistribution,
- upstream documentation explicitly permits the intended reuse.

Otherwise:
- write an original Korean summary,
- preserve source URL/title/author/date,
- use only short quotations,
- do not mirror an entire copyrighted blog post.

Images:
- actively seek diagrams/screenshots that improve understanding,
- cache images only when redistribution/use is allowed,
- otherwise create an original diagram or project-owned screenshot that demonstrates the same idea,
- keep metadata for every cached image.

Asset metadata:
- source URL
- author/project
- license
- retrieved date
- local path
- SHA256

All images required by the offline article must live under `dist/assets/`.

## Tool kit
Cover and prepare offline documentation/installers where licensing permits.

Core:
- IDA / IDA Free
- Ghidra
- x64dbg / x32dbg
- GDB
- Pwndbg
- Detect It Easy
- PE-bear
- HxD / ImHex
- binutils: `file`, `strings`, `readelf`, `objdump`, `nm`
- checksec
- `ltrace`
- `strace`
- UPX
- Cutter / Rizin / radare2

Managed/mobile:
- dnSpyEx
- ILSpy
- JADX
- apktool
- adb
- Frida

Automation:
- Python
- pwntools
- Z3
- angr
- Capstone
- Keystone
- Unicorn

Optional:
- WinDbg
- Sysinternals Strings
- Process Monitor
- Resource Hacker
- YARA

Never use random binary mirrors if an official release exists.

## Large binaries
Do not pollute normal Git history with huge tool archives.

Local offline kit:
```text
offline-kit/tools/
offline-kit/installers/
offline-kit/docs/
offline-kit/samples/
```

Git should normally store only:
- manifest
- version
- official URL
- SHA256
- license
- install notes
- downloader scripts

Add:
- `scripts/fetch-tools.ps1`
- `scripts/fetch-tools.sh`
- `tools/manifest.json`
- `tools/verify-checksums.py`

## UI
Required top-level navigation:
- 처음 시작
- 30초 트리아지
- 파일 종류별 접근
- 증상으로 찾기
- Assembly Dictionary
- Windows / PE
- Linux / ELF
- 정적 분석
- 동적 분석
- 패킹 / 안티디버깅
- 알고리즘 패턴
- 툴 사용법
- 단축키
- 자동화 / Solver

No decorative bloat.

## Validation
Required checks:
- duplicate title
- duplicate slug
- invalid frontmatter
- missing source
- broken local link
- broken image
- missing asset metadata
- search index integrity
- entry count by content type
- empty/placeholder article
- file:// smoke test

## Scope
For CTF, wargame, education, interoperability and defensive reverse engineering.

Do not turn this into commercial software license cracking instructions.

## Definition of done
- 1,000 useful searchable entries.
- Assembly mnemonics searchable directly.
- Search works completely offline.
- `dist/index.html` works by double click.
- screenshots/diagrams needed offline are local.
- tool usage/install/shortcut guides exist.
- Windows external SSD usage is tested.
- README explains updating/building/offline usage.
- development log is complete.
- private GitHub repository is pushed.

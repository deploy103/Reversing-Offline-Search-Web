# REQUIREMENTS.md

## Product
`Reversing-Offline-Search-Web` is an offline Korean reversing knowledge base and search engine for competition use.

The user should be able to search exactly what they see in IDA/Ghidra/x64dbg/GDB and get a practical next step.

Examples:
```text
positive sp value has been detected
_libc_start_main
call
call rax
test eax eax
cmp eax 1 jnz
-87097619 unsigned
0xffffff and
16777619
xor multiply loop
ida f5
ida xref
x64dbg string
rsp 뭐임
rdi rsi 인자
rcx rdx 인자
upx
ptrace
IsDebuggerPresent
```

## Runtime
Mandatory:
- Windows-friendly.
- `dist/index.html` opens via `file://`.
- no Internet.
- no localhost.
- no CDN.
- no runtime package install.
- all essential JS/CSS/media local.

## Search
Must index:
- article title/body/headings
- Korean aliases
- English aliases
- abbreviations
- error messages
- constants
- mnemonics
- registers
- Windows API names
- libc names
- tools
- file formats
- packer names

Search result:
- title
- category
- difficulty
- why it matched
- highlighted snippet
- tags
- related result links

A "stuck mode" toggle should prioritize symptom/error/problem-solving articles.

## Home page
Show:
- huge search bar
- "파일 받았을 때 30초 트리아지"
- "처음이라 아무것도 모르겠음"
- PE/EXE
- ELF
- Assembly Dictionary
- IDA
- Ghidra
- x64dbg
- GDB/Pwndbg
- packing
- algorithm patterns
- common stuck searches

## Content quota

Milestone 1 contains exactly 1,000 searchable entries.

| Type | Count | Purpose |
|---|---:|---|
| Long-form guides/tutorials | 500 | Deep offline explanations and complete workflows |
| Reference / dictionary / cheatsheets | 250 | Fast lookup during competition |
| Troubleshooting / errors / reversing patterns | 250 | "I'm stuck here" searches |
| Total | 1000 | |

The long-form core should be genuinely substantial. Do not create filler posts merely to hit the number.

Recommended long-form length:
- normally 1,500-4,000 Korean words when the topic justifies it,
- shorter only for intrinsically narrow topics,
- longer when it serves as a standalone offline chapter.

Recommended overall topical distribution:

| Domain | Approx. entries |
|---|---:|
| Beginner workflows / triage / methodology | 80 |
| Binary fundamentals / computer architecture | 80 |
| x86/x64 assembly / instruction dictionary / patterns | 160 |
| Windows / PE / WinAPI / x64dbg | 130 |
| Linux / ELF / libc / GDB / Pwndbg | 120 |
| Static analysis / IDA / Ghidra | 110 |
| Dynamic analysis / debugging | 90 |
| Algorithms / crypto-like validation / transforms | 90 |
| Packers / obfuscation / anti-analysis | 55 |
| .NET / Android / mobile / managed code | 35 |
| Automation / scripting / Z3 / angr / emulation | 30 |
| Tool installation / offline setup / shortcut references | 20 |
| Total | 1000 |

The exact 1,000-entry manifest should be generated and maintained in `CONTENT_PLAN.md`.

## Assembly search requirement
Searching a mnemonic must work even with no other keyword.

Examples:
```text
call
CALL
call 명령어
함수 호출
ret
lea
cmp
test
jnz
jz
sar
shr
movzx
movsx
syscall
```

Instruction page must include "리버싱할 때 이게 왜 중요함?" section.

## Beginner triage flow
Unknown file:

```text
확장자 믿지 않기
-> magic/file type 확인
-> architecture
-> PE / ELF / .NET / APK / script
-> strings
-> imports
-> sections
-> protections
-> packer suspicion
-> entry point
-> main / WinMain
-> input function
-> compare/check function
-> static or dynamic route
```

## Required error/message articles
Include searches for:
- IDA `positive sp value has been detected`
- decompiler failure
- stack pointer analysis problems
- bad stack pointer
- failed to decompile
- undefined instruction/data
- stripped ELF
- PIE address confusion
- ASLR address changes
- anti-debug termination
- debugger detection
- packed/obfuscated entry point

## Signed/unsigned
Must have practical pages covering:
- two's complement
- negative decimal to hex
- 8/16/24/32/64-bit masks
- `& 0xFF`
- `& 0xFFFFFF`
- integer overflow
- modular arithmetic
- sign extension
- zero extension
- why IDA shows a negative constant
- how to convert with Python/calculator

## Calling conventions
Cover:
- x86 cdecl
- stdcall
- fastcall
- thiscall basics
- SysV AMD64
- Microsoft x64
- return values
- stack alignment
- shadow space
- callee/caller-saved registers
- varargs basics

## Tool article requirements
Each major tool needs:
- what it is for
- official download
- offline installation
- first launch
- load a binary
- beginner workflow
- menu paths
- shortcuts
- common commands
- common errors
- competition workflow
- what this tool is bad at
- related tools

## IDA minimum shortcut reference
Cover at least:
- F5: decompile current function
- F2: breakpoint
- F7: step into
- F8: step over
- F9: run/start
- X: xrefs
- N: rename
- G: jump
- Shift+F12: strings
- Ctrl+P: functions
- Y: set type
- Tab / pseudocode-disassembly navigation according to current IDA behavior/version
- number representation controls

Verify shortcuts against current official Hex-Rays docs AND the actually installed version before publishing.
If official pages disagree across IDA versions/pages (for example pseudocode/decompile navigation), document the version difference instead of silently choosing one.

## x64dbg minimum
Cover:
- breakpoints
- run / pause / step
- memory map
- modules
- references
- string references
- find assembly
- expression syntax
- registers/flags
- dump view
- stack view
- patching for CTF experimentation
- saving patched file
- conditional breakpoint basics

## GDB/Pwndbg minimum
Cover:
- start/run
- args
- break
- continue
- stepi/nexti
- disassemble
- x/
- info registers
- backtrace
- memory examine
- watch
- PIE addresses
- attaching to process
- Pwndbg `context`, `telescope`, `vmmap`, `hexdump`, `search`

## Images
Articles should use screenshots/diagrams when they materially reduce confusion.

High-priority screenshots:
- IDA Functions
- IDA Strings
- IDA Xrefs
- IDA pseudocode vs disassembly
- IDA debugger controls
- Ghidra CodeBrowser
- Ghidra Decompiler
- x64dbg CPU view
- x64dbg stack/dump/register panes
- x64dbg string references
- GDB/Pwndbg context
- PE-bear headers
- Detect It Easy packer/compiler detection
- ELF section/layout diagram
- stack frame diagram
- calling convention diagrams
- CALL/RET stack diagram
- flags/Jcc diagram

Prefer project-created screenshots so they remain safe to bundle.

## Source quality
Store:
```json
{
  "id": "SRC-0001",
  "title": "...",
  "url": "...",
  "type": "official|repo|blog|writeup|reference",
  "author": "...",
  "license": "...",
  "retrieved_at": "...",
  "cached": false,
  "notes": "..."
}
```

## Build outputs
Suggested:
```text
dist/
  index.html
  article/
  assets/
    css/
    js/
    img/
    search-index.js
  cheatsheets/
```

## Performance
1,000 entries are still small enough for local search; images and offline tools dominate storage.

Target:
- entire project + offline documentation + cached media + permitted tool packages should stay under 40 GB,
- soft target: 30-35 GB,
- reserve at least 5 GB headroom,
- initial page under a few MB where practical,
- lazy-load large images,
- search responds in under ~300 ms on a normal competition laptop after index initialization,
- index may take longer to initialize if needed; correctness matters more than micro-optimization.

## Offline tool kit
The site should link to local relative paths where tool archives/installers are present.

Example:
```text
../offline-kit/tools/x64dbg/
../offline-kit/tools/ghidra/
```

Do not hardcode drive letters.

## Storage budget

The 30-40 GB budget should be allocated intentionally.

Suggested upper bounds:
- site HTML/JS/CSS/search indexes: < 1 GB
- article screenshots/diagrams/media: 5-10 GB
- offline documentation/PDF/manual mirrors where permitted: 5-8 GB
- reversing tools/installers/portable packages: 15-20 GB
- sample binaries/CTF practice assets: 2-5 GB
- reserve/headroom: at least 5 GB

Create `scripts/storage-report.py` and `scripts/storage-report.ps1` to report:
- total size
- size by top-level directory
- top 100 largest files
- duplicate files by SHA256
- assets over configurable thresholds

Fail CI/local validation if the assembled offline kit exceeds 40 GB.

## Completion test
Disconnect network entirely and verify:
1. double-click `dist/index.html`
2. search `call`
3. search `_libc_start_main`
4. search `positive sp`
5. search `0xffffff`
6. open IDA shortcut page
7. open x64dbg string page
8. open images
9. navigate related articles
10. return using browser history

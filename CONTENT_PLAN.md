# CONTENT_PLAN.md

Milestone 1 target: **exactly 1,000 searchable entries**.

Content composition:
- 500 long-form guides/tutorials
- 250 reference/dictionary/cheatsheet entries
- 250 troubleshooting/error/pattern entries

The previous 300-entry plan below is the mandatory seed set. Expand it to exactly 1,000 entries before mass authoring.

Expansion rules:
1. Preserve all seed topics.
2. Add breadth rather than duplicate rewrites.
3. Add more Windows/PE material because the intended competition environment is Windows.
4. Add assembly lookup pages for individual Jcc, SIMD basics, string instructions, compiler idioms, and register/flag concepts.
5. Add real error-message lookup entries from IDA, Ghidra, x64dbg, GDB, Pwndbg, Python/Z3/angr.
6. Add "symptom search" entries such as:
   - 함수가 어디서 호출되는지 모르겠음
   - 입력값이 어디에 저장되는지 모르겠음
   - 디컴파일 결과랑 어셈블리가 다름
   - 주소가 실행할 때마다 바뀜
   - breakpoint가 안 걸림
   - main이 안 보임
   - 문자열이 깨져 보임
   - 값이 갑자기 음수로 보임
7. Add compiler-pattern articles:
   - switch jump tables
   - stack canaries
   - loop lowering
   - inlining
   - tail calls
   - memset/memcpy idioms
   - C++ constructors/vtables/RTTI basics
8. Add Windows API lookup pages grouped by reversing relevance.
9. Add common C library function lookup pages.
10. Add beginner walkthroughs that combine tools.
11. Long-form entries should be 1,500-4,000 Korean words when warranted.
12. Keep exact count machine-verifiable.

Required generated manifest fields:
`id`, `title`, `type`, `category`, `difficulty`, `priority`, `status`.

## Seed 300 (mandatory)

## 처음 시작 / 문제 접근법 (18)

- REV-0001 — 리버싱 문제 파일을 받았을 때 30초 트리아지
- REV-0002 — 확장자를 믿으면 안 되는 이유와 실제 파일 형식 확인법
- REV-0003 — 처음 보는 EXE 문제 접근 순서
- REV-0004 — 처음 보는 ELF 문제 접근 순서
- REV-0005 — 문제를 정적 분석부터 할지 동적 분석부터 할지 결정하는 법
- REV-0006 — Flag 검증 함수 찾는 가장 흔한 경로
- REV-0007 — 입력 함수부터 역추적하는 방법
- REV-0008 — 성공/실패 문자열에서 역참조 따라가는 방법
- REV-0009 — main 함수가 안 보일 때 찾는 방법
- REV-0010 — stripped 바이너리에서 시작점 잡는 방법
- REV-0011 — 디컴파일 코드가 이상할 때 어셈블리로 돌아가는 기준
- REV-0012 — 문제 설명과 첨부파일에서 힌트 뽑는 방법
- REV-0013 — 문제에서 주어진 상수와 문자열을 먼저 기록해야 하는 이유
- REV-0014 — 리버싱 노트 작성법: 함수 이름 바꾸기와 가설 기록
- REV-0015 — 막혔을 때 5분 체크리스트
- REV-0016 — 브루트포스를 해도 되는 문제인지 판단하는 법
- REV-0017 — 솔버를 짜기 전에 직접 로직을 복원하는 순서
- REV-0018 — 대회장에서 리버싱 문제 하나를 끝까지 추적하는 실전 루틴

## 바이너리 기초 (20)

- REV-0019 — 바이너리와 실행 파일의 기본 구조
- REV-0020 — Magic Byte와 파일 시그니처
- REV-0021 — x86와 x64를 구분하는 법
- REV-0022 — 32비트와 64비트 레지스터 차이
- REV-0023 — Little Endian과 Big Endian
- REV-0024 — 2의 보수와 음수 표현
- REV-0025 — Signed와 Unsigned 해석
- REV-0026 — 8비트 16비트 24비트 32비트 64비트 마스크
- REV-0027 — 정수 Overflow와 Wraparound
- REV-0028 — 주소 VA RVA File Offset 차이
- REV-0029 — 메모리 Section과 Segment 차이
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0031 — 스택 프레임이 무엇인지
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0033 — 포인터와 역참조를 어셈블리에서 읽는 법
- REV-0034 — 배열 접근이 어셈블리로 변하는 방식
- REV-0035 — 구조체 접근이 어셈블리로 변하는 방식
- REV-0036 — 문자열이 메모리에 저장되는 방식 ASCII UTF-8 UTF-16
- REV-0037 — 컴파일러 최적화가 디컴파일 결과를 이상하게 만드는 이유
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이

## x86/x64 Assembly Dictionary (50)

- REV-0039 — MOV: 값 복사와 레지스터 메모리 이동
- REV-0040 — MOVZX: Zero Extension 이해
- REV-0041 — MOVSX와 MOVSXD: Sign Extension 이해
- REV-0042 — LEA: 주소 계산인데 왜 산술 연산처럼 보이는가
- REV-0043 — XCHG: 두 값 교환
- REV-0044 — PUSH: 스택에 값 넣기
- REV-0045 — POP: 스택에서 값 꺼내기
- REV-0046 — PUSHF와 POPF: 플래그 저장과 복원
- REV-0047 — ADD: 덧셈과 플래그
- REV-0048 — SUB: 뺄셈과 플래그
- REV-0049 — INC와 DEC: 1 증가 감소와 CF 주의
- REV-0050 — MUL: Unsigned 곱셈
- REV-0051 — IMUL: Signed 곱셈과 컴파일러 패턴
- REV-0052 — DIV: Unsigned 나눗셈
- REV-0053 — IDIV: Signed 나눗셈
- REV-0054 — NEG: 2의 보수 음수 만들기
- REV-0055 — AND: 마스크와 비트 제거
- REV-0056 — OR: 비트 설정
- REV-0057 — XOR: XOR 연산과 XOR reg reg 제로화
- REV-0058 — NOT: 비트 반전
- REV-0059 — TEST: 값을 바꾸지 않는 AND 비교
- REV-0060 — CMP: 값을 바꾸지 않는 SUB 비교
- REV-0061 — SHL과 SAL: 왼쪽 시프트
- REV-0062 — SHR: 논리 오른쪽 시프트
- REV-0063 — SAR: 산술 오른쪽 시프트
- REV-0064 — ROL: 왼쪽 Rotate
- REV-0065 — ROR: 오른쪽 Rotate
- REV-0066 — JMP: 무조건 분기
- REV-0067 — JE와 JZ: ZF가 1일 때 분기
- REV-0068 — JNE와 JNZ: ZF가 0일 때 분기
- REV-0069 — JG JGE JL JLE: Signed 비교 분기
- REV-0070 — JA JAE JB JBE: Unsigned 비교 분기
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-0073 — LEAVE: 함수 에필로그와 스택 프레임
- REV-0074 — NOP: 아무것도 하지 않는 명령과 패치
- REV-0075 — CMOVcc: 분기 없는 조건부 이동
- REV-0076 — SETcc: 조건 결과를 0 또는 1로 만들기
- REV-0077 — SYSCALL: x86-64 시스템 콜
- REV-0078 — SYSENTER와 SYSEXIT 기초
- REV-0079 — INT와 INT 0x80: 인터럽트 기반 시스템 콜
- REV-0080 — REP Prefix와 반복 문자열 명령
- REV-0081 — MOVS MOVSB MOVSW MOVSD MOVSQ
- REV-0082 — STOS STOSB STOSD STOSQ
- REV-0083 — LODS 문자열 로드 명령
- REV-0084 — SCAS와 문자열 검색 패턴
- REV-0085 — CMPS와 문자열 비교 패턴
- REV-0086 — CPUID: CPU 정보와 안티VM 단서
- REV-0087 — RDTSC: 타이밍 측정과 안티디버깅
- REV-0088 — 플래그 레지스터와 CF ZF SF OF PF를 Jcc와 연결해서 읽기

## Linux / ELF (25)

- REV-0089 — ELF 헤더 읽는 법
- REV-0090 — ELF Program Header와 Section Header 차이
- REV-0091 — readelf 기본 사용법
- REV-0092 — objdump 기본 사용법
- REV-0093 — nm으로 심볼 찾기
- REV-0094 — strings로 빠르게 단서 찾기
- REV-0095 — file 명령으로 ELF 정보 확인
- REV-0096 — checksec 결과 읽는 법
- REV-0097 — ELF Entry Point에서 main까지
- REV-0098 — _start 함수 읽는 법
- REV-0099 — _libc_start_main이 무엇이고 main을 찾는 법
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0102 — RELRO가 리버싱에 의미하는 것
- REV-0103 — PIE와 주소 계산
- REV-0104 — ASLR 때문에 실행할 때 주소가 바뀌는 이유
- REV-0105 — Canary NX PIE RELRO 한 번에 이해
- REV-0106 — SysV AMD64 Calling Convention
- REV-0107 — Linux x86 cdecl Calling Convention
- REV-0108 — argc argv envp를 어셈블리에서 찾는 법
- REV-0109 — scanf fgets read 입력 추적
- REV-0110 — strcmp strncmp memcmp 비교 추적
- REV-0111 — ltrace로 라이브러리 호출 빠르게 보기
- REV-0112 — strace로 시스템 콜에서 힌트 찾기
- REV-0113 — Core dump와 크래시 지점 분석 기초

## Windows / PE (28)

- REV-0114 — PE 파일 구조 한 번에 보기
- REV-0115 — DOS Header와 MZ 시그니처
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0117 — PE Section Table 읽기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0120 — Export Table과 DLL 함수
- REV-0121 — Entry Point와 WinMain 찾기
- REV-0122 — Microsoft x64 Calling Convention
- REV-0123 — Windows x86 stdcall cdecl fastcall thiscall
- REV-0124 — Shadow Space가 무엇인지
- REV-0125 — PE-bear로 헤더 분석하는 방법
- REV-0126 — Detect It Easy로 컴파일러 패커 확인
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0130 — IsDebuggerPresent 안티디버깅 식별
- REV-0131 — CheckRemoteDebuggerPresent 식별
- REV-0132 — PEB BeingDebugged 검사 이해
- REV-0133 — TLS Callback과 main 이전 코드
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0135 — DLL 문제 분석 시작하기
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0137 — Visual C++ Runtime 함수가 많은 바이너리 정리법
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0139 — CreateFile ReadFile WriteFile 입력 데이터 추적
- REV-0140 — Crypt API BCrypt API 흔적 찾기
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 정적 분석 (27)

- REV-0142 — IDA에 바이너리 처음 열었을 때 해야 할 것
- REV-0143 — IDA Functions 창 사용법
- REV-0144 — IDA Strings 창과 Shift+F12
- REV-0145 — IDA Xrefs와 X 키 사용법
- REV-0146 — IDA F5 디컴파일과 Pseudocode 읽기
- REV-0147 — IDA 함수 변수 이름 N으로 바꾸기
- REV-0148 — IDA Y로 타입 지정하기
- REV-0149 — IDA 숫자 표현 Signed Unsigned Hex 바꾸기
- REV-0150 — IDA Graph View에서 분기 읽기
- REV-0151 — IDA Positive SP Value Has Been Detected 경고
- REV-0152 — IDA Decompiler Failed가 뜰 때
- REV-0153 — IDA Stack Pointer 분석이 틀렸을 때
- REV-0154 — IDA에서 함수 경계가 잘못 잡혔을 때
- REV-0155 — IDA에서 Undefined Bytes를 Code/Data로 재해석
- REV-0156 — Ghidra 프로젝트 생성과 바이너리 Import
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0158 — Ghidra Decompiler 창 읽기
- REV-0159 — Ghidra Function 목록과 Symbol Tree
- REV-0160 — Ghidra XREF 따라가기
- REV-0161 — Ghidra Rename과 Data Type 수정
- REV-0162 — Hex View로 디컴파일 결과 검증하기
- REV-0163 — 문자열에서 검증 함수로 이동하는 정적 분석
- REV-0164 — Imports에서 검증 함수 후보 좁히기
- REV-0165 — 상수 검색으로 알고리즘 찾기
- REV-0166 — 함수 Call Graph로 핵심 로직 좁히기
- REV-0167 — Compiler Generated Code와 실제 문제 로직 구분
- REV-0168 — 정적 분석 결과를 Python 의사코드로 옮기기

## 동적 분석 / 디버깅 (27)

- REV-0169 — Breakpoint가 무엇이고 어디에 걸어야 하는가
- REV-0170 — Step Into와 Step Over 차이
- REV-0171 — Run Until Return과 함수 빠져나오기
- REV-0172 — 레지스터 값을 실행 중 추적하는 법
- REV-0173 — 스택 값을 실행 중 추적하는 법
- REV-0174 — 조건 분기 직전에 무엇을 봐야 하는가
- REV-0175 — CALL 직전 함수 인자 확인하는 법
- REV-0176 — CALL 직후 반환값 확인하는 법
- REV-0177 — x64dbg CPU View 읽는 법
- REV-0178 — x64dbg Breakpoint 설정과 삭제
- REV-0179 — x64dbg String References 찾기
- REV-0180 — x64dbg Find Assembly 사용법
- REV-0181 — x64dbg Dump와 Stack View
- REV-0182 — x64dbg Memory Map과 Module View
- REV-0183 — x64dbg 조건부 Breakpoint 기초
- REV-0184 — x64dbg CTF용 간단 패치와 저장
- REV-0185 — GDB 실행 run start args 사용법
- REV-0186 — GDB break와 address breakpoint
- REV-0187 — GDB stepi nexti continue
- REV-0188 — GDB info registers와 flags 확인
- REV-0189 — GDB x 명령으로 메모리 보기
- REV-0190 — GDB disassemble와 현재 RIP 주변 보기
- REV-0191 — GDB watchpoint 기초
- REV-0192 — Pwndbg 설치와 실행
- REV-0193 — Pwndbg context telescope vmmap
- REV-0194 — PIE 바이너리 GDB 브레이크포인트 잡기
- REV-0195 — 디버거에서 입력 버퍼가 실제로 변하는 과정 추적

## 알고리즘 / 검증 패턴 (28)

- REV-0196 — strcmp 기반 Flag 검증 패턴
- REV-0197 — memcmp 기반 Flag 검증 패턴
- REV-0198 — 문자별 for 루프 검증 패턴
- REV-0199 — XOR 반복 변환 역산
- REV-0200 — ADD SUB 상수 기반 문자 변환
- REV-0201 — Rotate ROL ROR 기반 변환
- REV-0202 — Shift SHL SHR SAR 기반 변환
- REV-0203 — AND 0xFF 마스크 이해
- REV-0204 — AND 0xFFFFFF 24비트 마스크 이해
- REV-0205 — Modulo와 오버플로를 이용한 검증
- REV-0206 — 음수 상수를 Unsigned Hex로 다시 읽기
- REV-0207 — FNV-1과 FNV-1a 해시 패턴
- REV-0208 — 16777619 상수가 보일 때 FNV 의심하기
- REV-0209 — CRC 계열 알고리즘 흔적 찾기
- REV-0210 — TEA와 XTEA 상수 패턴
- REV-0211 — AES 테이블 또는 AES API 흔적 찾기
- REV-0212 — Base64 인코딩 검증 패턴
- REV-0213 — Hex 인코딩 검증 패턴
- REV-0214 — Custom alphabet 치환 패턴
- REV-0215 — Lookup Table 기반 변환
- REV-0216 — 배열 인덱스 재배열 Shuffle 검증
- REV-0217 — 중첩 루프와 행렬 변환
- REV-0218 — 길이 검증부터 역추적하는 법
- REV-0219 — Brute Force가 가능한 입력 공간 계산
- REV-0220 — Meet-in-the-middle를 고려할 상황
- REV-0221 — 역연산 가능한 알고리즘 판단법
- REV-0222 — 검증 루틴을 Python으로 그대로 재현하기
- REV-0223 — Known plaintext와 Flag 형식으로 조건 줄이기

## 패킹 / 안티분석 (18)

- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0225 — UPX인지 확인하는 법
- REV-0226 — UPX 기본 언패킹
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0228 — Entropy가 높은 Section의 의미
- REV-0229 — Import가 거의 없는 PE를 봤을 때
- REV-0230 — Self-modifying Code 기초
- REV-0231 — Control Flow Flattening 기초
- REV-0232 — Opaque Predicate 기초
- REV-0233 — 문자열 난독화가 보일 때
- REV-0234 — ptrace PTRACE_TRACEME 안티디버깅
- REV-0235 — IsDebuggerPresent 우회 개념
- REV-0236 — PEB BeingDebugged 검사 우회 개념
- REV-0237 — RDTSC Time Check 안티디버깅
- REV-0238 — CPUID 기반 VM 탐지 기초
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0240 — 디버거에서 갑자기 종료될 때 체크리스트
- REV-0241 — 패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환

## .NET / Android / 모바일 (16)

- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0243 — dnSpyEx로 .NET EXE 열기
- REV-0244 — ILSpy 기본 사용법
- REV-0245 — CIL IL 명령어를 C#과 연결해서 읽기
- REV-0246 — .NET 문자열과 리소스 찾기
- REV-0247 — .NET 난독화 기초
- REV-0248 — APK 파일 구조 기초
- REV-0249 — JADX로 APK 분석 시작
- REV-0250 — AndroidManifest.xml에서 단서 찾기
- REV-0251 — apktool 기본 사용법
- REV-0252 — smali 기초 문법
- REV-0253 — Java Kotlin 코드와 smali 연결
- REV-0254 — Native Library lib*.so가 있을 때
- REV-0255 — adb 기본 명령 치트시트
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0257 — JNI 호출 Java에서 Native까지 추적

## 자동화 / Solver (16)

- REV-0258 — 리버싱용 Python 숫자 변환 치트시트
- REV-0259 — Python으로 Signed Unsigned 변환
- REV-0260 — Python으로 Little Endian 변환
- REV-0261 — Python struct pack unpack
- REV-0262 — Python XOR 역산 템플릿
- REV-0263 — Python Rotate 함수 템플릿
- REV-0264 — Python 32비트 Overflow 재현
- REV-0265 — Python Brute Force 기본 템플릿
- REV-0266 — pwntools로 프로세스 실행하고 입력 보내기
- REV-0267 — pwntools p32 p64 u32 u64
- REV-0268 — Z3 BitVec 기초
- REV-0269 — Z3로 문자 조건 풀기
- REV-0270 — Z3에서 8비트 32비트 Overflow 다루기
- REV-0271 — angr 심볼릭 실행 기초
- REV-0272 — Capstone으로 디스어셈블 자동화
- REV-0273 — Unicorn으로 작은 검증 함수 에뮬레이션

## 툴 사용법 / 치트시트 (27)

- REV-0274 — IDA 설치와 오프라인 준비
- REV-0275 — IDA 핵심 단축키 치트시트
- REV-0276 — IDA 10분 실전 워크플로
- REV-0277 — Ghidra 설치와 오프라인 준비
- REV-0278 — Ghidra 핵심 단축키 치트시트
- REV-0279 — Ghidra 10분 실전 워크플로
- REV-0280 — x64dbg 설치와 오프라인 준비
- REV-0281 — x64dbg 핵심 단축키와 명령 치트시트
- REV-0282 — x64dbg 10분 실전 워크플로
- REV-0283 — GDB 설치와 기본 설정
- REV-0284 — GDB 명령어 치트시트
- REV-0285 — Pwndbg 설치와 오프라인 준비
- REV-0286 — Pwndbg 명령어 치트시트
- REV-0287 — Detect It Easy 설치와 사용법
- REV-0288 — PE-bear 설치와 사용법
- REV-0289 — ImHex 설치와 기본 사용법
- REV-0290 — HxD 설치와 기본 사용법
- REV-0291 — radare2 설치와 첫 명령
- REV-0292 — radare2 명령어 치트시트
- REV-0293 — Cutter 설치와 기본 사용법
- REV-0294 — readelf objdump nm strings 치트시트
- REV-0295 — checksec 설치와 사용법
- REV-0296 — ltrace strace 치트시트
- REV-0297 — UPX 설치와 명령어
- REV-0298 — dnSpyEx ILSpy 설치와 사용법
- REV-0299 — JADX apktool adb 설치와 사용법
- REV-0300 — Z3 angr pwntools Python 오프라인 패키지 준비

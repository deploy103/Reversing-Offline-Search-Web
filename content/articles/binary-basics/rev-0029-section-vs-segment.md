---
id: REV-0029
title: "메모리 Section과 Segment 차이"
slug: "rev-0029-section-vs-segment"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [readelf, objdump, IDA, Ghidra, PE-bear]
keywords: ["section", "segment", "섹션", "세그먼트", "PT_LOAD", "program header", "section header", "IMAGE_SECTION_HEADER"]
aliases: ["section이 뭐임", "segment가 뭐임", "섹션 세그먼트 차이", "PT_LOAD가 뭐임", "section header segment header 차이"]
symptom_keywords: ["readelf -S랑 readelf -l 결과가 왜 다른지 모르겠음", "strip하면 섹션이 사라지는데 실행은 왜 됨", "section이랑 segment랑 뭐가 다른지 모르겠음", ".text .rodata가 왜 같은 영역에 묶여있음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
ELF에는 **링크/디버깅용 정보인 Section(섹션 헤더 테이블)**과 **실행/로딩용 정보인 Segment(프로그램 헤더 테이블)**가 완전히 별개의 테이블로 존재하며, OS 로더는 오직 Segment만 읽는다. 반면 PE는 이 둘을 나누지 않고 **Section 하나가 두 역할을 동시에** 담당한다.

## 언제 검색해야 하나
- `readelf -S`와 `readelf -l` 결과가 서로 다른 걸 보고 어느 쪽이 "진짜" 구조인지 헷갈릴 때
- strip된 ELF 바이너리인데 섹션 이름(`.text`, `.data`)이 안 보이는데도 실행이 멀쩡히 되는 이유가 궁금할 때
- `PT_LOAD`, `PT_DYNAMIC`, `PT_INTERP` 같은 프로그램 헤더 타입이 뭔지 모를 때
- PE에도 ELF처럼 별도의 "세그먼트 테이블"이 있는지 궁금할 때
- [REV-0028](./rev-0028-va-rva-offset.md)(VA/RVA/파일 오프셋 변환)을 읽다가 `p_vaddr`, `p_offset`, `VirtualAddress`, `PointerToRawData` 같은 값이 대체 어디서 나오는지 궁금할 때

## 핵심 개념
바이너리 파일 하나에는 코드, 문자열, 초기화된 전역변수, 초기화 안 된 전역변수 등 성격이 다른 데이터가 섞여 있다. 이걸 "누가, 언제, 무슨 목적으로" 구분해서 보느냐에 따라 두 가지 서로 다른 시야가 필요하다.

**Section(섹션) — 링커/디버거의 시야**
섹션은 링크 타임과 디버깅을 위한 개념이다. 컴파일러가 `.text`(코드), `.data`(초기화된 전역변수), `.bss`(초기화 안 된 전역변수, 파일에는 크기만 있고 실제 바이트는 없음), `.rodata`(문자열/상수 같은 읽기전용 데이터), `.symtab`(심볼 테이블), `.strtab`(문자열 테이블), `.dynsym`(동적 심볼) 같은 이름 붙은 조각으로 오브젝트 파일을 나눠 놓으면, 링커는 이 이름들을 보고 여러 `.o` 파일의 같은 이름 섹션끼리 합쳐서 최종 실행 파일을 만든다. IDA/Ghidra 같은 디스어셈블러도 이 섹션 이름을 읽어서 "이 주소는 `.text`에 있으니까 코드다", "이 주소는 `.rodata`니까 상수 문자열이다"라는 식으로 사람이 이해하기 쉽게 라벨을 붙여준다. 즉 섹션은 **"이 바이트 뭉치가 의미적으로 뭔가"를 설명하는 표**다.

**Segment(세그먼트) — OS 로더의 시야**
세그먼트는 런타임/로더 개념이다. 프로그램을 실행할 때 커널(정확히는 로더, 실제로는 `execve` 시스템 콜과 그 내부의 ELF 로더)이 파일을 읽어서 프로세스 메모리에 매핑(`mmap`)해야 하는데, 이때 로더는 **섹션 헤더 테이블을 아예 읽지 않는다**. 로더는 오직 **프로그램 헤더 테이블(Program Header Table)** 만 본다. 이 테이블의 각 항목이 "세그먼트"이고, 각 세그먼트는 `p_type` 필드로 종류가 정해진다:
- `PT_LOAD` — 실제로 메모리에 매핑해야 하는 영역. 하나의 실행 파일에는 보통 여러 개의 `PT_LOAD` 세그먼트가 있다(코드용, 데이터용 등).
- `PT_DYNAMIC` — 동적 링킹에 필요한 정보(필요한 공유 라이브러리 목록, 재배치 테이블 위치 등)가 담긴 위치.
- `PT_INTERP` — 이 바이너리를 실행할 때 사용할 동적 링커(인터프리터)의 경로 문자열, 예를 들면 `/lib64/ld-linux-x86-64.so.2`.
- `PT_NOTE` — 컴파일러/빌드 정보 같은 부가 메타데이터.
- `PT_GNU_STACK` — 스택을 실행 가능(executable)하게 만들지 여부를 로더에게 알려주는 표시. 이 세그먼트의 권한 비트에 실행(X) 플래그가 있으면 스택이 실행 가능해지고, NX(No-eXecute) 보호가 약해진다.

각 `PT_LOAD` 세그먼트에는 `p_vaddr`(매핑될 가상 주소), `p_offset`(파일 안에서의 오프셋), `p_filesz`/`p_memsz`(파일 크기/메모리 크기), 그리고 권한 플래그 `p_flags`(`PF_R`=읽기, `PF_W`=쓰기, `PF_X`=실행)가 들어 있다. 로더는 이 정보만으로 "이 영역을 이 주소에, 이런 권한으로 매핑하라"는 것을 알 수 있다. **섹션 이름 같은 건 로더에게 전혀 필요 없다.**

**섹션과 세그먼트의 관계 — 하나의 세그먼트가 여러 섹션을 묶는다**
실무에서 가장 중요한 그림은 이거다: 링커는 보통 **비슷한 권한을 가진 섹션들을 하나의 `PT_LOAD` 세그먼트로 묶어서** 배치한다. 전형적인 예:
- 읽기+실행(R-E) 권한의 `PT_LOAD` 세그먼트 하나에 `.text`(코드)와 `.rodata`(읽기전용 상수)가 함께 들어간다. 둘 다 실행 중에 바뀌면 안 되고 코드/상수를 실행·읽기만 하면 되니 같은 권한으로 묶어도 문제없다.
- 읽기+쓰기(RW-) 권한의 `PT_LOAD` 세그먼트 하나에 `.data`(초기화된 전역변수)와 `.bss`(초기화 안 된 전역변수)가 함께 들어간다.

즉 섹션이 "의미 단위"라면 세그먼트는 "권한/매핑 단위"이고, **여러 개의 의미 단위가 하나의 매핑 단위 안에 압축되어 들어간다**. `readelf -l`을 실행하면 출력 맨 아래에 정확히 이 관계를 보여주는 **"Section to Segment mapping"** 표가 나온다 — 이건 실제로 눈으로 확인할 수 있는 구체적인 증거다(아래 명령어/출력 해석 참고).

**결정적인 결과: strip해도 실행에는 전혀 지장이 없다**
로더가 프로그램 헤더만 읽는다는 사실에서 아주 실용적인 결론이 나온다. `strip` 명령으로 ELF의 섹션 헤더 테이블 전체를 지워버려도(즉 `.text`, `.data` 같은 이름과 `.symtab` 심볼 정보가 통째로 사라져도) **바이너리는 완벽하게 정상 실행된다.** 왜냐하면 실행에 필요한 건 프로그램 헤더(세그먼트)뿐이고, 그건 strip해도 그대로 남아 있기 때문이다. 반대로 이 때문에 IDA/Ghidra처럼 섹션 이름에 의존해서 코드/데이터 영역을 자동으로 구분하던 도구는 strip된 바이너리를 만나면 "여기가 `.text`인지 `.rodata`인지"를 스스로 추측해야 해서 분석이 더 어려워진다. **바이너리 자체의 동작은 전혀 영향받지 않지만, 분석 도구의 편의성만 떨어지는 것**이 핵심이다.

**PE는 다르다 — 하나의 Section Table이 두 역할을 겸한다**
PE(Windows 실행 파일)는 ELF처럼 섹션 헤더 테이블과 프로그램 헤더 테이블이 나뉘어 있지 않다. PE에는 `IMAGE_SECTION_HEADER` 배열 하나, 즉 **Section Table**만 있고, 이 배열의 각 항목이 링크 타임 정보와 로딩 정보를 동시에 담는다:
- `VirtualAddress`, `VirtualSize` — 이 섹션이 메모리에 매핑될 때의 상대 주소(RVA)와 크기. ELF의 `p_vaddr`/`p_memsz`에 해당하는 **세그먼트 역할**.
- `PointerToRawData`, `SizeOfRawData` — 이 섹션의 실제 바이트가 파일 디스크 상에서 어디에, 얼마나 있는지. ELF의 `p_offset`/`p_filesz`에 해당하는 **섹션 역할**.
- `Characteristics` — `IMAGE_SCN_MEM_EXECUTE`, `IMAGE_SCN_MEM_READ`, `IMAGE_SCN_MEM_WRITE` 같은 플래그로 이 섹션의 메모리 권한을 직접 지정한다. ELF 세그먼트의 `PF_X`, `PF_R`, `PF_W`와 정확히 대응되는 개념이다.

즉 PE에서는 **섹션이 곧 로더가 매핑하는 단위**다. ELF처럼 "여러 섹션을 하나의 세그먼트로 묶는" 별도의 상위 레이어가 없다. Windows 로더는 PE의 섹션 테이블을 그대로 읽어서 각 섹션을 `VirtualAddress` 위치에, `Characteristics`에 명시된 권한으로 매핑한다. 그래서 PE를 볼 때는 "이건 섹션이야, 세그먼트야?"라고 나눠 물을 필요가 없다 — PE의 섹션은 처음부터 두 역할을 겸하도록 설계되었다.

이 섹션/세그먼트 테이블에 있는 바로 그 숫자들(`p_vaddr`/`p_offset`, `VirtualAddress`/`PointerToRawData`)이 [REV-0028](./rev-0028-va-rva-offset.md)(VA/RVA/파일 오프셋 변환)에서 다룬 변환 공식에 그대로 쓰인다. 즉 이번 글은 "그 표가 왜 그렇게 생겼는지"를, [REV-0028](./rev-0028-va-rva-offset.md)은 "그 표의 숫자로 실제 계산을 어떻게 하는지"를 다룬다.

## 화면/코드에서 보이는 징후
- `readelf -S a.out`과 `readelf -l a.out`을 각각 돌렸는데 개수도 다르고 이름 있는 줄과 없는 줄이 섞여 있어서 헷갈리는 경우
- IDA로 strip된 ELF를 열었더니 함수 이름은 물론 섹션 이름도 `LOAD`, `seg000`처럼 IDA가 임의로 붙인 이름만 보이는 경우
- PE-bear/CFF Explorer로 PE를 열었는데 "Segment"라는 탭이 안 보이고 "Section Headers"만 있는 경우
- `readelf -l` 출력 맨 아래에 `Section to Segment mapping:` 문구와 함께 `00 .text .rodata` 같은 줄이 보이는 경우

## 가장 먼저 할 것
분석 중인 파일이 ELF라면 **`readelf -S`(섹션)와 `readelf -l`(세그먼트)을 둘 다 먼저 뽑아서 나란히 비교**한다. 특히 `readelf -l`의 맨 아래 "Section to Segment mapping" 표를 확인하면 어떤 섹션이 어떤 세그먼트에 속하는지 한눈에 알 수 있다. PE라면 애초에 표가 하나뿐이므로 `objdump -h`나 PE-bear로 Section Table 하나만 확인하면 된다.

## 단계별 절차

**1) ELF 섹션 헤더 테이블 확인 — 링커/디버깅 관점**
```bash
$ readelf -S /bin/ls
There are 30 section headers, starting at offset 0x1c718:

Section Headers:
  [Nr] Name              Type             Address           Offset
       Size              EntSize          Flags  Link  Info  Align
  ...
  [15] .text             PROGBITS         0000000000003890  00003890
       0000000000018171  0000000000000000  AX       0     0     16
  [16] .rodata           PROGBITS         000000000001c000  0001c000
       0000000000005c1c  0000000000000000   A       0     0     32
  ...
  [24] .data             PROGBITS         0000000000023f60  00022f60
       0000000000000668  0000000000000000  WA       0     0     32
  [25] .bss              NOBITS           0000000000024200  000234c8
       0000000000001c48  0000000000000000  WA       0     0     32
```
여기서 `.text`는 `AX`(Alloc+eXecute), `.data`는 `WA`(Write+Alloc)처럼 플래그도 보이지만, 이건 어디까지나 섹션 단위의 정보이고 **로더는 이 표를 읽지 않는다**.

**2) ELF 프로그램 헤더 테이블 확인 — 로더 관점**
```bash
$ readelf -l /bin/ls

Elf file type is DYN (Position-Independent Executable file)
Entry point 0x6690
There are 13 program headers, starting at offset 64

Program Headers:
  Type           Offset             VirtAddr           PhysAddr
                 FileSiz            MemSiz              Flags  Align
  PHDR           0x0000000000000040 0x0000000000000040 0x0000000000000040
                 0x00000000000002d8 0x00000000000002d8  R      0x8
  INTERP         0x0000000000000318 0x0000000000000318 0x0000000000000318
                 0x000000000000001c 0x000000000000001c  R      0x1
      [Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]
  LOAD           0x0000000000000000 0x0000000000000000 0x0000000000000000
                 0x0000000000003fa8 0x0000000000003fa8  R      0x1000
  LOAD           0x0000000000003890 0x0000000000003890 0x0000000000003890
                 0x0000000000018171 0x0000000000018171  R E    0x1000
  LOAD           0x000000000001c000 0x000000000001c000 0x000000000001c000
                 0x0000000000006bb0 0x0000000000006bb0  R      0x1000
  LOAD           0x0000000000022f60 0x0000000000023f60 0x0000000000023f60
                 0x0000000000000da8 0x0000000000000eb8  RW     0x1000
  DYNAMIC        0x0000000000022f70 0x0000000000023f70 0x0000000000023f70
                 0x00000000000001f0 0x00000000000001f0  RW     0x8
  ...
  GNU_STACK      0x0000000000000000 0x0000000000000000 0x0000000000000000
                 0x0000000000000000 0x0000000000000000  RW     0x10

 Section to Segment mapping:
  Segment Sections...
   00
   01     .interp
   02     .interp .note.gnu.property .note.gnu.build-id ...
   03     .init .plt .plt.sec .text .fini
   04     .rodata .eh_frame_hdr .eh_frame
   05     .init_array .fini_array .data.rel.ro .dynamic .got .data .bss
   06     .dynamic
   ...
```
맨 아래 "Section to Segment mapping" 표를 보면, 세그먼트 `03`(R E, 읽기+실행)이 `.init .plt .plt.sec .text .fini`를 한꺼번에 담고, 세그먼트 `05`(RW, 읽기+쓰기)가 `.data`와 `.bss`를 함께 담고 있는 걸 직접 확인할 수 있다. 이게 바로 "여러 섹션이 하나의 세그먼트로 묶인다"는 관계의 실물 증거다. 여기서 `GNU_STACK`의 Flags가 `RW`(실행 X 없음)이면 스택이 실행 불가능(NX 활성)이라는 뜻이고, 만약 `RWE`로 나온다면 스택이 실행 가능해서 스택 기반 셸코드 실행 공격에 더 취약하다는 뜻이다.

**3) strip 전후 비교로 확인하기**
```bash
$ cp /bin/ls ls_copy
$ strip ls_copy
$ readelf -S ls_copy
There are 0 section headers, starting at offset 0x1c718:
$ readelf -l ls_copy
# 프로그램 헤더는 strip 전과 완전히 동일하게 그대로 출력됨
$ ./ls_copy
# 정상적으로 실행됨 — 섹션 헤더가 하나도 없어도 실행에는 아무 문제 없음
```
이 실험이 "로더는 세그먼트만 본다"는 사실을 가장 직접적으로 보여준다.

**4) PE의 Section Table 확인**
```bash
$ objdump -h sample.exe

sample.exe:     file format pei-x86-64

Sections:
Idx Name          Size      VMA               LMA               File off  Algn
  0 .text         00001a00  0000000140001000  0000000140001000  00000400  2**4
                  CONTENTS, ALLOC, LOAD, READONLY, CODE
  1 .rdata        00000c00  0000000140003000  0000000140003000  00001e00  2**4
                  CONTENTS, ALLOC, LOAD, READONLY, DATA
  2 .data         00000400  0000000140005000  0000000140005000  00002a00  2**4
                  CONTENTS, ALLOC, LOAD, DATA
```
`VMA`가 메모리에 매핑될 가상 주소(ELF의 `p_vaddr`/PE의 `VirtualAddress`에 해당), `File off`가 디스크 상 위치(ELF의 `p_offset`/PE의 `PointerToRawData`에 해당)이다. PE-bear로 열면 각 섹션 항목에서 `Characteristics` 컬럼에 `IMAGE_SCN_MEM_EXECUTE`, `IMAGE_SCN_CNT_CODE` 같은 플래그를 직접 볼 수 있는데, 이게 바로 이 섹션의 메모리 권한이다. PE에는 이것 말고 별도의 "세그먼트 테이블"이 없다 — 이 표 하나가 전부다.

## 명령어/단축키
```bash
readelf -S <file>      # ELF 섹션 헤더 테이블 (링크/디버깅용)
readelf -l <file>      # ELF 프로그램 헤더 테이블 (로더용, Section to Segment mapping 포함)
readelf -SW <file>     # 긴 이름 안 잘리게 넓게 출력
objdump -h <file>      # ELF/PE 공통으로 섹션 요약 (ELF는 섹션 헤더, PE는 Section Table)
objdump -p <file>      # PE의 경우 Section Table을 더 자세히(Characteristics 포함) 출력
strip <file>           # ELF의 섹션 헤더 테이블 제거 (프로그램 헤더는 그대로 유지됨)
file <file>            # ELF인지 PE인지, stripped 여부 등 1차 판별
```
IDA/Ghidra에서는 별도 단축키 없이 좌측 "Segments"/"Sections" 창에서 직접 목록을 확인한다. Ghidra는 `Window → Memory Map`에서 각 영역의 권한(R/W/X)을 확인할 수 있다.

## 출력 해석
- `readelf -S`에서 `Flags` 컬럼의 `A`=Alloc(메모리에 할당됨), `X`=eXecute, `W`=Write. 이건 섹션 단위 힌트일 뿐 실제 매핑 권한을 최종 결정하는 건 세그먼트다.
- `readelf -l`에서 같은 `Offset`(파일 오프셋)이 여러 `LOAD` 항목에 겹쳐 보이면, 하나의 파일 페이지가 서로 다른 권한의 두 세그먼트 경계에 걸쳐 있다는 뜻이니 페이지 정렬(`Align`, 보통 `0x1000`)을 함께 확인한다.
- "Section to Segment mapping" 표에서 세그먼트 번호 앞에 아무 섹션 이름도 없는 줄(`00` 처럼)은 `PHDR` 자체나 정렬용 패딩처럼 특정 섹션에 대응하지 않는 세그먼트다.
- strip된 파일에서 `readelf -S`가 `There are 0 section headers`를 출력해도, `readelf -l`은 정상적으로 세그먼트 목록을 출력한다면 그 파일은 정상 실행 가능한 상태다.
- PE의 `objdump -h`에서 `CONTENTS, ALLOC, LOAD`가 붙은 섹션은 파일에 실제 바이트가 있고 메모리에도 로드된다는 뜻이며, `.bss`처럼 `ALLOC`만 있고 `CONTENTS`가 없으면 ELF의 `NOBITS`(`.bss`)와 같은 개념 — 메모리 공간만 예약되고 파일에는 실제 데이터가 없다.

## 흔한 실수
- ELF에서 "섹션 = 세그먼트"라고 동일시하는 것 — 이름과 목적, 그리고 읽는 주체(링커/디버거 vs. 로더)가 완전히 다른 두 개의 별도 테이블이다.
- strip된 ELF를 열었을 때 "섹션 정보가 없으니 이 파일은 손상됐거나 실행이 안 될 것"이라고 단정하는 것 — 섹션 헤더가 없어도 실행에는 전혀 지장이 없다. 오히려 malware나 CTF 바이너리에서 분석을 방해하려고 일부러 strip하는 경우가 흔하다.
- PE를 다루면서 ELF 용어인 "세그먼트"를 그대로 찾으려 하는 것 — PE에는 프로그램 헤더 테이블에 대응하는 별도 구조가 없다. Section Table 하나가 그 역할까지 겸한다.
- `readelf -l`의 `Offset`/`VirtAddr`를 섹션 헤더의 값과 섞어서 계산하는 것 — 같은 이름(오프셋, 가상주소)이라도 어느 테이블에서 온 값인지 구분해서 써야 한다.

## 막혔을 때 다음 체크
- 이 표의 숫자로 실제 VA/RVA/파일 오프셋을 상호 변환해야 한다면 → [REV-0028](./rev-0028-va-rva-offset.md)(VA/RVA/파일 오프셋 변환)로 이동해서 공식과 계산 예시를 확인.
- ELF/PE 포맷 전체 구조가 먼저 정리가 안 됐다면 → [REV-0019](./rev-0019-binary-basics.md)(바이너리 기초)로 돌아가서 전체 그림을 다시 확인.
- 메모리 레이아웃(스택/힙/코드/데이터 영역이 프로세스 안에서 실제로 어떻게 배치되는지)이 궁금하면 → REV-0030(메모리 레이아웃)으로 이동.
- strip된 바이너리에서 함수 경계를 다시 찾아야 한다면, 섹션 이름에 의존하지 말고 프로그램 헤더의 `PT_LOAD` 범위와 진입점(Entry point) 주소부터 시작해서 IDA/Ghidra의 자동 분석 결과를 검증하는 방식으로 접근한다.

## 미니 예제
정적 링크된 작은 ELF 실행 파일을 예로 들어보자. 아래처럼 컴파일했다고 하자.
```bash
$ gcc -static -O0 -o hello hello.c
```
`readelf -l hello`를 실행하면 `LOAD` 타입 세그먼트가 최소 2~4개 나온다. 그중 `Flags`가 `R E`인 세그먼트 하나와, `Section to Segment mapping`에서 그 세그먼트 번호 옆에 `.text .rodata`가 함께 적혀 있는 걸 볼 수 있다. 이제 `strip hello`를 실행한 뒤 `readelf -S hello`를 다시 돌리면 `There are 0 section headers`가 나오지만, `./hello`는 여전히 정상적으로 실행되고 출력도 그대로 나온다. 반면 IDA로 strip된 `hello`를 열면 `.text`, `.rodata` 같은 이름 대신 `LOAD`처럼 IDA가 임의로 붙인 세그먼트 이름만 보이고, 함수 이름도 `sub_401136`처럼 자동 생성된 이름으로 바뀌어 있을 것이다 — 코드 자체는 완전히 동일하게 동작하지만, 분석자가 참고할 수 있는 "이름표"만 사라진 상태다.

같은 프로그램을 Windows용으로 `gcc`(MinGW)나 MSVC로 빌드해서 PE로 만들고 PE-bear로 열면, 좌측에 "Section Headers" 탭 하나만 있고 여기서 `.text` 섹션의 `Virtual Address`와 `Raw Address`(=`PointerToRawData`)가 나란히 한 항목에 표시되는 걸 볼 수 있다. ELF처럼 "Program Headers" 탭이 따로 있는 게 아니라, 이 섹션 항목 자체가 로딩 정보까지 전부 담고 있는 것이다.

## 관련 글
- ./rev-0019-binary-basics.md — ELF/PE 전체 구조 개요
- ./rev-0028-va-rva-offset.md — 이 글의 섹션/세그먼트 테이블 값을 이용한 VA/RVA/파일 오프셋 변환 공식
- REV-0030 — Code Data BSS Stack Heap 기초
- REV-0206 — 음수 상수를 Unsigned Hex로 다시 읽기

## 출처/검증
- ELF 섹션 헤더/프로그램 헤더 구조: TIS Committee, "Tool Interface Standard (TIS) Executable and Linkable Format (ELF) Specification" 및 `man 5 elf` 기준 개념 설명 (2026-09-08 검증).
- `PT_LOAD`, `PT_DYNAMIC`, `PT_INTERP`, `PT_NOTE`, `PT_GNU_STACK` 타입 정의: `man 5 elf`, glibc `elf.h` 기준.
- PE `IMAGE_SECTION_HEADER` 및 `Characteristics` 플래그: Microsoft, "PE Format" 공식 문서(Windows Dev Center, `IMAGE_SECTION_HEADER structure`) 기준.
- `readelf`, `objdump` 동작: GNU Binutils 공식 매뉴얼 기준.

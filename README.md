# Reversing-Offline-Search-Web

인터넷이 끊긴 Windows PC에서도 `dist/index.html`을 더블클릭하면 바로 열리는, 오프라인 한국어 리버싱 지식베이스 겸 검색 엔진입니다. CTF/워게임 대회 중 `call`, `positive sp value`, `16777619`, `main 어디` 처럼 아무렇게나 검색해도 실전에서 바로 쓸 수 있는 답을 찾는 것이 목표입니다.

프로젝트 스펙은 `MASTER_PROMPT.md` / `AGENTS.md` / `REQUIREMENTS.md` / `CONTENT_PLAN.md`에 있습니다. 진행 상태는 `DEVELOPMENT_LOG.md`와 `state/progress.json`에 계속 기록됩니다.

## 빌드하기

Python 3 표준 라이브러리만 사용합니다 (외부 패키지 불필요).

```bash
python3 scripts/build.py       # content/articles/*.md -> dist/ 생성
python3 scripts/validate.py    # 중복/깨진 링크/frontmatter/placeholder 등 검증
```

`dist/`는 빌드 산출물이라 git에 커밋하지 않습니다(.gitignore). 실제 오프라인 배포 시에는 `dist/` 폴더 전체를 SSD에 복사하면 됩니다.

## 오프라인 사용법

1. `python3 scripts/build.py`로 `dist/`를 생성한다.
2. `dist/` 폴더를 통째로 오프라인 PC(SSD 등)에 복사한다.
3. 인터넷 연결 없이 `dist/index.html`을 더블클릭해서 연다.
4. 검색창에 명령어, 레지스터, 에러 메시지, 상수, 증상 등을 아무렇게나 입력한다.

로컬 서버, Node, Python, CDN, 원격 폰트/이미지, `fetch()`/`XMLHttpRequest` 없이 순수 `file://`로 동작하도록 만들어져 있습니다.

## 저장소 구조

```text
content/articles/<category>/<slug>.md   # 글 원본 (frontmatter + markdown)
assets/css, assets/js                   # 손으로 작성한 사이트 정적 리소스
scripts/build.py                        # 빌드 스크립트 (마크다운 -> dist/)
scripts/mdlib.py                        # 의존성 없는 frontmatter/markdown 파서
scripts/validate.py                     # 콘텐츠/링크/검색 인덱스 검증
research/sources.json                   # 리서치 출처 기록
state/progress.json                     # 진행 상태 (다른 AI/작업자가 이어받기 위함)
tests/search-smoke-queries.txt          # 검색 스모크 테스트 쿼리 목록
dist/                                   # 빌드 산출물 (gitignore, 배포용)
```

`reversing_analysis/`는 이 저장소와 무관한 별도 프로젝트이며 git에서 제외되어 있습니다.

## 현재 상태

Phase 1(정적 사이트 골격 + 오프라인 검색 엔진 + 샘플 10개 글) 완료. 나머지 990개 글, 어셈블리 사전, 툴 오프라인 킷, 이미지 등은 `state/progress.json`의 `pending_article_ids`를 참고해 계속 진행합니다.

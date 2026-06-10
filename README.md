# Idleon 빌드 가이드 (한글 번역)

Legends of Idleon 빌드 허브와 67개 가이드를 한글로 옮긴 비공식 번역 사이트입니다.
클래스·스킬·탤런트 등 고유명사는 인게임 검색을 위해 영어 그대로 두었고, 설명만 한글로 번역했습니다.

- **사이트**: https://7bellaa.github.io/idleon-guide-kr/
- **원문 출처**: [gameslikefinder.com — Idleon Builds](https://gameslikefinder.com/article/idleon-builds/)
- 번역 용어 기준: [`TRANSLATION-GLOSSARY.md`](TRANSLATION-GLOSSARY.md)

> 비공식 팬 번역본입니다. 모든 원저작권은 gameslikefinder.com에 있으며, 각 페이지 상단/하단에 원문 링크를 표기했습니다.

## 구조
```
index.html              # 메인 허브 (클래스 진화 트리 + 가이드 디렉터리)
assets/style.css        # 공유 스타일
assets/images/<slug>/   # 원문에서 복원한 가이드 이미지 (출처: gameslikefinder.com)
assets/images/_icons/   # 클래스/스킬 아이콘 (출처: 공식 위키 idleon.wiki)
guides/*.html           # 67개 개별 가이드 번역본
tools/sync_images.py    # 원문 이미지 추출·삽입 스크립트
tools/fetch_wiki_icons.py  # idleon.wiki 클래스/스킬 아이콘 다운로드
tools/build_index.py    # index.html 클래스 트리 생성 + 카드 아이콘 주입
```

## 메인 페이지(index.html)
클래스 빌드는 직업별(전사/아처/마법사/모험가) **기본직 → 전직 → 엘리트 → 마스터**
티어 트리로 정렬했고, 모든 클래스·스킬·가이드 카드에 공식 위키(idleon.wiki) 아이콘을
넣었습니다. 아이콘 갱신/재생성:
```
python3 tools/fetch_wiki_icons.py   # 위키에서 아이콘 다운로드 → assets/images/_icons/
python3 tools/build_index.py        # 트리 재생성 + 카드 아이콘 재주입 (재실행 안전)
```

## 이미지 동기화
번역본은 본문 텍스트만 옮겨 이미지가 없었습니다. 각 가이드 헤더의 원문 URL을 따라가
원문(gameslikefinder.com)의 본문 이미지를 내려받아 `assets/images/<slug>/`에 저장하고,
번역본의 대응 섹션(heading 순서 정렬)에 다시 삽입합니다. 표 안 항목명 옆 작은 게임
아이콘(버블·아이템 등)도 원문 표와 행·셀 위치를 맞춰 해당 셀에 주입합니다.

```
python3 tools/sync_images.py                 # 전체 67개
python3 tools/sync_images.py --only idleon-alchemy-guide   # 한 개만
python3 tools/sync_images.py --no-fetch      # 캐시만 사용(네트워크 X)
```
재실행해도 `<!-- glf-img -->` 마커로 중복 삽입을 막습니다. 원문 HTML은 `.cache/`에
임시 저장되며(커밋 제외), 이미지 저작권은 원저작자(gameslikefinder.com)에 있습니다.

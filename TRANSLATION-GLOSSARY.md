# Idleon 한글 번역 용어집 (TRANSLATION GLOSSARY)

모든 가이드 번역/재검수가 따라야 하는 단일 기준. 목표: **정확성 + 일관성 + 인게임 검색성**.

## 0. 대원칙
- **고유명사는 영어 유지**(클래스/스킬/탤런트/아이템/몬스터/화폐/시스템 이름). `<span class="en">...</span>`로 감싼다.
- **설명 산문만 한글로.** 단, 아래 "게임 용어(term of art)"는 일반 형용사로 직역하지 말 것.
- **한글 병기는 "첫 등장 1회만"**: `Accuracy(명중률)` 처럼. 같은 페이지에서 두 번째부터는 영어만(`Accuracy`).
- 의미가 어긋나지 않게 — 직역보다 게임 맥락에 맞는 자연스러운 한국어.

## 1. 플레이 스타일 (가장 중요 — 자주 오역됨)
| 원어 | 표기 | 의미 / 주의 |
|---|---|---|
| **AFK** | `AFK(방치)` → 이후 `AFK` | 게임을 꺼두거나 방치 상태로 얻는 수익(idle). "자리비움"으로 쓰지 말 것. |
| **Active / Active play / Active Fighting** | `Active(직접 플레이)` → 이후 `Active` | **AFK의 반댓말.** 게임을 켜두고 `Auto`로 돌리며 직접 루팅/파밍하는 방식. **절대 "적극적/적극 전투/능동적"으로 직역 금지.** |
| Auto | `Auto` | 인게임 자동전투 토글 |
| idle gains | `AFK 수익` | |

→ 스윕 대상(반드시 교정): `적극적`, `적극 전투`, `적극 플레이`, `적극적으로 플레이`, `능동적`, `자리비움` → 위 규칙으로.

## 2. 전투/스탯 용어 (영어 유지 + 첫 1회 병기)
| 원어 | 표기 |
|---|---|
| Accuracy | `Accuracy(명중률)` ※ "정확도" 쓰지 말고 **명중률**로 통일 |
| Damage | `Damage(피해)` |
| Defence | `Defence(방어)` |
| Multikill | `Multikill(멀티킬)` |
| Respawn (monster respawn) | `Respawn(리스폰)` |
| Movement Speed | `Movement Speed(이동 속도)` |
| Drop Rate / Drop Chance | `Drop Rate(드롭률)` / `Drop Chance(드롭 확률)` |
| Crit / Critical | `Crit(치명타)` |
| Class EXP | `Class EXP(클래스 경험치)` |
| Skill EXP | `Skill EXP(스킬 경험치)` |
| weapon power | `weapon power(무기 파워)` |
| Giant Monster | `Giant Monster(자이언트 몬스터)` |
| Crystal Monster | `Crystal Monster(크리스탈 몬스터)` |

## 3. 스킬링(생산) 용어
| 원어 | 표기 |
|---|---|
| Skilling | `Skilling(생산 스킬)` → 이후 `Skilling` |
| Efficiency | `Efficiency(효율)` |
| Power (skill power) | `skill power(스킬 파워)` |
| Multi-resource / multi-ore 등 | `Multi(다중 자원)` 맥락에 맞게 |
| Sampling / 3D Printer | `Sampling(샘플링)` / `3D Printer` (영어 유지) |
| AFK skilling gains | `AFK Skilling 수익` |

## 4. 시스템/메커니즘 (영어 유지, 필요시 첫 1회 병기)
talents→`talent(탤런트)`, talent point→`talent 포인트`, Tab 1/2/3→그대로, preset→`preset(프리셋)`,
Star Signs, Stamps, Statues, Obols, Cards / Card Sets, Bubbles, Vials, Cauldrons(Alchemy),
Refinery(`Refinery(정제소)`), Salt, Construction, Cogs, Prayers, Worship, Trapping, Cooking, Lab,
Gaming, Sailing, Breeding, Divinity, Sneaking, Summoning, Farming, Gem Shop, Merit Shop, Arcade Shop,
Post Office, Killroy, Crystal Countdown, Plunderous Mobs, Wraith/Tempest/Arcanist Form,
Upgrade Vault, Rare Drop Bags, AFK Info, Deathnote, Worship Souls 등 — **모두 영어 유지**.

## 5. 자주 쓰는 표현 규칙
| 원어 | 한국어 |
|---|---|
| account-wide | 계정 전체 |
| max (a talent) | "맥스" 또는 "최대 투자" |
| put 1 point in | "1포인트 투자" |
| bossing | 보스전 |
| min-max(ing) | 극한 효율(min-max) |
| world boss | 월드 보스 |
| early/mid/late game | 초반/중반/후반 |
| progression | 진행 |
| unlock | 해금 |

## 6. 스탯 약어 (그대로)
WIS, STR, AGI, LUK, Wisdom→`WIS(지혜)` 첫 1회 정도까지 허용. 약어는 영어 유지.

## 7. HTML 규칙 (재검수 시 유지)
- 템플릿/구조(header, `← 전체 목록`, notice, footer, `<div class="layout single">`) 변경 금지.
- 표는 `<div class="table-wrap"><table><thead>...</thead><tbody>...</tbody></table></div>` 유지.
- 영어 고유명사는 `<span class="en">...</span>` 유지/보강.
- 본문 내 외부 article 링크는 원문 URL(`target="_blank"`) 유지.
- 내용 누락 금지(원문과 대조해 빠진 문단/표 행 없도록). UTF-8, 태그 균형.

#!/usr/bin/env python3
"""
Rebuild index.html's class-build directory as a class-evolution tree (tier
columns: Base -> Subclass -> Elite -> Master, grouped by base job) and add
official-wiki icons to every skill / other guide card.

Icons come from assets/images/_icons/ (downloaded by fetch_wiki_icons.py;
see manifest.json). Re-runnable: regenerates the class section and re-injects
card icons each time.

Usage: python3 tools/build_index.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
ICONS = os.path.join(ROOT, "assets", "images", "_icons")

with open(os.path.join(ICONS, "manifest.json"), encoding="utf-8") as f:
    MANIFEST = json.load(f)


def icon_src(key):
    f = MANIFEST.get(key)
    return f"assets/images/_icons/{f}" if f else None


# --- class evolution tree -------------------------------------------------- #
# (family_ko, base_key, base_name, [branches]); each branch = list of
# (key, name, skill) ordered Subclass -> Elite -> Master
TREE = [
    ("전사", "warrior", "Warrior", [
        [("barbarian", "Barbarian", "Fishing"),
         ("blood-berserker", "Blood Berserker", "Cooking"),
         ("death-bringer", "Death Bringer", "Farming")],
        [("squire", "Squire", "Construction"),
         ("divine-knight", "Divine Knight", "Gaming")],
    ]),
    ("아처", "archer", "Archer", [
        [("bowman", "Bowman", "Catching"),
         ("siege-breaker", "Siege Breaker", "Sailing")],
        [("hunter", "Hunter", "Trapping"),
         ("beast-master", "Beast Master", "Breeding"),
         ("wind-walker", "Wind Walker", "Sneaking")],
    ]),
    ("마법사", "mage", "Mage", [
        [("wizard", "Wizard", "Worship"),
         ("elemental-sorcerer", "Elemental Sorcerer", "Divinity")],
        [("shaman", "Shaman", "Alchemy"),
         ("bubonic-conjuror", "Bubonic Conjuror", "Lab"),
         ("arcane-cultist", "Arcane Cultist", "Summoning")],
    ]),
    ("모험가", "journeyman", "Journeyman", [
        [("maestro", "Maestro", ""),
         ("voidwalker", "Voidwalker", "")],
    ]),
]


def node(key, name, skill, cls="cnode"):
    slug = f"idleon-{key}-build-guide"
    src = icon_src(key)
    img = (f'<img class="cicon" src="{src}" alt="" loading="lazy">'
           if src else f'<span class="cicon ph">{name[0]}</span>')
    sk = f'<span class="cskill">{skill}</span>' if skill else ""
    return (f'<a class="{cls}" href="guides/{slug}.html" '
            f'data-en-url="https://gameslikefinder.com/article/{slug}/">'
            f'{img}<span class="cname">{name}</span>{sk}</a>')


def build_tree():
    rows = []
    for fam_ko, bkey, bname, branches in TREE:
        n = len(branches)
        for i, branch in enumerate(branches):
            cells = []
            if i == 0:
                cells.append(f'<th class="fam" rowspan="{n}">{fam_ko}'
                             f'<span class="en">{bname}</span></th>')
                cells.append(f'<td class="base" rowspan="{n}">'
                             f'{node(bkey, bname, "")}</td>')
            # subclass / elite / master (pad to 3)
            for j in range(3):
                if j < len(branch):
                    cells.append(f"<td>{node(*branch[j])}</td>")
                else:
                    cells.append('<td class="empty"></td>')
            rows.append("        <tr>" + "".join(cells) + "</tr>")
    body = "\n".join(rows)
    return f'''<section id="class-builds" class="cat">
      <h2>클래스 빌드 <span class="en">(Class Builds)</span></h2>
      <p>기본직 → 전직 → 엘리트 → 마스터 순으로 정렬한 직업 트리입니다.
        각 노드의 작은 글씨는 해당 클래스가 담당하는 스킬. <span class="badge ko">KO</span>는 한글 번역본.</p>
      <div class="tree-wrap">
      <table class="class-tree">
        <thead><tr>
          <th class="fam-h">직업</th>
          <th>기본 <span class="en">Base</span></th>
          <th>전직 <span class="en">Subclass</span></th>
          <th>엘리트 <span class="en">Elite</span></th>
          <th>마스터 <span class="en">Master</span></th>
        </tr></thead>
        <tbody>
{body}
        </tbody>
      </table>
      </div>
    </section>'''


# --- icon injection for skill / other guide cards -------------------------- #
# guide slug (href stem) -> manifest key
SLUG_ICON = {
    "legends-of-idleon-mining-build": "mining",
    "idleon-smithing-build-guide": "smithing",
    "idleon-chopping-build-guide": "chopping",
    "idleon-fishing-build-guide": "fishing",
    "idleon-catching-build-guide": "catching",
    "idleon-alchemy-guide": "alchemy",
    "idleon-character-creation-order": "character-creation",
    "idleon-accuracy-guide": "accuracy",
    "idleon-task-merit-shop-guide": "merit-shop",
    "legends-of-idleon-gems": "gem-shop",
    "idleon-card-builds": "card-builds",
    "idleon-best-quests": "quests",
    "idleon-special-talents-guide": "special-talents",
    "idleon-crystal-monster-guide": "crystal-farming",
    "idleon-event-shop-guide": "event-shop",
    "idleon-equipment-guide": "equipment",
    "idleon-best-star-sign": "star-signs",
    "idleon-recipe-unlocks": "task-recipes",
    "idleon-best-stamps": "stamps",
    "idleon-statues-guide": "statues",
    "idleon-arcade-shop-priority": "arcade",
    "idleon-island-expeditions-guide": "island-expeditions",
    "idleon-post-office-guide": "post-office",
    "idleon-killroy-guide": "killroy",
    "idleon-obol-guide": "obols",
    "idleon-weekly-battle-guide": "weekly-battle",
    "idleon-poppy-guide": "poppy",
    "idleon-party-dungeons-guide": "party-dungeon",
    "idleon-max-talent-guide": "max-talent",
    "idleon-3d-printer-guide": "3d-printer",
    "idleon-construction-guide": "construction",
    "idleon-prayers-guide": "prayers",
    "idleon-tower-defence-setup-guide": "tower-defence",
    "idleon-equinox-guide": "equinox",
    "idleon-bubba-guide": "bubba",
    "idleon-cooking-guide": "cooking",
    "idleon-divinity-guide": "divinity",
    "idleon-sneaking-guide": "sneaking",
    "idleon-summoning-guide": "summoning",
    "idleon-farming-guide": "farming",
    "idleon-golden-food-guide": "golden-food",
    "idleon-legend-talents-guide": "legend-talents",
    "idleon-spelunking-guide": "spelunking",
    "idleon-research-guide": "research",
    "idleon-super-talents-guide": "super-talents",
    "idleon-minehead-guide": "minehead",
}

GUIDE_LINK_RE = re.compile(
    r'(<a class="guide-link" href="guides/([^"]+)\.html"[^>]*>)(\s*)'
    r'(?:<img class="licon"[^>]*>)?')


def inject_card_icons(html):
    def repl(m):
        open_tag, slug, ws = m.group(1), m.group(2), m.group(3)
        key = SLUG_ICON.get(slug)
        src = icon_src(key) if key else None
        if not src:
            return open_tag + ws  # leave as-is (no icon found)
        img = f'<img class="licon" src="{src}" alt="" loading="lazy">'
        return f"{open_tag}{ws}{img}"
    return GUIDE_LINK_RE.sub(repl, html)


def main():
    with open(INDEX, encoding="utf-8") as f:
        html = f.read()

    new = re.sub(r'<section id="class-builds".*?</section>',
                 build_tree(), html, count=1, flags=re.S)
    if new == html:
        print("WARNING: class-builds section not replaced")
    new = inject_card_icons(new)

    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(new)

    icons = new.count('class="licon"')
    nodes = new.count('class="cnode"') + new.count('class="cicon"') - new.count('class="cicon ph"')
    print(f"index.html rebuilt: {new.count('class=\"cnode\"')} class nodes, "
          f"{icons} card icons injected")


if __name__ == "__main__":
    main()

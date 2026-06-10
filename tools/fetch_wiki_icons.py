#!/usr/bin/env python3
"""
Download class / skill / topic icons from the official IdleOn wiki (idleon.wiki,
MediaWiki) for the index.html directory page.

For each key we list one or more candidate "File:" names; the first that exists
on the wiki is downloaded into assets/images/_icons/<key>.<ext>. Missing keys
are reported so index.html can fall back to a letter-badge.

Pure standard library. Resolves URLs via the MediaWiki API, then curls the file.

Usage: python3 tools/fetch_wiki_icons.py
"""
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "assets", "images", "_icons")
API = "https://idleon.wiki/api.php"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36")

# key -> ordered candidate wiki File names (first existing one wins)
CLASS = {
    "journeyman": "Journeyman", "warrior": "Warrior", "archer": "Archer",
    "mage": "Mage", "maestro": "Maestro", "voidwalker": "Voidwalker",
    "barbarian": "Barbarian", "squire": "Squire", "bowman": "Bowman",
    "hunter": "Hunter", "wizard": "Wizard", "shaman": "Shaman",
    "blood-berserker": "Blood_Berserker", "death-bringer": "Death_Bringer",
    "divine-knight": "Divine_Knight", "siege-breaker": "Siege_Breaker",
    "beast-master": "Beast_Master", "wind-walker": "Wind_Walker",
    "elemental-sorcerer": "Elemental_Sorcerer",
    "bubonic-conjuror": "Bubonic_Conjuror", "arcane-cultist": "Arcane_Cultist",
    "beginner": "Beginner",
}
ICON_CANDIDATES = {k: [f"{v}_Class_Icon.png"] for k, v in CLASS.items()}

# skills (skill-guides section + skill-flavoured "other" guides)
SKILL = {
    "mining": "Mining", "smithing": "Smithing", "chopping": "Choppin",
    "fishing": "Fishing", "catching": "Catching", "alchemy": "Alchemy",
    "construction": "Construction", "cooking": "Cooking",
    "divinity": "Divinity", "sneaking": "Sneaking", "summoning": "Summoning",
    "farming": "Farming", "worship": "Worship", "trapping": "Trapping",
    "lab": "Lab", "sailing": "Sailing", "gaming": "Gaming",
    "breeding": "Breeding",
}
for k, v in SKILL.items():
    ICON_CANDIDATES.setdefault(k, []).append(f"{v}_Skill_Icon.png")

# curated topic icons (best-effort; first existing candidate wins)
TOPIC = {
    "gem-shop": ["Gem.png"],
    "card-builds": ["Crystal_Carrot_Card.png"],
    "quests": ["Quest_Icon_World1.png"],
    "special-talents": ["Talent_Book_Library.png"],
    "crystal-farming": ["Crystal_Carrot_icon.png", "Crystal_Carrot_Idle.gif"],
    "equipment": ["Smithing.png"],
    "star-signs": ["Mainpage_Star_Signs.png", "Seraph_Twinkling_Star_Sign.gif"],
    "task-recipes": ["Cooking_Skill_Icon.png"],
    "stamps": ["Stamp_Stack.png", "Stamp_Ranks_Animated.gif"],
    "statues": ["Power_Statue.png"],
    "arcade": ["Arcade_Ball.png"],
    "island-expeditions": ["Sailing_Skill_Icon.png"],
    "post-office": ["Post_Office_Box_Reseto_Magnifico.png"],
    "killroy": ["Killroy.gif"],
    "obols": ["Obol_Altar_icon.png", "Obol_Fragment.png"],
    "weekly-battle": ["Colosseum_Ticket.png"],
    "poppy": ["Poppy.gif"],
    "party-dungeon": ["Dungeon_Credits.png"],
    "max-talent": ["Talent_Book_Library.png"],
    "3d-printer": ["3D_Printer.png"],
    "prayers": ["Worship_Skill_Icon.png"],
    "tower-defence": ["Worship_Skill_Icon.png"],
    "equinox": ["Equinox_Enhancement.png"],
    "bubba": ["BubbaUpgrade1.png"],
    "golden-food": ["Golden_Jam.png"],
    "legend-talents": ["Talent_Book_Library.png"],
    "spelunking": ["Cavern_Camp.png"],
    "research": ["Gaming_Skill_Icon.png"],
    "super-talents": ["Talent_Book_Library.png"],
    "minehead": ["Mining_Skill_Icon.png"],
    "accuracy": ["Accuracy_Icon.png"],
    "merit-shop": ["Dungeon_Credits.png"],
    "event-shop": ["Gem.png"],
    "character-creation": ["Beginner_Class_Icon.png"],
}
for k, v in TOPIC.items():
    ICON_CANDIDATES.setdefault(k, [])[:0] = v  # topic candidates first


def api_imageinfo(filenames):
    """Return {File_name: url} for the filenames that exist (batched by 45)."""
    out = {}
    files = list(filenames)
    for i in range(0, len(files), 45):
        chunk = files[i:i + 45]
        titles = "|".join(f"File:{f}" for f in chunk)
        q = urllib.parse.urlencode({
            "action": "query", "titles": titles, "prop": "imageinfo",
            "iiprop": "url", "format": "json"})
        req = urllib.request.Request(API + "?" + q, headers={"User-Agent": UA})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        norm = {n["to"]: n["from"]
                for n in data["query"].get("normalized", [])}
        for p in data["query"]["pages"].values():
            title = p["title"]
            orig = norm.get(title, title).replace("File:", "")
            if "imageinfo" in p:
                out[orig] = p["imageinfo"][0]["url"]
        time.sleep(0.5)
    return out


def sniff_ext(path):
    with open(path, "rb") as f:
        h = f.read(16)
    if h[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if h[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if h[:4] == b"GIF8":
        return ".gif"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return ".webp"
    return ""


def download(url, dest_no_ext):
    tmp = dest_no_ext + ".tmp"
    res = subprocess.run(
        ["curl", "-sL", "--max-time", "40", "-A", UA, "-w", "%{http_code}",
         "-o", tmp, url], capture_output=True, text=True, timeout=60)
    if (res.stdout or "").strip()[-3:] != "200" or not os.path.exists(tmp):
        return None
    ext = sniff_ext(tmp) or os.path.splitext(url)[1].lower() or ".png"
    final = dest_no_ext + ext
    os.replace(tmp, final)
    return os.path.basename(final)


def main():
    os.makedirs(DEST, exist_ok=True)
    all_files = {f for cands in ICON_CANDIDATES.values() for f in cands}
    print(f"resolving {len(all_files)} candidate files via wiki API...")
    urls = api_imageinfo(all_files)
    print(f"  {len(urls)} candidate files exist on wiki\n")

    resolved, missed = {}, []
    for key, cands in ICON_CANDIDATES.items():
        url = next((urls[c] for c in cands if c in urls), None)
        if not url:
            missed.append(key)
            continue
        local = download(url, os.path.join(DEST, key))
        if local:
            resolved[key] = local
            print(f"  OK   {key:22} <- {url.split('/')[-1]}")
        else:
            missed.append(key)
        time.sleep(0.15)

    print(f"\nresolved {len(resolved)} / {len(ICON_CANDIDATES)} icons")
    if missed:
        print("MISSED (will use letter-badge fallback):")
        print("  " + ", ".join(sorted(missed)))
    # write a manifest for the index build step
    with open(os.path.join(DEST, "manifest.json"), "w") as f:
        json.dump(resolved, f, indent=2, ensure_ascii=False)
    print(f"\nmanifest: {os.path.relpath(os.path.join(DEST, 'manifest.json'), ROOT)}")


if __name__ == "__main__":
    main()

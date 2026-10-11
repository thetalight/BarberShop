"""Generate reproducible intro stills from the reviewed series reference images."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from barber.cli import ROOT, image_command


PROJECT = ROOT / "videos/intro"
FIXED = ROOT / "series/xiangwei/assets"
STYLE = (
    "Original stylized human 3D film frame with realistic adult proportions, "
    "warm cinematic amber lighting, tactile wood and fabric, muted blue-gray accents. "
    "Maintain the exact same faces, hair, clothing, ages and ethnicity from the character references. "
    "Maintain the same room or storefront from the location reference. Vertical 9:16. "
    "Natural anatomy and hands. No words, letters, logos, subtitles or watermarks. "
)

SCENES = {
    "01": (
        ["locations/US_EXT_FRONT", "characters/human_barber_v1", "characters/daughter_v1"],
        "At the entrance of the corner barbershop, the East Asian barber father in cream shirt and dark brown apron opens the door warmly. His small four-year-old daughter with a dark bob and sage-green flower hair clip, wearing a sage-green top and tan overalls, stands beside him looking up at dad. Early afternoon American brick street and barber pole visible. Medium framing on father and child, faces clear, no extra people. Keep blank storefront sign unobstructed.",
    ),
    "02": (
        ["locations/US_INT_WIDE", "characters/human_barber_v1", "characters/daughter_v1"],
        "Inside the exact same warm American neighborhood barbershop, father stands by the one dark brown barber chair, smiling toward his daughter. The little girl with her fixed dark bob and flower hair clip is in the separate toy corner near the street window, holding a red toy car. Natural father-child scale, same round mirror on right, coherent reflections with no reflected faces. Medium-wide view, no extra people.",
    ),
    "03": (
        ["locations/US_INT_WIDE", "characters/commuter_regular_v1"],
        "The recurring Black American woman in navy jacket, rust shirt and canvas shoulder bag has just stepped into this exact barbershop after work. She looks slightly rushed but friendly, one hand lightly holding her bag strap. Warm room with the one barber chair and street window; no father, child or extra people. Medium shot, her face and clothes clearly match the reference, no mirror reflection of her face.",
    ),
    "04": (
        ["locations/US_CHAIR_FRONT", "characters/retired_regular_v1"],
        "The same familiar retired American gentleman with silver-gray hair, short gray beard, green plaid overshirt and brown trousers sits relaxed in the leather barber chair and tells a cheerful story. Camera at mirror position facing him, so no mirror in frame. Friendly expression, expressive hands resting naturally, exact same shop, no dog and no extra people.",
    ),
    "05": (
        ["locations/US_INT_WIDE", "characters/neighbor_owner_v1"],
        "The recurring Latina café owner in her late forties, teal cardigan and dark apron visits the same barbershop, carrying two simple unbranded takeaway coffee cups. She is near the doorway, smiling, clearly an adult. One barber chair, same street window and warm wooden cabinets; no extra people and no legible text.",
    ),
    "06": (
        ["locations/US_TOY_CORNER", "characters/daughter_v1", "characters/human_barber_v1"],
        "In the same small toy corner, the four-year-old daughter with a dark bob and flower hair clip, wearing a sage-green top and tan overalls, holds up a colorful crayon drawing of the barbershop and smiles. Her father in cream shirt and brown apron kneels next to her, listening warmly. The red toy car and low shelf remain visible. Close-medium view, faces and age consistent, no extra people, no readable text.",
    ),
    "02b": (
        ["locations/US_INT_WIDE", "characters/human_barber_v1", "characters/daughter_v1"],
        "Closer camera from beside the front window in the exact same small barbershop. The barber father smiles beside the dark leather chair while his small daughter with a dark bob and flower hair clip plays with a red toy car at the nearby low shelf. Frame the window, two people, toy shelf and chair; any mirror must reflect only an empty wall and light. Father and daughter look at each other naturally. No extra faces. Preserve the father's gray temple streak and daughter's tan overalls.",
    ),
    "04b": (
        ["locations/US_INT_WIDE", "characters/retired_regular_v1"],
        "The familiar retired American gentleman with silver-gray hair, short gray beard, green plaid shirt and brown trousers sits on a simple waiting bench by the street window, smiling as he tells a story. Medium-close shot from the doorway side of the same barbershop. The wall mirror and barber chair are fully outside the camera frame. NO mirrors, reflections, shiny glass, duplicate people, or dog. One man only, matching the reference face and clothes.",
    ),
    "05b": (
        ["locations/US_INT_WIDE", "characters/neighbor_owner_v1"],
        "The recurring mature Latina café owner in teal cardigan and dark apron visits the same barbershop and holds TWO PLAIN WHITE CERAMIC MUGS with absolutely no writing or design. Friendly smile, medium view near the street window. The one barber chair and walnut cabinets establish the same space. Cups have blank surfaces, no printed takeaway cups, no words, logos, letters or numbers. No other people or reflected faces.",
    ),
}


def main() -> None:
    selected = sys.argv[1:] or list(SCENES)
    out_dir = PROJECT / "assets/stills"
    out_dir.mkdir(parents=True, exist_ok=True)
    for number in selected:
        refs, scene = SCENES[number]
        output = out_dir / f"scene_{number}.png"
        paths = [FIXED / f"{name}.png" for name in refs]
        seed = 4100 + int(number[:2]) + (100 if number.endswith("b") else 0)
        argv, _ = image_command(STYLE + scene, paths, output, seed)
        log = PROJECT / "assets/stills" / f"scene_{number}.log"
        print(f"Generating {number}: {output}", flush=True)
        with log.open("w", encoding="utf-8") as file:
            result = subprocess.run(argv, stdout=file, stderr=subprocess.STDOUT, timeout=3600)
        if result.returncode:
            raise SystemExit(f"Scene {number} failed, see {log}")
        if number == "01":
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(output), "-q:v", "2",
                            str(out_dir / "scene_01.jpg")], check=True)


if __name__ == "__main__":
    main()

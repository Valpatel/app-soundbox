"""
Clean SFX Prompt Library for AudioGen

All prompts are designed to produce isolated, clean sounds without:
- Background noise
- Room reverb
- Street ambience
- Multiple layered sounds

Focus: Single, crisp sound effects that can be processed/layered later.
"""

# Quality modifiers to append to prompts for cleaner output
QUALITY_SUFFIXES = [
    ", isolated sound, studio quality, no background noise",
    ", clean recording, no reverb, single sound",
    ", crisp audio, isolated, professional recording",
    ", dry recording, no ambient noise, clear",
    ", studio recording, isolated sound effect, clean",
]

# =============================================================================
# ANIMALS & CREATURES (currently empty: bird, dog, cat, insect)
# =============================================================================

ANIMAL_PROMPTS = {
    "bird": [
        # Specific bird types for variety
        "single sparrow chirp, isolated bird call, no background",
        "robin singing, clear bird song, studio quality",
        "crow caw, single loud bird call, isolated",
        "owl hoot, deep bird call, clean recording",
        "eagle screech, sharp bird cry, no reverb",
        "seagull call, single gull squawk, isolated",
        "pigeon cooing, soft bird sound, close mic",
        "woodpecker tapping, rhythmic bird percussion, clean",
        "hawk cry, piercing bird call, isolated sound",
        "canary singing, melodic bird song, studio recording",
        "parrot squawk, loud bird call, no background noise",
        "duck quacking, single quack, isolated",
        "chicken clucking, barnyard bird, clean audio",
        "rooster crowing, morning bird call, crisp",
        "songbird trill, rapid bird melody, no reverb",
    ],
    "dog": [
        # Different bark types
        "single dog bark, medium sized dog, isolated",
        "small dog yapping, chihuahua bark, clean recording",
        "large dog bark, deep woof, no reverb",
        "dog growling, low menacing growl, isolated sound",
        "puppy whimpering, soft cry, close mic recording",
        "dog howling, long wolf-like howl, clean",
        "dog panting, heavy breathing, isolated",
        "aggressive dog snarl, teeth baring, no background",
        "playful dog bark, excited yip, studio quality",
        "guard dog bark, loud alert bark, isolated",
        "dog whining, sad dog sound, clean recording",
        "multiple quick barks, rapid succession, no echo",
        "dog sniffing, nose sounds, close microphone",
        "dog eating, crunching kibble, isolated foley",
        "dog drinking water, lapping sounds, clean",
    ],
    "cat": [
        "cat meowing, single meow, isolated recording",
        "cat purring, continuous purr, close mic",
        "cat hissing, aggressive hiss, clean sound",
        "kitten mewing, tiny meow, studio quality",
        "cat yowling, loud cat call, no background",
        "cat growling, low feline growl, isolated",
        "cat chirping, hunting sound, clean recording",
        "cat scratching, claws on surface, foley",
        "angry cat screech, fight sound, no reverb",
        "contented cat purr, relaxed purring, warm",
        "cat eating, crunching food, isolated",
        "playful cat sound, excited meow, clean",
    ],
    "insect": [
        "bee buzzing, single bee flight, isolated",
        "fly buzzing, housefly sound, close mic",
        "mosquito whine, high pitched buzz, clean",
        "cricket chirping, single cricket, night sound isolated",
        "cicada drone, summer insect, no background",
        "wasp buzzing, aggressive insect, studio quality",
        "grasshopper chirp, leg rubbing sound, clean",
        "beetle clicking, hard shell sound, isolated",
        "dragonfly wings, rapid wing beats, close recording",
        "moth flutter, soft wing sounds, quiet",
        "swarm of bees, multiple bees, controlled recording",
        "cockroach scuttling, insect movement, foley",
    ],
}

# =============================================================================
# TRAILER & CINEMATIC (empty: riser, boom, stinger, swell, buildup, drop, drone, sub_bass)
# =============================================================================

TRAILER_PROMPTS = {
    "riser": [
        "cinematic riser, ascending tension sound, clean synth",
        "orchestral riser, building strings, isolated",
        "electronic riser, sweeping upward tone, no reverb",
        "horror riser, creepy ascending sound, dry",
        "action riser, intense building sound, studio",
        "sci-fi riser, futuristic ascending tone, clean",
        "reverse cymbal riser, metallic sweep, isolated",
        "vocal riser, choir ascending, no background",
        "synth riser, saw wave ascending, clean",
        "tension riser, dissonant building tone, dry recording",
        "epic riser, massive ascending sound, cinematic",
        "subtle riser, gentle build, quiet start",
    ],
    "boom": [
        "deep cinematic boom, low frequency impact, clean",
        "thunder boom, massive low end, isolated",
        "explosion boom, distant blast, no debris",
        "drum boom, taiko hit, studio recording",
        "sub boom, extremely low impact, clean bass",
        "metal boom, resonant low hit, dry",
        "epic boom, trailer impact, isolated sound",
        "cannon boom, artillery blast, no echo",
        "door slam boom, heavy impact, foley",
        "earthquake boom, rumbling impact, clean recording",
    ],
    "stinger": [
        "horror stinger, sharp scare chord, isolated",
        "orchestral stinger, dramatic accent, clean",
        "brass stinger, powerful horn hit, studio",
        "string stinger, violin screech accent, no reverb",
        "synth stinger, electronic accent, dry",
        "action stinger, intense accent hit, isolated",
        "mystery stinger, curious accent, clean",
        "reveal stinger, dramatic moment, studio quality",
        "tension stinger, dissonant accent, no background",
        "comedy stinger, quirky accent sound, clean",
    ],
    "swell": [
        "orchestral swell, strings crescendo, isolated",
        "synth swell, pad growing louder, clean",
        "choir swell, voices building, studio",
        "brass swell, horns crescendo, no reverb",
        "ambient swell, atmospheric growth, dry",
        "tension swell, building unease, isolated",
        "emotional swell, heartfelt crescendo, clean",
        "epic swell, massive orchestral build, studio",
        "subtle swell, gentle volume increase, quiet",
        "reverse swell, sound building backward, clean",
    ],
    "buildup": [
        "drum buildup, snare roll crescendo, isolated",
        "electronic buildup, synth tension build, clean",
        "orchestral buildup, timpani roll, studio",
        "action buildup, intense percussion, no reverb",
        "horror buildup, creepy escalation, dry",
        "anticipation buildup, growing tension, clean",
        "heartbeat buildup, accelerating pulse, isolated",
        "noise buildup, white noise rising, studio",
        "rhythmic buildup, pattern intensifying, clean",
        "cinematic buildup, epic preparation, no background",
    ],
    "drop": [
        "bass drop, heavy low frequency hit, clean",
        "dubstep drop, wobble bass impact, isolated",
        "cinematic drop, everything stops then boom, dry",
        "electronic drop, synth impact, studio",
        "drum drop, full kit impact, no reverb",
        "silence drop, sudden stop, clean cut",
        "orchestral drop, full orchestra hit, isolated",
        "tension drop, release after buildup, clean",
        "sub drop, extreme low frequency, studio",
        "glitch drop, electronic stutter impact, dry",
    ],
    "drone": [
        "dark drone, ominous low tone, clean",
        "ambient drone, atmospheric hum, isolated",
        "synth drone, sustained electronic tone, dry",
        "orchestral drone, sustained strings, no reverb",
        "horror drone, creepy sustained tone, studio",
        "sci-fi drone, futuristic hum, clean",
        "mechanical drone, machine hum, isolated",
        "vocal drone, sustained voice, dry recording",
        "low drone, sub frequency sustain, clean",
        "textured drone, complex sustained sound, studio",
        "peaceful drone, calm ambient tone, isolated",
        "dissonant drone, unsettling sustained, clean",
    ],
    "sub_bass": [
        "sub bass hit, extremely low impact, clean",
        "sub bass rumble, low frequency vibration, isolated",
        "sub bass pulse, rhythmic low end, dry",
        "sub bass drop, descending low frequency, studio",
        "sub bass swell, growing low end, clean",
        "808 sub bass, hip hop low end, isolated",
        "cinematic sub bass, theatrical low, no reverb",
        "sub bass tone, sustained low frequency, clean",
        "sub bass wobble, modulated low end, studio",
        "earthquake sub bass, ground shaking low, isolated",
    ],
}

# =============================================================================
# UI & INTERFACE (empty: menu)
# =============================================================================

UI_PROMPTS = {
    "menu": [
        "menu open sound, soft whoosh, UI sound clean",
        "menu close sound, gentle swoosh, isolated",
        "menu hover sound, subtle highlight, studio",
        "menu select sound, soft click confirm, clean",
        "menu scroll sound, list movement, dry",
        "dropdown menu sound, expanding UI, isolated",
        "menu transition sound, smooth slide, clean",
        "popup menu sound, appearing UI, studio",
        "menu back sound, return navigation, dry",
        "menu tab sound, section change, clean",
        "context menu sound, right click UI, isolated",
        "menu navigation sound, arrow key movement, studio",
    ],
}

# =============================================================================
# ACTIONS & MOVEMENT (empty: footstep)
# =============================================================================

MOVEMENT_PROMPTS = {
    "footstep": [
        # Different surfaces
        "footstep on wood floor, single step, isolated foley",
        "footstep on concrete, hard surface step, clean",
        "footstep on gravel, crunchy step, no background",
        "footstep on grass, soft outdoor step, isolated",
        "footstep on tile, hard click step, studio",
        "footstep on carpet, soft muffled step, clean",
        "footstep on metal, industrial step, dry",
        "footstep on sand, beach walking, isolated",
        "footstep on snow, crunchy winter step, clean",
        "footstep on leaves, autumn walking, foley",
        "footstep on water puddle, splash step, isolated",
        "footstep on stairs, ascending wood steps, clean",
        # Different shoes
        "high heels on hard floor, clicking steps, isolated",
        "boots on concrete, heavy footstep, clean",
        "sneakers on gym floor, squeaky step, studio",
        "bare feet on wood, soft padding, isolated",
        "dress shoes on marble, formal steps, clean",
        "running footsteps, rapid steps, isolated",
        "walking footsteps, casual pace, clean recording",
        "sneaking footsteps, quiet careful steps, isolated",
    ],
}

# =============================================================================
# HUMAN SOUNDS (empty: laugh)
# =============================================================================

HUMAN_PROMPTS = {
    "laugh": [
        "male chuckle, soft laugh, isolated voice",
        "female giggle, light laughter, clean recording",
        "child laughing, playful laugh, studio",
        "evil laugh, villainous cackle, no reverb",
        "nervous laugh, awkward chuckle, isolated",
        "hearty laugh, deep belly laugh, clean",
        "sinister laugh, creepy chuckle, dry",
        "joyful laugh, happy laughter, studio quality",
        "sarcastic laugh, mocking chuckle, isolated",
        "maniacal laugh, crazy laughter, clean",
        "crowd laughing, audience laughter, controlled",
        "snicker, suppressed laugh, quiet isolated",
        "guffaw, loud burst of laughter, clean",
        "witch cackle, halloween laugh, isolated",
    ],
}

# =============================================================================
# VEHICLES & MACHINES (empty: electricity, helicopter)
# =============================================================================

VEHICLE_PROMPTS = {
    "electricity": [
        "electric spark, single zap, isolated",
        "power surge, electrical buzz, clean",
        "static electricity, crackling spark, studio",
        "electric arc, continuous zapping, no background",
        "transformer hum, electrical buzz, isolated",
        "short circuit, sparking electronics, clean",
        "tesla coil, electric discharge, dry",
        "power line buzz, high voltage hum, isolated",
        "electric shock, zapping sound, studio",
        "circuit breaker trip, electrical snap, clean",
        "fluorescent light buzz, tube hum, isolated",
        "electrical crackle, sparking wire, no reverb",
    ],
    "helicopter": [
        "helicopter rotor, spinning blades, isolated",
        "helicopter flyby, passing overhead, clean",
        "helicopter hovering, stationary rotor, studio",
        "helicopter startup, engine beginning, no background",
        "helicopter landing, descending rotor, isolated",
        "helicopter takeoff, ascending flight, clean",
        "distant helicopter, far away rotor, dry",
        "helicopter interior, cabin sound, isolated",
        "military helicopter, heavy rotor, studio",
        "news helicopter, light chopper, clean",
        "helicopter blades only, no engine, isolated",
        "helicopter approach, getting closer, no reverb",
    ],
}

# =============================================================================
# SCI-FI & FANTASY (empty: teleport, futuristic, power_up)
# =============================================================================

SCIFI_PROMPTS = {
    "teleport": [
        "teleportation sound, sci-fi transport, clean synth",
        "beam up sound, star trek style, isolated",
        "portal opening, dimensional rift, studio",
        "matter transport, atoms dispersing, no reverb",
        "instant teleport, quick zap transport, clean",
        "warp sound, space folding, isolated",
        "blink teleport, short range jump, dry",
        "fade teleport, gradual disappear, studio",
        "glitch teleport, digital transport, clean",
        "magic teleport, fantasy transport, isolated",
        "teleport arrival, appearing sound, no background",
        "teleport departure, vanishing sound, clean",
    ],
    "futuristic": [
        "futuristic door, sci-fi sliding door, isolated",
        "futuristic computer, digital interface, clean",
        "futuristic weapon charge, energy building, studio",
        "futuristic engine, spaceship hum, no reverb",
        "futuristic alert, sci-fi alarm, isolated",
        "futuristic scan, digital scanning, clean",
        "futuristic hologram, projection sound, dry",
        "futuristic vehicle, hover car, studio",
        "futuristic UI, interface sounds, isolated",
        "futuristic ambient, space station hum, clean",
        "futuristic servo, robotic movement, no background",
        "futuristic communication, radio transmission, isolated",
    ],
    "power_up": [
        "power up sound, energy charging, clean synth",
        "video game power up, arcade collect, isolated",
        "shield power up, defensive buff, studio",
        "speed power up, acceleration boost, no reverb",
        "health power up, healing collect, clean",
        "weapon power up, upgrade sound, isolated",
        "magic power up, fantasy buff, dry",
        "level up sound, achievement gain, studio",
        "coin collect, arcade pickup, clean",
        "super power up, major upgrade, isolated",
        "temporary power up, short boost, no background",
        "ultimate power up, maximum charge, clean",
    ],
}

# =============================================================================
# WEAPONS & COMBAT (empty: fight)
# =============================================================================

COMBAT_PROMPTS = {
    "fight": [
        "punch impact, fist hitting body, isolated foley",
        "kick impact, foot striking, clean",
        "body slam, wrestling throw, studio",
        "martial arts hit, combat strike, no reverb",
        "slap sound, open hand hit, isolated",
        "headbutt impact, skull collision, clean",
        "elbow strike, joint impact, dry",
        "knee strike, leg impact, studio",
        "body fall, person hitting ground, isolated",
        "combat grunt, fighting exertion, clean vocal",
        "block sound, defensive parry, no background",
        "grapple sound, wrestling hold, isolated",
        "throw impact, body landing, clean",
        "combat whoosh, fast movement, studio",
    ],
}

# =============================================================================
# HORROR & TENSION (empty: jumpscare)
# =============================================================================

HORROR_PROMPTS = {
    "jumpscare": [
        "jumpscare stinger, sudden scare, isolated",
        "jumpscare hit, shocking impact, clean",
        "jumpscare screech, piercing scare, no reverb",
        "cat screech jumpscare, animal scare, studio",
        "orchestra jumpscare, dramatic shock, isolated",
        "synth jumpscare, electronic scare, clean",
        "horror jumpscare, terrifying accent, dry",
        "subtle jumpscare, quiet shock, studio",
        "loud jumpscare, massive scare hit, isolated",
        "reverse jumpscare, backward shock, clean",
        "glitch jumpscare, digital scare, no background",
        "bass jumpscare, low frequency shock, isolated",
    ],
}

# =============================================================================
# CARTOON & COMEDY (empty: funny, slide_whistle)
# =============================================================================

CARTOON_PROMPTS = {
    "funny": [
        "comedy honk, clown horn, isolated",
        "silly boing, cartoon spring, clean",
        "wacky slide, descending comedy, studio",
        "goofy pop, comic effect, no reverb",
        "comedy fail, pratfall sound, isolated",
        "silly squeak, rubber sound, clean",
        "cartoon splat, messy impact, dry",
        "comedy whistle, playful toot, studio",
        "goofy gulp, exaggerated swallow, isolated",
        "silly hiccup, comic hiccup, clean",
        "comedy zip, fast movement, no background",
        "wacky wobble, unstable sound, isolated",
    ],
    "slide_whistle": [
        "slide whistle up, ascending whistle, isolated",
        "slide whistle down, descending whistle, clean",
        "slide whistle bounce, up and down, studio",
        "slide whistle slow, gradual slide, no reverb",
        "slide whistle fast, quick slide, isolated",
        "slide whistle wobble, vibrato whistle, clean",
        "slide whistle long, extended slide, dry",
        "slide whistle short, brief slide, studio",
        "slide whistle comedy, funny whistle, isolated",
        "slide whistle fall, dropping whistle, clean",
        "double slide whistle, two slides, no background",
        "slide whistle trill, rapid vibrato, isolated",
    ],
}

# =============================================================================
# MASTER CATEGORY MAPPING
# =============================================================================

ALL_SFX_PROMPTS = {
    # Animals
    "bird": ANIMAL_PROMPTS["bird"],
    "dog": ANIMAL_PROMPTS["dog"],
    "cat": ANIMAL_PROMPTS["cat"],
    "insect": ANIMAL_PROMPTS["insect"],
    # Trailer
    "riser": TRAILER_PROMPTS["riser"],
    "boom": TRAILER_PROMPTS["boom"],
    "stinger": TRAILER_PROMPTS["stinger"],
    "swell": TRAILER_PROMPTS["swell"],
    "buildup": TRAILER_PROMPTS["buildup"],
    "drop": TRAILER_PROMPTS["drop"],
    "drone": TRAILER_PROMPTS["drone"],
    "sub_bass": TRAILER_PROMPTS["sub_bass"],
    # UI
    "menu": UI_PROMPTS["menu"],
    # Movement
    "footstep": MOVEMENT_PROMPTS["footstep"],
    # Human
    "laugh": HUMAN_PROMPTS["laugh"],
    # Vehicles
    "electricity": VEHICLE_PROMPTS["electricity"],
    "helicopter": VEHICLE_PROMPTS["helicopter"],
    # Sci-Fi
    "teleport": SCIFI_PROMPTS["teleport"],
    "futuristic": SCIFI_PROMPTS["futuristic"],
    "power_up": SCIFI_PROMPTS["power_up"],
    # Combat
    "fight": COMBAT_PROMPTS["fight"],
    # Horror
    "jumpscare": HORROR_PROMPTS["jumpscare"],
    # Cartoon
    "funny": CARTOON_PROMPTS["funny"],
    "slide_whistle": CARTOON_PROMPTS["slide_whistle"],
}

# Target counts per category
TARGET_COUNTS = {
    # Animals - aim for ~50-100 each
    "bird": 75,
    "dog": 75,
    "cat": 60,
    "insect": 60,
    # Trailer - these are heavily used, aim for 100+
    "riser": 100,
    "boom": 100,
    "stinger": 100,
    "swell": 80,
    "buildup": 100,
    "drop": 100,
    "drone": 80,
    "sub_bass": 80,
    # UI
    "menu": 50,
    # Movement
    "footstep": 100,
    # Human
    "laugh": 75,
    # Vehicles
    "electricity": 60,
    "helicopter": 50,
    # Sci-Fi
    "teleport": 60,
    "futuristic": 80,
    "power_up": 80,
    # Combat
    "fight": 75,
    # Horror
    "jumpscare": 60,
    # Cartoon
    "funny": 60,
    "slide_whistle": 40,
}

def get_prompts_for_category(category: str, count: int = None) -> list:
    """Get prompts for a category, cycling through available prompts."""
    if category not in ALL_SFX_PROMPTS:
        raise ValueError(f"Unknown category: {category}")

    base_prompts = ALL_SFX_PROMPTS[category]
    target = count or TARGET_COUNTS.get(category, 50)

    # Cycle through prompts to reach target count
    result = []
    for i in range(target):
        prompt = base_prompts[i % len(base_prompts)]
        # Add variation suffix for repeated prompts
        if i >= len(base_prompts):
            variation = i // len(base_prompts)
            # Add subtle variation to avoid exact duplicates
            prompt = f"{prompt}, variation {variation + 1}"
        result.append(prompt)

    return result


if __name__ == "__main__":
    # Print summary
    print("=" * 60)
    print("CLEAN SFX PROMPT LIBRARY")
    print("=" * 60)

    total_prompts = 0
    total_target = 0

    for category, prompts in ALL_SFX_PROMPTS.items():
        target = TARGET_COUNTS.get(category, 50)
        total_prompts += len(prompts)
        total_target += target
        print(f"{category:15s}: {len(prompts):3d} base prompts -> {target:3d} target clips")

    print("=" * 60)
    print(f"Total: {len(ALL_SFX_PROMPTS)} categories")
    print(f"       {total_prompts} base prompts")
    print(f"       {total_target} target clips to generate")

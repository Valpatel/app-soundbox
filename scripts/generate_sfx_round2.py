#!/usr/bin/env python3
"""
Sound Box - SFX Generation Round 2
Focus: Clean, isolated sound effects without background noise
Emphasis on footsteps, UI sounds, and commonly needed game/video SFX
"""

import requests
import time
import sys

API_URL = "http://localhost:5309"

# =============================================================================
# FOOTSTEPS - Comprehensive variations
# =============================================================================

FOOTSTEPS = []

# Surface materials
surfaces = [
    ("concrete", "hard concrete pavement"),
    ("gravel", "loose gravel crunching"),
    ("wood", "wooden floor boards"),
    ("tile", "ceramic tile floor"),
    ("carpet", "soft carpet muffled"),
    ("grass", "outdoor grass lawn"),
    ("leaves", "dry autumn leaves"),
    ("snow", "fresh snow crunching"),
    ("sand", "beach sand soft"),
    ("metal", "metal grating industrial"),
    ("marble", "marble floor elegant"),
    ("dirt", "dirt path outdoor"),
    ("mud", "wet mud squelching"),
    ("water", "shallow water splashing"),
    ("puddle", "rain puddle splash"),
    ("stone", "cobblestone street"),
]

# Footwear types
footwear = [
    ("boots", "heavy boots"),
    ("heels", "high heels clicking"),
    ("sneakers", "rubber sneakers soft"),
    ("barefoot", "bare feet soft"),
    ("dress shoes", "leather dress shoes"),
    ("sandals", "flip flop sandals"),
    ("work boots", "steel toe work boots"),
    ("slippers", "soft slippers shuffling"),
    ("combat boots", "military combat boots"),
    ("running shoes", "athletic running shoes"),
]

# Movement styles
styles = [
    ("walking", "normal walking pace"),
    ("running", "fast running"),
    ("sneaking", "quiet sneaking tiptoeing"),
    ("limping", "uneven limping injured"),
    ("stomping", "heavy stomping angry"),
    ("shuffling", "slow shuffling tired"),
    ("jogging", "light jogging pace"),
    ("sprinting", "fast sprinting"),
]

# Generate footstep combinations (subset to avoid too many)
for surface, surface_desc in surfaces:
    # Basic footsteps on each surface
    FOOTSTEPS.append(f"footsteps {surface_desc} single step clean isolated")
    FOOTSTEPS.append(f"footsteps {surface_desc} walking steady pace clean")
    FOOTSTEPS.append(f"footsteps {surface_desc} running fast clean isolated")

# Footwear specific
for shoe, shoe_desc in footwear:
    FOOTSTEPS.append(f"footsteps {shoe_desc} walking clean isolated")
    FOOTSTEPS.append(f"footsteps {shoe_desc} running clean isolated")

# Character types
characters = [
    "footsteps child small light running",
    "footsteps heavy person slow walking",
    "footsteps elderly slow shuffling careful",
    "footsteps soldier marching boots",
    "footsteps dancer graceful light",
    "footsteps zombie dragging shuffling horror",
    "footsteps robot mechanical metal",
    "footsteps giant heavy ground shaking",
    "footsteps creature monster claws",
    "footsteps horse hooves trotting",
    "footsteps horse hooves galloping",
    "footsteps dog paws running",
    "footsteps cat paws soft padding",
]
FOOTSTEPS.extend(characters)

# =============================================================================
# UI / APP SOUNDS - Clean digital interface sounds
# =============================================================================

UI_SOUNDS = [
    # Notifications
    "notification chime gentle pleasant clean",
    "notification ping short crisp digital",
    "notification bubble pop soft friendly",
    "notification ding bright positive clean",
    "notification alert subtle professional",
    "notification whoosh slide in smooth",
    "notification badge count increment",
    "notification message received chat",
    "notification email new mail arrived",
    "notification reminder gentle alarm",
    "notification success task complete",
    "notification error soft warning gentle",
    "notification update available",
    "notification download complete",
    "notification upload finished",

    # Buttons and clicks
    "button click soft plastic clean",
    "button click mechanical tactile",
    "button click digital interface",
    "button hover subtle feedback",
    "button toggle switch on off",
    "button press deep satisfying",
    "button release spring back",
    "checkbox tick check mark",
    "radio button select click",
    "slider drag smooth movement",
    "slider snap to position",
    "dropdown menu open expand",
    "dropdown menu close collapse",

    # Typing and keyboard
    "keyboard typing mechanical clicky",
    "keyboard typing membrane soft",
    "keyboard single key press",
    "keyboard spacebar press deep",
    "keyboard enter key press",
    "keyboard backspace delete",
    "keyboard shortcut combo",
    "touchscreen tap finger glass",
    "touchscreen swipe gesture",
    "touchscreen pinch zoom",

    # System sounds
    "system startup boot sequence",
    "system shutdown power down",
    "system error critical alert",
    "system warning caution beep",
    "system connected device plugged",
    "system disconnected device removed",
    "system volume change beep",
    "system screenshot capture shutter",
    "system copy paste clipboard",
    "system undo action reverse",
    "system redo action forward",
    "system save document confirm",
    "system delete trash swoosh",
    "system search magnify whoosh",
    "system loading processing",
    "system complete finished success",

    # App specific
    "timer countdown tick tock",
    "timer alarm ringing done",
    "stopwatch start beep",
    "stopwatch lap split",
    "stopwatch stop end",
    "calendar reminder event alert",
    "music player play button",
    "music player pause button",
    "music player skip next",
    "music player skip previous",
    "video call ringing incoming",
    "video call connected join",
    "video call ended hang up",
    "camera shutter photo capture",
    "camera focus beep confirm",
    "payment success transaction complete",
    "payment processing waiting",
    "lock screen unlock slide",
    "fingerprint scan accepted",
    "face recognition success",
]

# =============================================================================
# GAME SOUNDS - Actions, combat, power-ups
# =============================================================================

GAME_SOUNDS = [
    # Combat hits
    "punch impact flesh hit clean",
    "punch swing whoosh miss",
    "kick impact body thud",
    "slap face sharp crisp",
    "hit impact blunt force",
    "hit critical damage powerful",
    "hit light tap weak",
    "block shield deflect metal",
    "block parry sword clang",
    "block dodge whoosh miss",

    # Weapons
    "sword swing slash whoosh",
    "sword hit metal clang",
    "sword unsheathe draw blade",
    "sword sheathe put away",
    "axe swing heavy chop",
    "axe hit wood splitting",
    "hammer swing heavy slow",
    "hammer hit impact thud",
    "bow draw string tension",
    "bow release arrow shoot",
    "arrow fly whoosh air",
    "arrow hit target thud",
    "arrow miss ricochet",
    "staff swing magic whoosh",
    "dagger stab quick thrust",
    "spear throw launch whoosh",
    "whip crack snap sharp",
    "chain swing rattle metal",
    "shield bash impact thud",

    # Magic and abilities
    "spell cast magical energy",
    "spell fire flame burst",
    "spell ice freeze crystal",
    "spell lightning electric zap",
    "spell heal restoration glow",
    "spell buff enhancement power",
    "spell debuff curse negative",
    "spell teleport vanish whoosh",
    "spell summon appear magical",
    "mana charge energy building",
    "mana depleted empty drained",
    "aura activate energy surrounding",
    "shield magical barrier activate",
    "invisibility cloak vanish",

    # Power-ups and items
    "coin collect pickup ching",
    "gem collect sparkle valuable",
    "item pickup acquire get",
    "power up activate boost",
    "health pickup heal restore",
    "ammo pickup reload stock",
    "key collect unlock item",
    "treasure chest open discovery",
    "loot drop items falling",
    "inventory open bag rustle",
    "inventory close bag zip",
    "item equip gear up",
    "item unequip remove gear",
    "item use consume activate",
    "item craft create forge",
    "item upgrade enhance improve",
    "item break destroy shatter",

    # Character actions
    "jump launch spring up",
    "jump land impact ground",
    "double jump air boost",
    "dash quick burst speed",
    "roll dodge tumble ground",
    "climb grab ledge grip",
    "slide ground friction swoosh",
    "wall jump kick off",
    "swim splash water movement",
    "dive underwater plunge",
    "surface emerge water gasp",
    "glide air float gentle",
    "fall long descending whoosh",
    "respawn appear materialize",
    "death defeat collapse thud",
    "revive resurrect restore",

    # Level and progress
    "level up fanfare celebration",
    "experience gain points add",
    "achievement unlock accomplish",
    "quest complete mission done",
    "checkpoint reached save point",
    "door unlock open access",
    "door locked denied rattle",
    "secret found discovery chime",
    "puzzle solve correct answer",
    "puzzle wrong incorrect buzz",
    "countdown timer tick urgent",
    "countdown end time up",
    "score increase points tally",
    "combo streak multiplier",
    "critical hit bonus damage",

    # Environment interaction
    "switch toggle lever pull",
    "button press pressure plate",
    "mechanism activate gears turning",
    "trap trigger warning alert",
    "trap spring activate danger",
    "platform moving mechanical",
    "elevator ascending going up",
    "elevator descending going down",
    "conveyor belt running loop",
    "fan spinning air blowing",
    "turret firing automatic",
    "laser beam continuous energy",
]

# =============================================================================
# NATURE SOUNDS - Clean isolated natural sounds
# =============================================================================

NATURE_SOUNDS = [
    # Birds (isolated calls)
    "bird chirp single tweet clean",
    "bird song melodic warbling",
    "bird crow caw harsh",
    "bird owl hoot night",
    "bird hawk screech predator",
    "bird eagle cry majestic",
    "bird seagull call coastal",
    "bird duck quack water",
    "bird rooster crow morning",
    "bird chicken cluck farm",
    "bird woodpecker pecking tree",
    "bird wings flapping takeoff",
    "bird wings landing settle",

    # Insects
    "insect bee buzzing flying",
    "insect fly buzzing annoying",
    "insect mosquito whine high",
    "insect cricket chirp night",
    "insect cicada buzz summer",
    "insect grasshopper jump spring",
    "insect beetle crawling",
    "insect butterfly wings flutter",

    # Animals (clean calls)
    "dog bark single alert",
    "dog bark multiple aggressive",
    "dog growl warning threat",
    "dog whimper sad hurt",
    "dog howl lonely night",
    "dog panting happy hot",
    "dog drinking water lapping",
    "dog eating food crunching",
    "dog tail wagging happy",
    "cat meow single call",
    "cat meow multiple needy",
    "cat purr content happy",
    "cat hiss angry warning",
    "cat growl aggressive threat",
    "wolf howl wild night",
    "wolf pack howling chorus",
    "bear growl aggressive large",
    "bear roar attack angry",
    "lion roar powerful king",
    "tiger growl predator big",
    "elephant trumpet call loud",
    "horse neigh whinny call",
    "horse snort breath",
    "cow moo farm animal",
    "sheep baa farm animal",
    "goat bleat farm animal",
    "pig oink farm animal",
    "pig squeal loud high",
    "frog croak ribbit water",
    "frog chorus pond night",
    "snake hiss reptile warning",
    "snake rattle warning danger",

    # Weather (isolated)
    "thunder rumble distant low",
    "thunder crack close loud",
    "thunder rolling long echo",
    "lightning strike electric zap",
    "rain drop single splash",
    "rain light drizzle patter",
    "rain heavy downpour storm",
    "rain on window glass tapping",
    "rain on roof metal patter",
    "rain on leaves nature patter",
    "hail stones falling impact",
    "wind gust sudden strong",
    "wind howl eerie storm",
    "wind whistle through gap",
    "wind chime gentle breeze",
    "snow falling quiet soft",
    "blizzard wind snow harsh",
    "ice cracking frozen lake",
    "icicle falling breaking glass",

    # Water
    "water drop single drip",
    "water drip faucet leak",
    "water splash small ripple",
    "water splash large impact",
    "water pour from container",
    "water stream brook flowing",
    "water river rapids rushing",
    "water waterfall distant roar",
    "water waves gentle shore",
    "water waves crashing beach",
    "water bubbles underwater",
    "water boiling pot stove",
    "water ice cubes glass",
    "water drain sink empty",
    "water spray hose garden",
]

# =============================================================================
# HOUSEHOLD SOUNDS - Everyday objects and appliances
# =============================================================================

HOUSEHOLD = [
    # Kitchen
    "pot lid metal clang",
    "pan sizzle cooking frying",
    "knife chopping cutting board",
    "knife sharpening steel blade",
    "microwave beep timer done",
    "microwave door open close",
    "microwave running humming",
    "oven door open creak",
    "oven timer ding ready",
    "refrigerator door open seal",
    "refrigerator humming running",
    "dishwasher running water spray",
    "blender running motor whir",
    "mixer electric beating whir",
    "toaster pop up ready",
    "kettle boiling whistling",
    "coffee maker brewing drip",
    "coffee grinder grinding beans",
    "ice dispenser cubes falling",
    "garbage disposal grinding",
    "plate dish clatter ceramic",
    "glass clink toast cheers",
    "cutlery drawer silverware",
    "cork pop bottle opening",
    "can opening tab pull",
    "jar lid twist open",
    "plastic wrap tear stretch",
    "aluminum foil crinkle tear",
    "paper towel tear rip",

    # Bathroom
    "toilet flush water rushing",
    "toilet lid up down",
    "sink faucet running water",
    "shower running water spray",
    "bathtub filling water",
    "bathtub draining gurgle",
    "soap dispenser pump squirt",
    "toothbrush electric buzzing",
    "hair dryer blowing hot",
    "electric razor buzzing shave",
    "medicine cabinet opening",
    "towel flapping shaking",

    # Living room
    "tv turning on static",
    "tv channel change click",
    "remote control button press",
    "sofa sitting down cushion",
    "recliner lever mechanical",
    "lamp switch click on",
    "light switch flip toggle",
    "curtains opening sliding",
    "blinds pulling cord rattle",
    "clock ticking mechanical",
    "clock chime hourly bell",
    "clock alarm ringing loud",

    # Bedroom
    "bed springs creaking mattress",
    "blanket rustling fabric",
    "pillow fluffing soft",
    "alarm clock ringing wake",
    "alarm clock snooze button",
    "closet door sliding open",
    "drawer opening sliding wood",
    "drawer closing shutting",
    "hangers sliding metal rack",
    "zipper opening closing",
    "velcro ripping separating",
    "button snap fastening",
    "belt buckle metal clink",

    # Cleaning
    "vacuum cleaner running motor",
    "vacuum cleaner suction hose",
    "broom sweeping floor bristles",
    "mop bucket water splash",
    "spray bottle spritz mist",
    "sponge squeezing water",
    "scrubbing cleaning brush",
    "washing machine running cycle",
    "washing machine beep done",
    "dryer running tumbling",
    "dryer buzzer finished",
    "ironing board setup unfold",
    "iron steam hiss press",

    # Tools and hardware
    "hammer nail hitting wood",
    "screwdriver turning screw",
    "drill electric spinning",
    "saw cutting wood back forth",
    "sander electric vibrating",
    "wrench turning bolt metal",
    "toolbox opening metal latch",
    "tape measure extending snap",
    "duct tape pulling sticky",
    "stapler office punching",
    "hole punch paper cutting",
    "paper shredder grinding",
    "scissors cutting paper snip",
    "pencil writing scratching",
    "pen clicking retractable",
    "marker drawing squeaking",
    "eraser rubbing paper",
    "paper rustling handling",
    "paper crumpling balling up",
    "paper tearing ripping",
    "book page turning flip",
    "book closing thud",
    "book dropping falling thump",
]

# =============================================================================
# VEHICLES - Cars, bikes, machines
# =============================================================================

VEHICLES = [
    # Car sounds
    "car engine start ignition",
    "car engine idle running",
    "car engine revving accelerate",
    "car engine off shutdown",
    "car door open creak",
    "car door close slam",
    "car door lock beep click",
    "car door unlock beep click",
    "car trunk open latch",
    "car trunk close thud",
    "car horn short honk",
    "car horn long honk angry",
    "car turn signal blinker click",
    "car windshield wipers swipe",
    "car window rolling down electric",
    "car seat belt click buckle",
    "car gear shift manual stick",
    "car handbrake engage release",
    "car key fob beep chirp",
    "car alarm siren blaring",
    "car passing by whoosh",
    "car skid tires screech",
    "car crash impact metal",
    "car tire puncture flat pop",

    # Motorcycle
    "motorcycle engine start loud",
    "motorcycle engine idle rumble",
    "motorcycle engine revving roar",
    "motorcycle passing by loud",
    "motorcycle kickstand click",

    # Bicycle
    "bicycle bell ring ding",
    "bicycle chain pedaling click",
    "bicycle brakes squeaking",
    "bicycle tire pump inflating",
    "bicycle spoke spinning wheel",
    "bicycle kickstand flip",
    "bicycle crash falling metal",

    # Trucks and large vehicles
    "truck engine diesel rumble",
    "truck horn loud deep",
    "truck air brakes release hiss",
    "truck backup beeping warning",
    "truck loading cargo thud",
    "bus door open hydraulic",
    "bus engine idle diesel",
    "ambulance siren wailing",
    "police siren wailing",
    "fire truck siren horn",
    "ice cream truck music jingle",
    "garbage truck lifting mechanism",
    "forklift beeping backing",

    # Trains
    "train horn whistle loud",
    "train wheels on track clacking",
    "train engine steam locomotive",
    "train brakes screeching stop",
    "train station announcement chime",
    "subway train arriving station",
    "subway doors opening closing",

    # Aircraft
    "airplane takeoff engine roar",
    "airplane landing touchdown",
    "airplane flying overhead",
    "airplane cabin ding chime",
    "helicopter rotor spinning",
    "helicopter flying overhead",
    "jet engine turbine whine",
    "propeller plane buzzing",

    # Boats
    "boat motor outboard running",
    "boat horn foghorn deep",
    "boat waves splashing hull",
    "sailboat rigging ropes wind",
    "anchor chain dropping metal",
    "rowing oars water splash",
    "kayak paddle water stroke",
]

# =============================================================================
# SPORTS AND RECREATION
# =============================================================================

SPORTS = [
    # Ball sports
    "basketball bouncing dribble",
    "basketball swish net score",
    "basketball rim hit bounce",
    "basketball court sneaker squeak",
    "soccer ball kick thud",
    "soccer ball hitting net goal",
    "soccer ball bouncing grass",
    "football throw spiral whoosh",
    "football catch hands impact",
    "football tackle body impact",
    "baseball bat hit crack",
    "baseball catch glove pop",
    "baseball pitch throw whoosh",
    "tennis racket hit ball",
    "tennis ball bounce court",
    "ping pong ball bounce paddle",
    "golf club swing whoosh",
    "golf ball hit drive",
    "golf ball hole cup drop",
    "bowling ball rolling lane",
    "bowling pins strike crash",
    "billiards cue hit ball",
    "billiards balls colliding",
    "billiards ball pocket drop",
    "volleyball hit spike",
    "volleyball serve toss hit",
    "hockey puck slap shot",
    "hockey stick hit ice",
    "hockey skates on ice",

    # Gym and fitness
    "weights dropping gym thud",
    "weights plates clanging metal",
    "dumbbell rack placing",
    "barbell loading plates",
    "treadmill running belt",
    "exercise bike pedaling",
    "rowing machine sliding",
    "punching bag hit boxing",
    "jump rope spinning whoosh",
    "yoga mat unrolling",
    "stretching joints cracking",
    "whistle coach referee",
    "stopwatch click timer",
    "crowd cheering stadium",
    "crowd booing disappointed",
    "crowd gasp surprised",
    "crowd applause clapping",

    # Water sports
    "swimming stroke splash",
    "diving board spring jump",
    "diving splash entry water",
    "surfboard paddling water",
    "surfboard riding wave",
    "water skiing spray wake",
    "jet ski engine water",

    # Winter sports
    "skiing downhill snow swoosh",
    "ski poles planting snow",
    "ski lift chair moving",
    "snowboard carving snow",
    "ice skating blade cut",
    "ice skating spin scratch",
    "hockey stick puck slap",
    "curling stone sliding ice",
    "sled sliding snow whoosh",
]

# =============================================================================
# HORROR AND SUSPENSE
# =============================================================================

HORROR = [
    # Creepy sounds
    "creaking floor old wood",
    "creaking door slow opening",
    "creaking stairs footstep",
    "creaking rocking chair",
    "creaking rope swinging",
    "whisper eerie ghostly voice",
    "whisper unintelligible murmur",
    "breathing heavy ominous",
    "breathing shallow scared",
    "heartbeat slow tense",
    "heartbeat fast panic",
    "scratching wall clawing",
    "scratching door desperate",
    "tapping window finger",
    "knocking door slow creepy",
    "knocking pattern shave haircut",
    "chains rattling dungeon",
    "chains dragging floor",
    "clock ticking ominous slow",
    "music box creepy tune",
    "child laughing eerie distant",
    "crying distant muffled",
    "scream distant horror",
    "scream short sharp startled",
    "growl low threatening beast",
    "snarl aggressive monster",
    "hissing creature reptile",
    "clicking creature insectoid",
    "wet squelching organic gross",
    "bones cracking breaking",
    "flesh tearing ripping",
    "blood dripping splatter",

    # Tension builders
    "drone low rumble ominous",
    "drone high frequency tension",
    "pulse heartbeat rhythm fear",
    "static interference distorted",
    "distortion glitchy broken",
    "reverse audio eerie backward",
    "wind moan haunted hollow",
    "distant thunder rumble storm",
    "wolf howl distant lonely",
    "crow caw ominous warning",
    "raven call dark foreboding",
    "owl hoot night eerie",
    "bats wings flapping swarm",
    "rats scurrying many feet",
    "bugs crawling insects many",

    # Jump scares (short sharp)
    "stinger horror jump scare",
    "stinger sharp loud sudden",
    "stinger orchestral hit shock",
    "stinger piano slam discord",
    "stinger violin screech",
    "slam door loud sudden",
    "crash loud sudden startle",
    "scream short loud sudden",
    "gasp sharp intake breath",
]

# =============================================================================
# COMBINE ALL PROMPTS
# =============================================================================

ALL_PROMPTS = []

# Add category prefix for better organization
for p in FOOTSTEPS:
    ALL_PROMPTS.append(("footstep", p))

for p in UI_SOUNDS:
    ALL_PROMPTS.append(("ui", p))

for p in GAME_SOUNDS:
    ALL_PROMPTS.append(("game", p))

for p in NATURE_SOUNDS:
    ALL_PROMPTS.append(("nature", p))

for p in HOUSEHOLD:
    ALL_PROMPTS.append(("household", p))

for p in VEHICLES:
    ALL_PROMPTS.append(("vehicle", p))

for p in SPORTS:
    ALL_PROMPTS.append(("sports", p))

for p in HORROR:
    ALL_PROMPTS.append(("horror", p))

print(f"Total prompts to generate: {len(ALL_PROMPTS)}")
print(f"  - Footsteps: {len(FOOTSTEPS)}")
print(f"  - UI sounds: {len(UI_SOUNDS)}")
print(f"  - Game sounds: {len(GAME_SOUNDS)}")
print(f"  - Nature sounds: {len(NATURE_SOUNDS)}")
print(f"  - Household: {len(HOUSEHOLD)}")
print(f"  - Vehicles: {len(VEHICLES)}")
print(f"  - Sports: {len(SPORTS)}")
print(f"  - Horror: {len(HORROR)}")
print()

def generate_sfx(prompt, duration=5):
    """Submit a generation request."""
    try:
        resp = requests.post(
            f"{API_URL}/generate",
            json={
                "prompt": prompt,
                "duration": duration,
                "model": "audio",
                "priority": "high"
            },
            timeout=10
        )
        return resp.status_code == 200, resp.json() if resp.status_code == 200 else None
    except Exception as e:
        return False, str(e)

def wait_for_completion(job_id, timeout=120):
    """Wait for a job to complete."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{API_URL}/job/{job_id}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get('status')
                if status == 'completed':
                    return True, data
                elif status == 'failed':
                    return False, data.get('error', 'Unknown error')
            time.sleep(2)
        except (requests.RequestException, KeyError, ValueError) as e:
            # Log error but continue polling
            print(f"  Poll error: {e}", end="", flush=True)
            time.sleep(2)
    return False, "Timeout"

def main():
    generated = 0
    failed = 0

    # Resume from a specific index if provided
    start_idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    for i, (category, prompt) in enumerate(ALL_PROMPTS[start_idx:], start=start_idx + 1):
        print(f"[{i}/{len(ALL_PROMPTS)}] {category}: {prompt[:50]}...", end=" ", flush=True)

        success, result = generate_sfx(prompt)
        if not success:
            print(f"[ERR submit]")
            failed += 1
            continue

        job_id = result.get('job_id')
        if not job_id:
            print(f"[ERR no job_id]")
            failed += 1
            continue

        # Wait for completion
        success, result = wait_for_completion(job_id)
        if success:
            print("OK")
            generated += 1
        else:
            print(f"[ERR {result}]")
            failed += 1

        # Brief pause between submissions
        time.sleep(0.5)

        # Progress report every 50
        if i % 50 == 0:
            print(f"\n=== {generated} generated, {failed} failed ===\n")

    print(f"\n=== DONE: {generated} generated, {failed} failed ===")

if __name__ == "__main__":
    main()

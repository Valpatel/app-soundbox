"""
SFX Prompt Templates for Bulk Generation

Generates diverse sound effect prompts for Meta's AudioGen model.
Target: 15,000 SFX clips distributed across 10 categories.

Categories:
- impact (1500): Crashes, hits, punches, explosions
- nature (1500): Weather, water, animals, environment
- mechanical (1500): Engines, machines, tools, vehicles
- electronic (1500): Beeps, synths, tech sounds, gaming
- ambient (1500): Room tones, environments, atmospheres
- human (1000): Footsteps, breathing, crowds, actions
- scifi (1500): Space, lasers, robots, technology
- horror (1000): Creepy, monsters, suspense, gore
- ui (1500): Clicks, notifications, interface sounds
- transition (1500): Whooshes, swipes, risers, reveals

Usage:
    from sfx_templates import get_all_sfx_prompts, CATEGORY_DISTRIBUTION
    prompts = get_all_sfx_prompts()  # Returns list of {'text': str, 'category': str}

Note: AudioGen works best with descriptive prompts that include:
- Sound type (e.g., "explosion", "footsteps")
- Quality descriptors (e.g., "clean", "isolated", "loud")
- Context (e.g., "indoor", "metal surface", "sci-fi")
"""

import random
from itertools import product

# ==================== IMPACT (1500 clips) ====================
IMPACT_TEMPLATES = [
    # Basic impacts
    "A loud crash", "Heavy impact sound", "Metal hitting metal",
    "Object falling and hitting ground", "Collision sound",
    "Heavy thud", "Light tap", "Soft bump", "Hard knock",

    # Crashes
    "Car crash sound", "Glass breaking", "Window shattering",
    "Dishes breaking", "Wooden crate smashing", "Metal can crushing",
    "Building debris falling", "Wall crumbling",

    # Punches and hits
    "Punch sound effect", "Boxing punch", "Heavy punch",
    "Slap sound", "Body hit", "Combat impact",
    "Karate chop", "Kick sound", "Wrestling slam",

    # Explosions
    "Small explosion", "Distant explosion", "Muffled explosion",
    "Firecracker pop", "Fireworks bang", "Cannon fire",
    "Bomb blast", "Grenade explosion", "Artillery fire",

    # Material impacts
    "Rock hitting ground", "Stone dropping", "Gravel falling",
    "Sand pouring", "Dirt clump hitting ground", "Ice cracking",
    "Wood splintering", "Plastic crunching", "Cardboard folding",

    # Weapon sounds
    "Sword clash", "Shield hit", "Arrow impact",
    "Bullet ricochet", "Gun bolt action", "Hammer strike",
    "Axe chopping wood", "Pickaxe hitting stone", "Chainsaw cutting",
]

# ==================== NATURE (1500 clips) ====================
NATURE_TEMPLATES = [
    # Weather
    "Rain falling", "Heavy rain downpour", "Light rain drizzle",
    "Thunder rumbling", "Thunderstorm", "Lightning strike",
    "Wind blowing", "Strong wind gusts", "Howling wind",
    "Storm sounds", "Hail falling", "Snowstorm wind",

    # Water
    "River flowing", "Stream babbling", "Waterfall",
    "Ocean waves", "Waves crashing on shore", "Gentle waves lapping",
    "Water dripping", "Water splashing", "Rain on water",
    "Lake ambiance", "Underwater sounds", "Bubbles rising",

    # Animals
    "Birds chirping", "Bird singing", "Crow cawing",
    "Dog barking", "Cat meowing", "Wolf howling",
    "Horse neighing", "Cow mooing", "Sheep bleating",
    "Owl hooting", "Frog croaking", "Crickets chirping",
    "Bee buzzing", "Fly buzzing", "Mosquito sound",
    "Lion roar", "Bear growl", "Elephant trumpet",

    # Environment
    "Forest ambiance", "Jungle sounds", "Desert wind",
    "Mountain wind", "Grassland ambiance", "Swamp sounds",
    "Cave dripping", "Beach ambiance", "Campfire crackling",
    "Trees rustling", "Leaves falling", "Branch snapping",

    # Insects
    "Cicadas singing", "Grasshopper chirping", "Night insects",
    "Summer insects", "Cricket sounds", "Bug sounds",
]

# ==================== MECHANICAL (1500 clips) ====================
MECHANICAL_TEMPLATES = [
    # Engines
    "Car engine starting", "Car engine idling", "Car engine revving",
    "Motorcycle engine", "Truck engine", "Diesel engine",
    "Race car engine", "Engine accelerating", "Engine decelerating",
    "Airplane engine", "Jet engine", "Helicopter rotor",
    "Boat motor", "Lawn mower engine", "Chainsaw motor",

    # Machines
    "Factory machinery", "Industrial machine", "Assembly line",
    "Press machine", "Hydraulic press", "Stamping machine",
    "Conveyor belt", "Machine humming", "Machine whirring",
    "Drill press", "Lathe spinning", "Grinding machine",

    # Gears and mechanisms
    "Gears turning", "Clockwork mechanism", "Cog wheels",
    "Ratchet clicking", "Lever mechanism", "Pulley system",
    "Spring mechanism", "Lock clicking", "Safe dial turning",

    # Vehicles
    "Train passing", "Train horn", "Train on tracks",
    "Subway train", "Tram sounds", "Bus hydraulics",
    "Car horn honking", "Bicycle bell", "Skateboard wheels",

    # Tools
    "Power drill", "Electric saw", "Jackhammer",
    "Pneumatic hammer", "Nail gun", "Staple gun",
    "Air compressor", "Welding torch", "Blowtorch",

    # Motors and fans
    "Electric motor", "Fan spinning", "Industrial fan",
    "Ventilation system", "Air conditioner", "Refrigerator hum",
    "Washing machine", "Dryer tumbling", "Dishwasher running",
]

# ==================== ELECTRONIC (1500 clips) ====================
ELECTRONIC_TEMPLATES = [
    # Digital sounds
    "Digital beep", "Computer beep", "System notification",
    "Error sound", "Success chime", "Failure buzz",
    "Warning beep", "Alert tone", "Alarm beeping",

    # Synth sounds
    "Synthesizer pad", "Electronic drone", "Synth bass",
    "Synth lead", "Arpeggio sequence", "Electronic pulse",
    "Glitch sound", "Digital static", "Binary code sound",

    # Tech sounds
    "Computer startup", "Computer shutdown", "Hard drive spinning",
    "Floppy disk", "CD drive opening", "Printer printing",
    "Scanner scanning", "Modem dial-up", "Keyboard typing",
    "Mouse clicking", "Touchscreen tap", "Phone vibrating",

    # Retro gaming
    "8-bit game sound", "Arcade game effect", "Pixel game sound",
    "Retro jump sound", "Power up sound", "Coin collect",
    "Game over sound", "Level complete", "High score sound",

    # Modern tech
    "Smartphone notification", "Text message tone", "Email notification",
    "App launch sound", "Touch interface sound", "Voice assistant beep",
    "Smart home device", "Robot voice", "Digital assistant",

    # Radio and communication
    "Radio static", "Radio tuning", "Walkie talkie",
    "Intercom sound", "PA system", "Microphone feedback",
    "Transmission sound", "Signal interference", "Frequency sweep",
]

# ==================== AMBIENT (1500 clips) ====================
AMBIENT_TEMPLATES = [
    # Urban environments
    "City traffic", "Busy street sounds", "Downtown ambiance",
    "City park sounds", "Urban playground", "Sidewalk cafe",
    "Office building lobby", "Shopping mall ambiance", "Subway station",
    "Airport terminal", "Train station", "Bus station",

    # Indoor spaces
    "Office ambiance", "Quiet office", "Busy office",
    "Library silence", "Hospital hallway", "School hallway",
    "Restaurant ambiance", "Cafe sounds", "Bar atmosphere",
    "Kitchen sounds", "Living room ambiance", "Bedroom at night",

    # Outdoor spaces
    "Park ambiance", "Garden sounds", "Backyard birds",
    "Countryside sounds", "Farm ambiance", "Rural setting",
    "Mountain ambiance", "Forest clearing", "Meadow sounds",
    "Beach atmosphere", "Pier sounds", "Harbor ambiance",

    # Room tones
    "Empty room tone", "Large hall reverb", "Small room ambiance",
    "Basement ambiance", "Attic creaking", "Garage sounds",
    "Warehouse echo", "Factory floor", "Construction site",

    # Time of day
    "Morning ambiance", "Afternoon sounds", "Evening atmosphere",
    "Night ambiance", "Dawn chorus", "Dusk sounds",
    "Late night city", "Midnight silence", "Early morning",

    # Weather ambiance
    "Rainy day inside", "Thunderstorm ambiance", "Windy day",
    "Snowy silence", "Foggy atmosphere", "Sunny day outdoors",
]

# ==================== HUMAN (1000 clips) ====================
HUMAN_TEMPLATES = [
    # Footsteps
    "Footsteps on wood", "Footsteps on concrete", "Footsteps on gravel",
    "Walking on grass", "Running footsteps", "Slow walking",
    "High heels clicking", "Boots stomping", "Bare feet walking",
    "Sneakers squeaking", "Flip flops", "Snow crunching footsteps",

    # Breathing and body
    "Heavy breathing", "Light breathing", "Gasping for air",
    "Sighing", "Yawning", "Snoring",
    "Heartbeat", "Heart pounding", "Pulse sound",
    "Stomach growling", "Coughing", "Sneezing",

    # Actions
    "Clapping hands", "Snapping fingers", "Knocking on door",
    "Typing on keyboard", "Writing with pen", "Turning pages",
    "Drinking water", "Eating crunchy food", "Chewing",
    "Zipper sound", "Button clicking", "Velcro opening",

    # Crowds
    "Crowd murmuring", "Crowd cheering", "Stadium crowd",
    "Applause", "Audience laughing", "Party crowd",
    "Protest crowd", "Concert crowd", "Busy marketplace",

    # Voices (non-speech)
    "Humming", "Whistling", "Mumbling",
    "Gasping", "Screaming", "Whimpering",
    "Laughing", "Crying", "Groaning",
]

# ==================== SCI-FI (1500 clips) ====================
SCIFI_TEMPLATES = [
    # Space
    "Spaceship engine", "Spaceship flyby", "Space station ambiance",
    "Airlock opening", "Space door whoosh", "Hyperdrive activation",
    "Warp speed", "Space debris", "Asteroid field",
    "Planetary atmosphere entry", "Space pod ejection", "Docking sequence",

    # Lasers and weapons
    "Laser gun fire", "Laser beam", "Plasma weapon",
    "Energy blast", "Photon torpedo", "Ion cannon",
    "Stun gun", "Force field activation", "Shield impact",
    "Lightsaber hum", "Energy sword clash", "Weapon charging",

    # Robots and AI
    "Robot walking", "Robot servo motors", "Mechanical robot",
    "Android activation", "Cyborg sounds", "Drone hovering",
    "AI processing", "Computer core", "Data transfer",
    "Hologram projection", "Scanner sound", "Targeting system",

    # Technology
    "Teleporter sound", "Transporter beam", "Portal opening",
    "Time machine", "Cryogenic chamber", "Medical scanner",
    "Force field hum", "Energy barrier", "Power core",
    "Fusion reactor", "Quantum computer", "Neural interface",

    # Creatures
    "Alien creature", "Monster growl", "Creature screech",
    "Mutant sound", "Xenomorph hiss", "Space creature",
    "Alien communication", "Extraterrestrial signal", "UFO sound",

    # Atmospheres
    "Alien planet ambiance", "Space void", "Nebula sounds",
    "Black hole effects", "Zero gravity", "Vacuum of space",
]

# ==================== HORROR (1000 clips) ====================
HORROR_TEMPLATES = [
    # Creepy sounds
    "Creaking door", "Creaking floorboard", "Old stairs creaking",
    "Chains rattling", "Metal scraping", "Rusty gate",
    "Wind through broken windows", "Drafty corridor", "Whispering wind",

    # Monster sounds
    "Monster growl", "Creature snarl", "Beast roar",
    "Zombie groan", "Vampire hiss", "Werewolf howl",
    "Ghost wail", "Demon voice", "Banshee scream",
    "Creature breathing", "Monster footsteps", "Claws scratching",

    # Suspense
    "Heartbeat tension", "Breathing in darkness", "Whispers",
    "Distant screaming", "Eerie silence", "Tense drone",
    "Building dread", "Something approaching", "Stalking sounds",

    # Jump scares
    "Sudden loud noise", "Sharp stinger", "Shock sound",
    "Scary reveal", "Horror hit", "Fright sound",
    "Jumpscare effect", "Tension release", "Startling sound",

    # Environments
    "Haunted house ambiance", "Creepy forest", "Abandoned hospital",
    "Dark basement", "Creepy attic", "Graveyard at night",
    "Old mansion", "Dungeon dripping", "Catacombs echo",

    # Gore (mild)
    "Bone cracking", "Flesh tearing", "Wet impact",
    "Something dripping", "Squishy sound", "Ooze sound",
]

# ==================== UI (1500 clips) ====================
UI_TEMPLATES = [
    # Click sounds
    "Button click", "Soft click", "Hard click",
    "Toggle switch", "Checkbox click", "Radio button select",
    "Menu item select", "Tab switch", "Dropdown open",

    # Notifications
    "Notification chime", "Alert tone", "Message received",
    "Email notification", "Success sound", "Error sound",
    "Warning alert", "Confirmation beep", "Task complete",
    "Achievement unlock", "Badge earned", "Level up",

    # Navigation
    "Page turn", "Scroll sound", "Swipe sound",
    "Back button", "Forward navigation", "Home button",
    "Expand sound", "Collapse sound", "Zoom in",
    "Zoom out", "Refresh sound", "Loading indicator",

    # Actions
    "Item selected", "Item deselected", "Copy sound",
    "Paste sound", "Delete sound", "Undo sound",
    "Redo sound", "Save sound", "Open file",
    "Close window", "Minimize sound", "Maximize sound",

    # Feedback
    "Positive feedback", "Negative feedback", "Neutral feedback",
    "Hover sound", "Focus sound", "Typing sound",
    "Slider move", "Progress update", "Timer tick",

    # Game UI
    "Menu open", "Menu close", "Inventory sound",
    "Item pickup", "Item drop", "Item equip",
    "Health pickup", "Coin sound", "Points scored",
    "Game start", "Game pause", "Game resume",
]

# ==================== TRANSITION (1500 clips) ====================
TRANSITION_TEMPLATES = [
    # Whooshes
    "Whoosh sound", "Fast whoosh", "Slow whoosh",
    "Heavy whoosh", "Light whoosh", "Air whoosh",
    "Wind swoosh", "Speed whoosh", "Passing whoosh",
    "Dramatic whoosh", "Subtle whoosh", "Cinematic swoosh",

    # Swipes
    "Swipe transition", "Left swipe", "Right swipe",
    "Up swipe", "Down swipe", "Quick swipe",
    "Smooth swipe", "Paper swipe", "Digital swipe",

    # Risers and falls
    "Tension riser", "Building suspense", "Ascending tone",
    "Descending tone", "Drop sound", "Impact drop",
    "Reverse cymbal", "Uplifter sound", "Downlifter",

    # Reveals
    "Reveal sound", "Magic reveal", "Dramatic reveal",
    "Curtain opening", "Unveiling sound", "Presentation reveal",
    "Logo reveal", "Title reveal", "Scene reveal",

    # Fades
    "Fade in", "Fade out", "Crossfade",
    "Audio dissolve", "Smooth transition", "Gradual change",

    # Motion
    "Slide in", "Slide out", "Pop in",
    "Pop out", "Bounce", "Spring sound",
    "Elastic snap", "Rubber band", "Stretch sound",

    # Cinematic
    "Scene change", "Cut transition", "Flash transition",
    "Glitch transition", "Digital wipe", "Film reel",
    "Tape rewind", "Fast forward", "Time skip",
    "Dream sequence", "Flashback sound", "Memory transition",
]


# ==================== BYK3S MOTORCYCLE SOUNDS ====================
# Combinatorial generation: action × speed × surface × condition

MOTO_TIRE_ACTIONS = [
    "skidding", "sliding", "squealing", "screeching", "braking hard",
    "drifting", "spinning", "losing traction", "wheel spinning",
    "tire burnout", "peeling out", "fishtailing", "locking up",
]

MOTO_SPEEDS = [
    "low speed", "high speed", "medium speed", "very fast", "slow",
    "accelerating", "decelerating", "constant speed",
]

MOTO_SURFACES = [
    "ice", "concrete", "asphalt", "gravel", "sand", "mud", "dirt",
    "wet pavement", "metal grating", "cobblestone", "brick", "grass",
    "snow", "loose gravel", "packed dirt", "cracked asphalt",
    "painted road markings", "manhole cover", "steel plate",
]

MOTO_CONDITIONS = [
    "dry", "wet", "frozen", "icy", "muddy", "dusty", "rainy",
    "snowy", "slick", "oily", "damp", "flooded",
]

def generate_motorcycle_tire_prompts():
    """Generate all motorcycle tire sound combinations."""
    prompts = []

    # Generate all meaningful combinations
    for action in MOTO_TIRE_ACTIONS:
        for speed in MOTO_SPEEDS:
            for surface in MOTO_SURFACES:
                for condition in MOTO_CONDITIONS:
                    # Create descriptive prompt for AudioGen
                    prompt = f"Motorcycle tires {action} on {condition} {surface} at {speed}"
                    prompts.append(prompt)

    # Also add some specific variants
    specific_prompts = [
        # Ice and frozen conditions
        "Motorcycle sliding uncontrollably on black ice",
        "Bike tires spinning on frozen asphalt trying to grip",
        "High speed motorcycle skid on icy highway",
        "Motorcycle braking hard on ice, tires locking up",
        "Cyberpunk bike drifting on frozen concrete",

        # Wet conditions
        "Motorcycle hydroplaning on wet road",
        "Bike tires splashing through puddles at speed",
        "Motorcycle emergency braking on rain-soaked asphalt",
        "Wet tire squeal during hard cornering",
        "Motorcycle sliding on wet manhole cover",

        # Gravel and loose surfaces
        "Motorcycle kicking up gravel during hard acceleration",
        "Bike tires sliding sideways on loose gravel",
        "Dirt bike sliding on sandy terrain",
        "Motorcycle drifting on loose dirt road",
        "Gravel spraying from spinning motorcycle tires",

        # High performance
        "Sport bike tire screech during burnout",
        "Racing motorcycle braking from high speed",
        "Motorcycle drag racing tire spin",
        "Superbike drifting around corner",
        "Performance motorcycle tire squeal",

        # Urban surfaces
        "Motorcycle sliding on wet painted crosswalk",
        "Bike skidding on metal construction plate",
        "Motorcycle tires slipping on oily garage floor",
        "Urban bike sliding on slick city street",
        "Motorcycle emergency stop on cobblestone",

        # Weather extremes
        "Motorcycle fighting for traction in heavy rain",
        "Bike sliding on freshly fallen snow",
        "Motorcycle on hail-covered road surface",
        "Tires spinning on frost-covered bridge",
        "Motorcycle sliding during dust storm",

        # Combat/gaming specific
        "Futuristic motorcycle power slide",
        "Combat bike emergency maneuver skid",
        "Cyberpunk hover bike landing skid",
        "Military motorcycle tactical stop",
        "Armored bike sliding into cover",
    ]

    prompts.extend(specific_prompts)
    return prompts

# Pre-generate motorcycle prompts
MOTORCYCLE_TIRE_TEMPLATES = generate_motorcycle_tire_prompts()

# ==================== BYK3S ENGINE SOUNDS ====================
MOTO_ENGINE_TEMPLATES = [
    # Idle and startup
    "Motorcycle engine cold start",
    "Bike engine warming up idle",
    "Futuristic motorcycle powering on",
    "Cyberpunk bike electric motor activation",
    "Motorcycle engine idling rough",
    "Motorcycle engine idling smooth",

    # Revving
    "Motorcycle revving aggressively",
    "Bike engine revving high",
    "Low rumble motorcycle rev",
    "Quick motorcycle rev blip",
    "Sustained high RPM motorcycle",

    # Acceleration
    "Motorcycle accelerating hard from stop",
    "Bike engine accelerating through gears",
    "High speed motorcycle acceleration",
    "Motorcycle pulling away fast",
    "Bike launching from standstill",

    # Deceleration
    "Motorcycle engine braking",
    "Bike decelerating through gears",
    "Motorcycle slowing down engine rumble",
    "Engine overrun deceleration pop",
    "Motorcycle coasting engine sound",

    # Flyby
    "Motorcycle passing at high speed",
    "Bike flyby doppler effect",
    "Multiple motorcycles passing",
    "Distant motorcycle approaching",
    "Motorcycle speeding away into distance",

    # Combat/futuristic
    "Futuristic combat bike engine",
    "Cyberpunk motorcycle hover engine",
    "Military motorcycle turbine",
    "Armored bike heavy engine",
    "Energy-powered motorcycle hum",
    "Electric combat motorcycle whine",
    "Hybrid bike engine with electric assist",
    "Weaponized motorcycle power unit",
]

# ==================== BYK3S COMBAT SOUNDS ====================
BYK3S_COMBAT_TEMPLATES = [
    # Weapons on bike
    "Motorcycle mounted gun firing",
    "Bike cannon blast",
    "Combat motorcycle laser weapon",
    "Missile launch from moving bike",
    "Chain gun from speeding motorcycle",

    # Impacts on bike
    "Bullet hitting motorcycle armor",
    "Explosion near speeding bike",
    "EMP hitting motorcycle systems",
    "Shrapnel hitting bike chassis",
    "Laser strike on motorcycle shield",

    # Destruction
    "Motorcycle crashing at high speed",
    "Bike explosion from fuel tank hit",
    "Motorcycle sliding crash sparks",
    "Combat bike structural failure",
    "Motorcycle tumbling end over end",

    # Systems
    "Motorcycle shield activation",
    "Bike weapons system online",
    "Combat motorcycle radar ping",
    "Target lock on sound from bike",
    "Motorcycle stealth mode engaging",
    "Bike boost system charging",
    "Nitro injection sound",
    "Afterburner ignition",
]

# ==================== BYK3S ENVIRONMENT ====================
BYK3S_ENVIRONMENT_TEMPLATES = [
    # Cyberpunk city
    "Dystopian city traffic ambiance",
    "Neon-lit street sounds",
    "Rain on cyberpunk cityscape",
    "Industrial district machinery",
    "Underground tunnel echo",

    # Combat zones
    "Warzone distant explosions",
    "Firefight in urban setting",
    "Drone swarm overhead",
    "AI defense system alarm",
    "Data center server hum",

    # Weather in game world
    "Acid rain on metal surfaces",
    "Electromagnetic storm crackling",
    "Toxic fog swirling",
    "Nuclear winter wind howl",
    "Polluted atmosphere rumble",
]

# Category distribution for SFX
CATEGORY_DISTRIBUTION = {
    'impact': 1500,
    'nature': 1500,
    'mechanical': 1500,
    'electronic': 1500,
    'ambient': 1500,
    'human': 1000,
    'scifi': 1500,
    'horror': 1000,
    'ui': 1500,
    'transition': 1500,
    # BYK3S game-specific sounds
    'motorcycle_tire': 5000,   # All tire/surface combinations
    'motorcycle_engine': 1000,  # Engine sounds
    'byk3s_combat': 1000,      # Combat effects
    'byk3s_environment': 500,  # Game world ambiance
}


def generate_prompts_for_category(category: str, count: int) -> list:
    """Generate prompts for a specific SFX category."""
    # Map category names to template variables
    TEMPLATE_MAP = {
        'impact': IMPACT_TEMPLATES,
        'nature': NATURE_TEMPLATES,
        'mechanical': MECHANICAL_TEMPLATES,
        'electronic': ELECTRONIC_TEMPLATES,
        'ambient': AMBIENT_TEMPLATES,
        'human': HUMAN_TEMPLATES,
        'scifi': SCIFI_TEMPLATES,
        'horror': HORROR_TEMPLATES,
        'ui': UI_TEMPLATES,
        'transition': TRANSITION_TEMPLATES,
        'motorcycle_tire': MOTORCYCLE_TIRE_TEMPLATES,
        'motorcycle_engine': MOTO_ENGINE_TEMPLATES,
        'byk3s_combat': BYK3S_COMBAT_TEMPLATES,
        'byk3s_environment': BYK3S_ENVIRONMENT_TEMPLATES,
    }

    templates = TEMPLATE_MAP.get(category, [])

    if not templates:
        return []

    prompts = list(templates)

    # If we need more prompts, create variations
    while len(prompts) < count:
        for template in templates:
            if len(prompts) >= count:
                break
            # Add variations
            variations = [
                f"Short {template.lower()}",
                f"Long {template.lower()}",
                f"{template} sound effect",
                f"Clean {template.lower()}",
                f"Loud {template.lower()}",
                f"Soft {template.lower()}",
            ]
            for var in variations:
                if len(prompts) >= count:
                    break
                prompts.append(var)

    # Shuffle and trim
    random.shuffle(prompts)
    return prompts[:count]


def get_all_sfx_prompts() -> list:
    """Generate all SFX prompts with categories."""
    all_prompts = []

    for category, count in CATEGORY_DISTRIBUTION.items():
        prompts = generate_prompts_for_category(category, count)
        for prompt in prompts:
            all_prompts.append({
                'text': prompt,
                'category': category,
            })

    random.shuffle(all_prompts)
    return all_prompts


if __name__ == '__main__':
    # Test generation
    prompts = get_all_sfx_prompts()
    print(f"Generated {len(prompts)} SFX prompts")

    # Show distribution
    from collections import Counter
    categories = Counter(p['category'] for p in prompts)
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

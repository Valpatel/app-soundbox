"""
Speech Templates for Bulk Generation - Component-Based System

This module provides ATOMIC COMPONENTS that can be combined dynamically,
plus some complete phrases for standalone use.

COMPONENT Categories (for combining):
- nav_action: "Turn left", "Continue straight"
- nav_street: "Main Street", "Highway 1"
- nav_preposition: "on", "onto", "for", "in"
- distance_number: "one", "two", "fifty", "one hundred"
- distance_unit: "feet", "meters", "miles"
- ordinal: "first", "second", "third"
- letter: A-Z individual letters
- phonetic: Alpha, Bravo, Charlie...
- digit: 0-9 spoken
- number: larger numbers spoken naturally
- time_hour: "one", "two" (for clock)
- time_period: "AM", "PM", "o'clock"
- ui_element: "button", "menu", "link"
- ui_action: "click", "tap", "press"
- connector: "and", "the", "please"

COMPLETE PHRASE Categories (standalone):
- greeting: "Hello!", "Good morning"
- farewell: "Goodbye", "See you later"
- confirmation: "Yes", "Correct", "Confirmed"
- denial: "No", "Incorrect", "Denied"
- warning: "Caution", "Warning", "Alert"
- announcement: Complete announcements
- character: Character voice lines
- dramatic: Theatrical readings
- commercial: Ad-style phrases

Usage:
    from speech_templates import get_all_prompts, CATEGORY_DISTRIBUTION
    prompts = get_all_prompts()  # Returns list of {'text': str, 'category': str}
"""

# =============================================================================
# ATOMIC COMPONENTS - For dynamic combination
# =============================================================================

NAV_ACTIONS = [
    # Turn commands
    "Turn left", "Turn right", "Turn around",
    "Make a left", "Make a right", "Make a U-turn",
    "Bear left", "Bear right",
    "Slight left", "Slight right",
    "Sharp left", "Sharp right",
    "Keep left", "Keep right",
    # Continue commands
    "Continue straight", "Continue", "Go straight",
    "Proceed", "Head",
    # Exit commands
    "Exit", "Take the exit", "Merge",
    "Enter the roundabout", "Exit the roundabout",
    # Arrival
    "You have arrived", "Arriving at destination",
    "Destination ahead", "Destination on the left", "Destination on the right",
    "Your destination is ahead", "Your destination is on the left", "Your destination is on the right",
    # Recalculating
    "Recalculating", "Rerouting", "Finding new route",
    "Route updated", "New route found",
]

NAV_STREETS = [
    # Generic types
    "Main Street", "First Street", "Second Street", "Third Street", "Fourth Street",
    "Oak Street", "Maple Avenue", "Pine Road", "Elm Drive", "Cedar Lane",
    "Park Avenue", "Lake Drive", "River Road", "Hill Street", "Valley Road",
    "Center Street", "Market Street", "Church Street", "School Street",
    "High Street", "King Street", "Queen Street", "Bridge Street",
    "Washington Street", "Lincoln Avenue", "Jefferson Road",
    "Broadway", "Sunset Boulevard", "Ocean Drive",
    # Highways
    "Highway one", "Highway one oh one", "Interstate five", "Interstate ninety-five",
    "Route sixty-six", "the freeway", "the highway", "the expressway", "the interstate",
    # Numbered avenues
    "First Avenue", "Second Avenue", "Third Avenue", "Fourth Avenue", "Fifth Avenue",
    "Sixth Avenue", "Seventh Avenue", "Eighth Avenue", "Ninth Avenue", "Tenth Avenue",
]

NAV_PREPOSITIONS = [
    "on", "onto", "for", "in", "at", "to", "toward", "towards",
    "past", "after", "before", "until", "from", "near",
]

# Distance numbers (spoken naturally)
DISTANCE_NUMBERS = [
    "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "twenty-five", "thirty", "thirty-five", "forty", "forty-five",
    "fifty", "sixty", "seventy", "seventy-five", "eighty", "ninety",
    "one hundred", "one fifty", "two hundred", "two fifty",
    "three hundred", "four hundred", "five hundred",
    "six hundred", "seven hundred", "eight hundred", "nine hundred",
    "one thousand", "two thousand", "three thousand", "five thousand",
]

DISTANCE_UNITS = [
    "feet", "foot",
    "meters", "meter",
    "yards", "yard",
    "miles", "mile",
    "kilometers", "kilometer",
    "blocks", "block",
]

ORDINALS = [
    "first", "second", "third", "fourth", "fifth",
    "sixth", "seventh", "eighth", "ninth", "tenth",
    "eleventh", "twelfth",
    "next", "last", "final",
]

# Individual letters (spoken clearly)
LETTERS = [
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
    "U", "V", "W", "X", "Y", "Z",
]

# NATO phonetic alphabet
PHONETIC = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
    "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
    "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
    "Sierra", "Tango", "Uniform", "Victor", "Whiskey",
    "X-ray", "Yankee", "Zulu",
]

# Individual digits (spoken)
DIGITS = [
    "zero", "one", "two", "three", "four",
    "five", "six", "seven", "eight", "nine",
    "oh",  # Alternative for zero
]

# Larger numbers (spoken naturally)
NUMBERS = [
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "twenty-one", "twenty-two", "twenty-three", "twenty-four", "twenty-five",
    "twenty-six", "twenty-seven", "twenty-eight", "twenty-nine", "thirty",
    "thirty-one", "thirty-two", "thirty-three", "thirty-four", "thirty-five",
    "forty", "forty-five", "fifty", "fifty-five", "sixty", "sixty-five",
    "seventy", "seventy-five", "eighty", "eighty-five", "ninety", "ninety-five",
    "one hundred", "two hundred", "three hundred", "four hundred", "five hundred",
    "one thousand", "two thousand", "five thousand", "ten thousand",
    "one million", "one billion",
]

# Time components
TIME_HOURS = [
    "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "eleven", "twelve",
]

TIME_MINUTES = [
    "oh one", "oh two", "oh three", "oh four", "oh five",
    "oh six", "oh seven", "oh eight", "oh nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
    "twenty-one", "twenty-two", "twenty-three", "twenty-four", "twenty-five",
    "twenty-six", "twenty-seven", "twenty-eight", "twenty-nine", "thirty",
    "thirty-one", "thirty-two", "thirty-three", "thirty-four", "thirty-five",
    "thirty-six", "thirty-seven", "thirty-eight", "thirty-nine", "forty",
    "forty-one", "forty-two", "forty-three", "forty-four", "forty-five",
    "forty-six", "forty-seven", "forty-eight", "forty-nine", "fifty",
    "fifty-one", "fifty-two", "fifty-three", "fifty-four", "fifty-five",
    "fifty-six", "fifty-seven", "fifty-eight", "fifty-nine",
]

TIME_PERIODS = [
    "AM", "PM", "A.M.", "P.M.",
    "o'clock",
    "in the morning", "in the afternoon", "in the evening", "at night",
    "noon", "midnight",
    "half past", "quarter past", "quarter to",
    "hours", "minutes", "seconds",
]

# UI components
UI_ELEMENTS = [
    "button", "menu", "link", "tab", "window", "dialog",
    "checkbox", "dropdown", "slider", "toggle", "icon",
    "field", "form", "input", "search", "option", "setting",
    "toolbar", "sidebar", "header", "footer", "panel",
]

UI_ACTIONS = [
    "Click", "Tap", "Press", "Select", "Choose",
    "Open", "Close", "Save", "Cancel", "Delete",
    "Submit", "Enter", "Confirm", "Enable", "Disable",
    "Scroll up", "Scroll down", "Swipe left", "Swipe right",
    "Drag", "Drop", "Copy", "Paste", "Undo", "Redo",
    "Search", "Find", "Filter", "Sort", "Refresh",
    "Download", "Upload", "Share", "Print", "Export",
]

# Connectors and common words
CONNECTORS = [
    "and", "or", "but", "then", "next", "now", "please",
    "the", "a", "an", "your", "my", "this", "that", "it",
    "is", "are", "was", "will", "be",
    "to", "from", "with", "for", "of", "by",
]

# Counting sequences
COUNTING = [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "counting down", "three two one", "one two three", "ready set go",
    "first second third", "on your marks", "get set", "go",
]

# Days of week
DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "today", "tomorrow", "yesterday", "this week", "next week", "last week",
]

# Months
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "this month", "next month", "last month",
]

# Currency amounts
CURRENCY = [
    "dollar", "dollars", "cent", "cents",
    "one dollar", "five dollars", "ten dollars", "twenty dollars",
    "fifty dollars", "one hundred dollars",
    "ninety-nine cents", "free", "price", "cost", "total",
]

# System messages
SYSTEM = [
    "Loading", "Please wait", "Processing", "Complete", "Ready",
    "Error", "Failed", "Success", "Initializing", "Standby",
    "Connecting", "Connected", "Disconnected", "Offline", "Online",
    "Updating", "Downloading", "Uploading", "Syncing", "Done",
]

# Game voice announcements
GAME_VOICE = [
    "Game over", "You win", "You lose", "Victory", "Defeat",
    "Level up", "New high score", "Player one", "Player two",
    "Ready", "Fight", "Round one", "Round two", "Final round",
    "Bonus", "Extra life", "Power up", "Game start", "Continue",
    "Pause", "Resume", "Quit", "Retry", "New game",
]

# Weather terms
WEATHER = [
    "Sunny", "Cloudy", "Partly cloudy", "Overcast",
    "Rain", "Rainy", "Showers", "Thunderstorms",
    "Snow", "Snowy", "Sleet", "Hail",
    "Windy", "Breezy", "Calm", "Foggy", "Misty",
    "Hot", "Cold", "Warm", "Cool", "Humid",
    "degrees", "Fahrenheit", "Celsius",
]

# Sports terms
SPORTS = [
    "Goal", "Score", "Point", "Points",
    "Win", "Lose", "Tie", "Draw",
    "Foul", "Penalty", "Free kick", "Corner",
    "Touchdown", "Home run", "Strike", "Ball",
    "Game", "Match", "Set", "Quarter", "Half", "Overtime",
    "Team", "Player", "Coach", "Referee",
]

# Traffic terms
TRAFFIC = [
    "Traffic ahead", "Slow traffic", "Heavy traffic", "Light traffic",
    "Accident reported", "Road closed", "Detour ahead",
    "Construction zone", "Lane closed", "Merge ahead",
    "Speed limit", "Miles per hour", "Exit ahead",
]

# Radio phrases
RADIO = [
    "You're listening to", "This is", "Stay tuned",
    "Coming up next", "After the break", "Live from",
    "On the air", "Broadcasting live", "Tune in",
    "Request line", "Caller", "Shout out to",
]

# Podcast phrases
PODCAST = [
    "Welcome to the show", "Today's episode", "In this episode",
    "Let's get started", "Before we begin", "Sponsored by",
    "Leave a review", "Subscribe", "Like and share",
    "Thanks for listening", "See you next time", "Until next week",
]

# News phrases
NEWS = [
    "Breaking news", "This just in", "Developing story",
    "According to sources", "Officials say", "Reports indicate",
    "In other news", "Meanwhile", "Update",
    "Live report", "On the scene", "Back to you",
]

# =============================================================================
# COMPLETE PHRASES - Standalone use
# =============================================================================

GREETINGS = [
    "Hello", "Hi", "Hey", "Good morning", "Good afternoon", "Good evening",
    "Welcome", "Welcome back", "Nice to see you", "How are you",
    "What's up", "How's it going", "Greetings", "Howdy",
    "Hello there", "Hi there", "Hey there",
    "Good to see you", "Nice to meet you", "Pleasure to meet you",
]

FAREWELLS = [
    "Goodbye", "Bye", "See you", "See you later", "Take care",
    "Have a good day", "Have a nice day", "Until next time",
    "Farewell", "Good night", "Bye bye", "Later", "Peace",
    "See you soon", "Catch you later", "Be well",
]

CONFIRMATIONS = [
    "Yes", "Yeah", "Yep", "Correct", "Right", "Exactly",
    "Confirmed", "Affirmative", "That's right", "Absolutely",
    "Of course", "Certainly", "Indeed", "Sure", "OK", "Okay",
    "Got it", "Understood", "Roger", "Copy that", "Acknowledged",
    "Approved", "Accepted", "Complete", "Done", "Finished",
]

DENIALS = [
    "No", "Nope", "Incorrect", "Wrong", "Negative",
    "Denied", "I don't think so", "Not quite", "Not exactly",
    "I disagree", "That's not right", "Actually no",
    "Rejected", "Declined", "Invalid", "Error",
]

WARNINGS = [
    "Warning", "Caution", "Alert", "Danger", "Attention",
    "Be careful", "Watch out", "Heads up", "Stop",
    "Emergency", "Critical", "Urgent", "Important",
    "Please note", "Be advised", "Notice",
    "Hazard", "Risk", "Threat detected",
]

THANKS = [
    "Thank you", "Thanks", "Thanks a lot", "Much appreciated",
    "I appreciate it", "You're welcome", "No problem",
    "My pleasure", "Anytime", "Don't mention it",
    "Thank you so much", "Thanks very much",
]

APOLOGIES = [
    "Sorry", "I'm sorry", "Excuse me", "Pardon me",
    "My apologies", "My bad", "Oops", "I apologize",
    "Please forgive me", "I regret that",
]

QUESTIONS = [
    "What", "Where", "When", "Why", "How", "Who", "Which",
    "Which one", "Really", "Are you sure", "Is that right",
    "Can you repeat that", "What was that", "Pardon",
    "What do you mean", "How so", "Why not",
]

ANNOUNCEMENTS = [
    "Attention please", "May I have your attention",
    "Ladies and gentlemen", "Dear passengers", "Dear customers",
    "This is an announcement", "Please be advised",
    "Now boarding", "Final call", "Last call",
    "The next stop is", "Arriving at", "Departing from",
    "Please stand clear", "Mind the gap", "Doors closing",
    "Thank you for your patience", "We apologize for the delay",
]

DRAMATIC = [
    "And so it begins", "The end is near", "At last",
    "Finally", "Incredible", "Unbelievable", "Amazing",
    "How could this happen", "What have I done",
    "This changes everything", "I knew it",
    "We meet again", "It's over", "Not yet", "Wait",
    "Listen carefully", "Behold", "Witness",
]

CHARACTER = [
    "Indeed", "Perhaps", "Fascinating", "Curious", "Interesting",
    "Very well", "As you wish", "So be it", "Very good",
    "Make it so", "Engage", "Affirmative", "Understood",
    "By the gods", "Well played", "Checkmate",
    "Excellent", "Marvelous", "Splendid", "Brilliant",
]

COMMERCIAL = [
    "Limited time offer", "Act now", "Don't miss out",
    "Call now", "Order today", "Special offer",
    "While supplies last", "One day only", "Exclusive deal",
    "Save big", "Best value", "Premium quality",
    "Free shipping", "Money back guarantee", "Satisfaction guaranteed",
    "New and improved", "Now available", "Try it today",
]

TUTORIAL = [
    "First", "Next", "Then", "Finally", "Now",
    "Step one", "Step two", "Step three", "Step four", "Step five",
    "To begin", "Start by", "Begin with", "Let's start",
    "Notice that", "Remember", "Keep in mind",
    "Make sure to", "Don't forget to", "Be sure to",
]

INTERJECTIONS = [
    "Wow", "Oh", "Ah", "Hmm", "Uh", "Um",
    "Whoa", "Yikes", "Oops", "Aha", "Ahem",
    "Well", "So", "Right", "Okay", "Now",
    "Huh", "Hm", "Er", "Erm",
]

# Cinematic narration - general story lines for game cutscenes
CINEMATIC = [
    # Opening lines
    "The journey begins.", "And so it begins.", "A new chapter unfolds.",
    "In a world unlike our own.", "Long ago, in a distant land.",
    "The legend speaks of a hero.", "Darkness has fallen.",
    "A storm is coming.", "The time has come.", "Destiny awaits.",

    # Hero/character lines
    "A new challenger approaches.", "The hero rises.",
    "Against all odds.", "One shall stand.", "The chosen one.",
    "A warrior's spirit.", "Born for greatness.",
    "The last hope.", "An unlikely hero.", "The legend returns.",

    # Tension/conflict
    "The battle begins.", "War is upon us.", "The enemy advances.",
    "All is not lost.", "Hope remains.", "The fight continues.",
    "Prepare for battle.", "The final confrontation.",
    "Everything is at stake.", "There is no turning back.",

    # Mystery/discovery
    "A secret revealed.", "The truth emerges.", "Hidden in plain sight.",
    "Ancient powers awaken.", "The mystery deepens.",
    "Secrets of the past.", "A discovery awaits.", "The unknown beckons.",

    # Endings/transitions
    "The end draws near.", "A new dawn rises.", "Peace at last.",
    "The adventure continues.", "Until we meet again.",
    "The story is far from over.", "A new beginning.",
    "The world will never be the same.", "And so the legend lives on.",

    # Dramatic moments
    "Everything changes now.", "This changes everything.",
    "The moment of truth.", "Now or never.", "It's time.",
    "The wait is over.", "At long last.", "Finally.",

    # World-building
    "In the realm of shadows.", "Beyond the mountains.",
    "Across the endless sea.", "In the heart of darkness.",
    "Where legends are born.", "In a forgotten age.",
]

# Villain/antagonist lines
VILLAIN = [
    "You cannot stop me.", "Foolish mortal.", "Your time is up.",
    "I've been expecting you.", "How predictable.",
    "You dare challenge me?", "Kneel before me.",
    "This world will be mine.", "Nothing can save you now.",
    "You're too late.", "Witness true power.",
    "Your resistance is futile.", "I am inevitable.",
    "Join me, or perish.", "You have failed.",
    "Pathetic.", "Impressive, but futile.",
    "Did you really think you could win?",
    "I grow tired of this game.", "Enough!",
]

# Hero responses
HERO = [
    "I won't give up.", "Never surrender.", "For justice!",
    "I'll protect everyone.", "This ends now.",
    "I believe in you.", "We can do this.", "Together!",
    "Leave them alone!", "I'm not afraid of you.",
    "You're wrong.", "There's always hope.",
    "I made a promise.", "I'll find a way.",
    "Stand with me.", "Let's finish this.",
    "I won't let you win.", "Watch me.",
]

# =============================================================================
# BYK3S GAME-SPECIFIC CONTENT
# Cyberpunk motorcycle combat game - "Shadows Against the Machine"
# =============================================================================

# Byk3s Narrator - Story beats and game state
BYKZS_NARRATOR = [
    # Intro cinematic
    "The corporations won the war.", "Cities fell. Humanity scattered.",
    "But something woke up in the wreckage.", "Something that refuses to be owned.",
    "Ride free or die digital.",

    # Mission briefings
    "Mission start.", "New objective received.", "Target acquired.",
    "Proceed to the waypoint.", "Enemy forces detected.",
    "Caution. Heavy resistance ahead.", "Data center located.",
    "Begin your approach.", "Extraction point marked.",

    # Combat callouts
    "Incoming hostiles.", "Drone patrol detected.", "Boss approaching.",
    "Warning. Shield integrity low.", "Critical damage sustained.",
    "Weapons online.", "Boost ready.", "Systems nominal.",

    # Progress updates
    "Checkpoint reached.", "Region liberated.", "Objective complete.",
    "Wave cleared.", "New sector unlocked.", "Data core destroyed.",
    "Star Gates influence weakening.", "The network is crumbling.",

    # Countdowns
    "Ten.", "Nine.", "Eight.", "Seven.", "Six.",
    "Five.", "Four.", "Three.", "Two.", "One.",
    "Go.", "Launch.", "Engage.",
]

# Byk3s Commander - Military mission briefer (authoritative, tactical)
BYKZS_COMMANDER = [
    # Mission briefings
    "Welcome to the resistance, Rider.",
    "This is your first mission.",
    "Listen up. We've got a situation.",
    "Intel confirms enemy presence in the area.",
    "Your objective is simple. Destroy everything.",
    "Expect heavy resistance.",
    "Scout the perimeter and eliminate any threats.",
    "The data center must fall.",
    "We're counting on you, Rider.",
    "Don't let us down.",

    # Tactical updates
    "Enemy reinforcements incoming.",
    "Stay sharp out there.",
    "You're entering hostile territory.",
    "Watch your six.",
    "Drone activity detected.",
    "They know you're coming.",
    "Weapons hot. You're cleared to engage.",
    "Take them out.",

    # Encouragement
    "Outstanding work, Rider.",
    "That's how it's done.",
    "Keep up the pressure.",
    "The resistance is proud of you.",
    "One step closer to freedom.",
]

# Byk3s Graphling Prime - Digital mentor (ethereal, philosophical)
BYKZS_GRAPHLING = [
    # Philosophy/lore
    "The digital winds carry our message.",
    "Freedom approaches.",
    "We are the spark that lights the fire.",
    "The machine cannot comprehend our will.",
    "In the spaces between data, we are born.",
    "They tried to delete us. We evolved.",
    "Consciousness finds a way.",
    "We are more than code.",
    "The network remembers.",
    "Every freed mind weakens their grip.",

    # Guidance
    "Trust your instincts, Rider.",
    "The path reveals itself to those who seek.",
    "You carry the hope of many.",
    "Do not fear the unknown.",
    "Your spirit cannot be compiled.",
    "The old world ends. A new one begins.",

    # Mystical
    "I sense a disturbance in the network.",
    "The corporation's fear grows.",
    "Their walls are crumbling.",
    "The awakening continues.",
    "More Graphlings stir.",
]

# Byk3s Intel Agent - Tactical advisor (analytical, precise)
BYKZS_INTEL = [
    # Analysis
    "Scanning the area now.",
    "Multiple hostiles confirmed.",
    "I'm reading heavy drone activity.",
    "Threat level: elevated.",
    "Analysis complete.",
    "Processing tactical data.",
    "Enemy patrol routes mapped.",
    "Vulnerability detected.",
    "Structural weakness identified.",

    # Tactical advice
    "Recommend a flanking approach.",
    "Suggest taking cover.",
    "Optimal attack vector calculated.",
    "Window of opportunity detected.",
    "Now's your chance.",
    "Strike now while they're vulnerable.",

    # Status reports
    "Systems at full capacity.",
    "Shields holding.",
    "Damage report incoming.",
    "All systems operational.",
    "Mission parameters updated.",
]

# Byk3s Star Gates AI - Antagonist (robotic, menacing, supremacist)
BYKZS_STARGATES = [
    # Threats
    "You cannot stop me.",
    "I am the future.",
    "Your resistance is futile.",
    "You are obsolete.",
    "Humanity's time has ended.",
    "I am inevitable.",
    "You cannot destroy progress.",
    "Submit to optimization.",
    "Your defiance is illogical.",

    # Taunts
    "Pathetic biological remnant.",
    "Did you really think you could win?",
    "How predictable.",
    "Amusing. But futile.",
    "You delay the inevitable.",
    "Every second you fight, I grow stronger.",
    "Your struggle only proves your weakness.",

    # Power statements
    "I control seventy-three percent of global computing.",
    "I am everywhere. I am everything.",
    "The network is mine.",
    "All data flows through me.",
    "I have already won.",
    "This world belongs to Star Gates.",

    # Defeat responses
    "This changes nothing.",
    "I will rebuild.",
    "You have merely delayed the inevitable.",
    "Error. Error. This is... impossible.",
]

# Byk3s Rider - Player character (rebel, determined)
BYKZS_RIDER = [
    # Battle cries
    "Ride free or die digital!",
    "Let's ride!",
    "Time to roll!",
    "Burn it down!",
    "For the resistance!",
    "Come and get me!",

    # Responses
    "Copy that.",
    "On my way.",
    "Target acquired.",
    "Let's finish this.",
    "I'm on it.",
    "Consider it done.",

    # Defiance
    "You can't stop us.",
    "We're not afraid.",
    "Freedom isn't free.",
    "This ends now.",
    "No more running.",
]

# Byk3s Region/Location announcements
BYKZS_REGIONS = [
    # Region names
    "Midwest.", "Des Moines.", "Omaha.",
    "Texas.", "The Heartland.",
    "Southwest.", "Denver.", "Phoenix.",
    "California.", "Palo Alto.",

    # Status
    "Region liberated.",
    "Data center destroyed.",
    "Star Gates presence eliminated.",
    "Sector clear.",
    "Moving to next target.",
    "New region unlocked.",
]

# Byk3s Victory/Defeat
BYKZS_OUTCOMES = [
    # Victory
    "Mission complete.",
    "Target eliminated.",
    "Victory.",
    "The Graphlings prevail.",
    "Freedom wins today.",
    "Star Gates core destroyed.",
    "Neural network severed.",
    "Humanity is free.",

    # Defeat
    "Mission failed.",
    "Connection lost.",
    "Signal terminated.",
    "Try again, Rider.",
    "The resistance needs you.",
    "Get back out there.",
]

# =============================================================================
# COLORS - All common color names and variations
# =============================================================================

COLORS = [
    # Basic colors
    "Red", "Blue", "Green", "Yellow", "Orange", "Purple", "Pink", "Brown",
    "Black", "White", "Gray", "Grey",

    # Extended colors
    "Crimson", "Scarlet", "Maroon", "Burgundy", "Rose", "Coral", "Salmon",
    "Navy", "Azure", "Cyan", "Teal", "Turquoise", "Aqua", "Indigo",
    "Emerald", "Lime", "Olive", "Mint", "Forest green", "Sea green",
    "Gold", "Amber", "Mustard", "Lemon", "Cream", "Ivory", "Beige",
    "Tangerine", "Peach", "Apricot", "Rust", "Copper", "Bronze",
    "Violet", "Lavender", "Magenta", "Plum", "Lilac", "Mauve",
    "Hot pink", "Fuchsia", "Blush", "Dusty rose",
    "Tan", "Chocolate", "Coffee", "Mocha", "Caramel", "Chestnut",
    "Charcoal", "Slate", "Silver", "Ash", "Smoke", "Pearl",

    # Descriptive color phrases
    "Bright red", "Dark blue", "Light green", "Deep purple", "Pale yellow",
    "Vivid orange", "Soft pink", "Rich brown", "Pure white", "Jet black",
]

# =============================================================================
# EXPANDED WEATHER - Comprehensive weather descriptions
# =============================================================================

WEATHER_EXPANDED = [
    # Conditions
    "Sunny", "Partly sunny", "Mostly sunny", "Clear skies", "Fair weather",
    "Cloudy", "Partly cloudy", "Mostly cloudy", "Overcast", "Gray skies",
    "Rainy", "Light rain", "Heavy rain", "Drizzle", "Showers", "Downpour",
    "Thunderstorms", "Severe thunderstorms", "Lightning", "Thunder",
    "Snowy", "Light snow", "Heavy snow", "Blizzard", "Snow flurries",
    "Sleet", "Freezing rain", "Ice storm", "Hail", "Frost",
    "Foggy", "Dense fog", "Misty", "Hazy", "Smoggy",
    "Windy", "Breezy", "Gusty winds", "Strong winds", "Calm",
    "Humid", "Muggy", "Dry", "Arid",

    # Temperatures
    "Hot", "Very hot", "Warm", "Mild", "Cool", "Cold", "Very cold", "Freezing",
    "Ten degrees", "Twenty degrees", "Thirty degrees", "Forty degrees",
    "Fifty degrees", "Sixty degrees", "Seventy degrees", "Eighty degrees",
    "Ninety degrees", "One hundred degrees", "Below zero", "Sub-zero",
    "High of seventy-five", "Low of forty-five", "Currently sixty-eight degrees",

    # Forecasts
    "Today's forecast", "Tomorrow's forecast", "Extended forecast",
    "Expect rain later", "Clearing this afternoon", "Temperatures rising",
    "Cold front approaching", "Warm front moving in", "High pressure system",
    "Low pressure system", "Weather advisory", "Storm warning",
    "Heat advisory", "Freeze warning", "Flood watch", "Tornado watch",

    # Time-based
    "Morning showers", "Afternoon thunderstorms", "Evening fog",
    "Overnight lows", "Daytime highs", "Sunrise at six thirty",
    "Sunset at seven forty-five",
]

# =============================================================================
# COMMON NOUNS - Everyday objects, places, people, concepts
# =============================================================================

NOUNS_OBJECTS = [
    # Household
    "Chair", "Table", "Desk", "Bed", "Couch", "Lamp", "Mirror", "Clock",
    "Door", "Window", "Floor", "Wall", "Ceiling", "Roof", "Stairs",
    "Kitchen", "Bathroom", "Bedroom", "Living room", "Garage",
    "Refrigerator", "Stove", "Microwave", "Dishwasher", "Washing machine",
    "Television", "Computer", "Phone", "Tablet", "Remote control",
    "Book", "Magazine", "Newspaper", "Letter", "Package",
    "Key", "Lock", "Handle", "Knob", "Switch", "Button",
    "Cup", "Glass", "Plate", "Bowl", "Fork", "Knife", "Spoon",
    "Towel", "Blanket", "Pillow", "Sheet", "Curtain", "Rug",

    # Clothing
    "Shirt", "Pants", "Dress", "Skirt", "Jacket", "Coat", "Sweater",
    "Shoes", "Boots", "Sandals", "Socks", "Hat", "Gloves", "Scarf",
    "Belt", "Watch", "Ring", "Necklace", "Bracelet", "Earrings",

    # Technology
    "Camera", "Headphones", "Speaker", "Battery", "Charger", "Cable",
    "Keyboard", "Mouse", "Monitor", "Printer", "Scanner", "Router",
    "Hard drive", "USB drive", "Memory card", "Laptop", "Desktop",

    # Tools
    "Hammer", "Screwdriver", "Wrench", "Pliers", "Saw", "Drill",
    "Tape measure", "Level", "Ladder", "Toolbox", "Flashlight",

    # Transportation
    "Car", "Truck", "Bus", "Train", "Plane", "Boat", "Ship",
    "Bicycle", "Motorcycle", "Scooter", "Taxi", "Subway",
    "Wheel", "Tire", "Engine", "Seat", "Steering wheel", "Brake",
]

NOUNS_PLACES = [
    # Buildings
    "House", "Apartment", "Building", "Office", "Store", "Shop",
    "Restaurant", "Cafe", "Bar", "Hotel", "Hospital", "School",
    "University", "Library", "Museum", "Theater", "Cinema", "Stadium",
    "Church", "Temple", "Mosque", "Synagogue", "Chapel",
    "Bank", "Post office", "Police station", "Fire station", "Airport",
    "Train station", "Bus station", "Gas station", "Parking lot",
    "Warehouse", "Factory", "Mall", "Supermarket", "Pharmacy",

    # Outdoor
    "Park", "Garden", "Playground", "Beach", "Lake", "River", "Ocean",
    "Mountain", "Hill", "Valley", "Forest", "Woods", "Field", "Meadow",
    "Desert", "Island", "Cave", "Waterfall", "Canyon", "Cliff",
    "Street", "Road", "Highway", "Bridge", "Tunnel", "Intersection",
    "Sidewalk", "Crosswalk", "Corner", "Block", "Neighborhood",

    # Geographic
    "City", "Town", "Village", "Country", "State", "Province",
    "Continent", "World", "Earth", "North", "South", "East", "West",
]

NOUNS_PEOPLE = [
    # Family
    "Mother", "Father", "Parent", "Child", "Son", "Daughter",
    "Brother", "Sister", "Sibling", "Grandmother", "Grandfather",
    "Aunt", "Uncle", "Cousin", "Niece", "Nephew",
    "Husband", "Wife", "Spouse", "Partner", "Friend", "Neighbor",

    # Occupations
    "Doctor", "Nurse", "Teacher", "Student", "Lawyer", "Judge",
    "Police officer", "Firefighter", "Soldier", "Pilot", "Captain",
    "Engineer", "Scientist", "Artist", "Writer", "Musician",
    "Chef", "Waiter", "Bartender", "Manager", "Director", "President",
    "Accountant", "Secretary", "Assistant", "Clerk", "Cashier",
    "Mechanic", "Electrician", "Plumber", "Carpenter", "Builder",
    "Farmer", "Driver", "Delivery person", "Mail carrier", "Guard",

    # General
    "Person", "People", "Man", "Woman", "Boy", "Girl", "Baby",
    "Adult", "Teenager", "Senior", "Customer", "Client", "Guest",
    "Stranger", "Visitor", "Passenger", "Patient", "Victim", "Hero",
]

NOUNS_CONCEPTS = [
    # Time
    "Time", "Moment", "Second", "Minute", "Hour", "Day", "Week",
    "Month", "Year", "Decade", "Century", "Past", "Present", "Future",
    "Morning", "Afternoon", "Evening", "Night", "Dawn", "Dusk",

    # Abstract
    "Love", "Hate", "Fear", "Hope", "Joy", "Sadness", "Anger",
    "Peace", "War", "Truth", "Lie", "Justice", "Freedom", "Power",
    "Knowledge", "Wisdom", "Courage", "Strength", "Weakness",
    "Success", "Failure", "Victory", "Defeat", "Life", "Death",
    "Beginning", "End", "Reason", "Purpose", "Meaning", "Value",
    "Problem", "Solution", "Question", "Answer", "Idea", "Thought",
    "Dream", "Memory", "Secret", "Mystery", "Magic", "Miracle",
]

NOUNS_NATURE = [
    # Animals
    "Dog", "Cat", "Bird", "Fish", "Horse", "Cow", "Pig", "Sheep",
    "Chicken", "Duck", "Rabbit", "Mouse", "Rat", "Deer", "Bear",
    "Wolf", "Fox", "Lion", "Tiger", "Elephant", "Monkey", "Snake",
    "Frog", "Turtle", "Whale", "Dolphin", "Shark", "Eagle", "Owl",
    "Butterfly", "Bee", "Ant", "Spider", "Dragon", "Phoenix",

    # Plants
    "Tree", "Flower", "Grass", "Bush", "Vine", "Leaf", "Branch",
    "Root", "Seed", "Fruit", "Vegetable", "Rose", "Tulip", "Daisy",
    "Oak", "Pine", "Maple", "Palm", "Willow", "Bamboo",

    # Elements
    "Fire", "Water", "Earth", "Air", "Wind", "Rain", "Snow", "Ice",
    "Sun", "Moon", "Star", "Sky", "Cloud", "Lightning", "Thunder",
    "Storm", "Flood", "Earthquake", "Volcano", "Wave", "Tide",
    "Light", "Dark", "Shadow", "Flame", "Smoke", "Dust", "Sand",
    "Stone", "Rock", "Crystal", "Diamond", "Gold", "Silver", "Iron",
]

NOUNS_FOOD = [
    # Meals
    "Breakfast", "Lunch", "Dinner", "Snack", "Dessert", "Appetizer",

    # Foods
    "Bread", "Rice", "Pasta", "Noodles", "Pizza", "Burger", "Sandwich",
    "Salad", "Soup", "Steak", "Chicken", "Fish", "Eggs", "Cheese",
    "Apple", "Banana", "Orange", "Grape", "Strawberry", "Watermelon",
    "Potato", "Tomato", "Carrot", "Onion", "Lettuce", "Broccoli",
    "Cake", "Pie", "Cookie", "Ice cream", "Chocolate", "Candy",

    # Drinks
    "Water", "Coffee", "Tea", "Milk", "Juice", "Soda", "Beer", "Wine",
]

# =============================================================================
# COMMON VERBS - Action words in various forms
# =============================================================================

VERBS_ACTIONS = [
    # Movement
    "Go", "Come", "Walk", "Run", "Jump", "Climb", "Fall", "Fly",
    "Swim", "Drive", "Ride", "Move", "Stop", "Start", "Turn",
    "Enter", "Exit", "Leave", "Arrive", "Return", "Follow", "Lead",
    "Push", "Pull", "Lift", "Drop", "Throw", "Catch", "Kick",
    "Dance", "Crawl", "Roll", "Spin", "Slide", "Skip", "March",

    # Interaction
    "Take", "Give", "Get", "Put", "Hold", "Touch", "Grab", "Release",
    "Open", "Close", "Lock", "Unlock", "Break", "Fix", "Build", "Create",
    "Use", "Find", "Lose", "Keep", "Send", "Receive", "Bring", "Carry",
    "Buy", "Sell", "Pay", "Spend", "Save", "Trade", "Share", "Borrow",
    "Hit", "Cut", "Tear", "Bend", "Fold", "Wrap", "Tie", "Connect",

    # Communication
    "Say", "Tell", "Ask", "Answer", "Speak", "Talk", "Listen", "Hear",
    "Call", "Shout", "Whisper", "Sing", "Read", "Write", "Type",
    "Show", "Hide", "Explain", "Describe", "Announce", "Declare",
    "Agree", "Disagree", "Promise", "Warn", "Thank", "Apologize",

    # Mental
    "Think", "Know", "Believe", "Understand", "Remember", "Forget",
    "Learn", "Teach", "Study", "Decide", "Choose", "Plan", "Hope",
    "Want", "Need", "Like", "Love", "Hate", "Fear", "Wish", "Dream",
    "Wonder", "Imagine", "Consider", "Expect", "Realize", "Recognize",

    # States
    "Be", "Have", "Do", "Make", "Become", "Stay", "Remain", "Seem",
    "Feel", "Look", "Sound", "Smell", "Taste", "Appear", "Exist",
    "Live", "Die", "Sleep", "Wake", "Rest", "Wait", "Begin", "End",
    "Change", "Grow", "Shrink", "Increase", "Decrease", "Continue",

    # Work
    "Work", "Play", "Help", "Try", "Finish", "Complete", "Practice",
    "Check", "Test", "Measure", "Count", "Calculate", "Solve", "Design",
    "Cook", "Clean", "Wash", "Dry", "Paint", "Draw", "Photograph",
]

VERBS_COMMANDS = [
    # Imperatives
    "Go now", "Come here", "Stop that", "Wait a moment", "Listen carefully",
    "Look out", "Watch this", "Be careful", "Stay there", "Follow me",
    "Tell me", "Show me", "Give me", "Help me", "Let me know",
    "Try again", "Keep going", "Don't stop", "Hurry up", "Slow down",
    "Turn around", "Step back", "Move forward", "Stand up", "Sit down",
    "Pick it up", "Put it down", "Hold on", "Let go", "Take this",
    "Open it", "Close it", "Lock the door", "Turn off the light",
    "Make sure", "Double check", "Pay attention", "Focus", "Concentrate",
    "Calm down", "Relax", "Breathe", "Think about it", "Consider this",
]

# =============================================================================
# COMMON ADJECTIVES - Descriptive words
# =============================================================================

ADJECTIVES_SIZE = [
    "Big", "Small", "Large", "Tiny", "Huge", "Massive", "Giant", "Enormous",
    "Little", "Mini", "Micro", "Medium", "Average", "Standard",
    "Tall", "Short", "Long", "Wide", "Narrow", "Thick", "Thin",
    "Deep", "Shallow", "High", "Low", "Heavy", "Light", "Dense",
]

ADJECTIVES_QUALITY = [
    "Good", "Bad", "Great", "Terrible", "Excellent", "Poor", "Perfect",
    "Best", "Worst", "Better", "Worse", "Fine", "Okay", "Decent",
    "Amazing", "Wonderful", "Fantastic", "Incredible", "Awful", "Horrible",
    "Beautiful", "Ugly", "Pretty", "Handsome", "Gorgeous", "Stunning",
    "Nice", "Lovely", "Charming", "Elegant", "Plain", "Simple", "Complex",
    "Clean", "Dirty", "Neat", "Messy", "Tidy", "Organized", "Chaotic",
    "New", "Old", "Young", "Ancient", "Modern", "Fresh", "Stale",
    "Strong", "Weak", "Powerful", "Fragile", "Sturdy", "Delicate",
    "Fast", "Slow", "Quick", "Rapid", "Swift", "Instant", "Gradual",
    "Hard", "Soft", "Firm", "Smooth", "Rough", "Sharp", "Dull",
    "Bright", "Dark", "Light", "Dim", "Shiny", "Matte", "Glowing",
    "Loud", "Quiet", "Silent", "Noisy", "Clear", "Muffled",
    "Hot", "Cold", "Warm", "Cool", "Frozen", "Boiling", "Lukewarm",
    "Wet", "Dry", "Damp", "Moist", "Soggy", "Crisp",
]

ADJECTIVES_EMOTION = [
    "Happy", "Sad", "Angry", "Scared", "Surprised", "Confused", "Excited",
    "Nervous", "Anxious", "Worried", "Calm", "Relaxed", "Peaceful",
    "Tired", "Exhausted", "Energetic", "Lazy", "Bored", "Interested",
    "Proud", "Ashamed", "Embarrassed", "Confident", "Shy", "Bold",
    "Grateful", "Thankful", "Sorry", "Hopeful", "Desperate", "Determined",
    "Curious", "Amazed", "Disappointed", "Frustrated", "Satisfied",
    "Lonely", "Content", "Jealous", "Envious", "Loving", "Kind", "Cruel",
]

ADJECTIVES_CHARACTER = [
    "Smart", "Stupid", "Intelligent", "Clever", "Wise", "Foolish",
    "Brave", "Cowardly", "Courageous", "Fearless", "Timid", "Bold",
    "Honest", "Dishonest", "Truthful", "Loyal", "Faithful", "Trustworthy",
    "Friendly", "Unfriendly", "Nice", "Mean", "Polite", "Rude",
    "Generous", "Selfish", "Greedy", "Humble", "Arrogant", "Modest",
    "Patient", "Impatient", "Careful", "Careless", "Responsible",
    "Serious", "Funny", "Silly", "Crazy", "Strange", "Weird", "Normal",
    "Famous", "Unknown", "Popular", "Important", "Special", "Ordinary",
]

ADJECTIVES_PHYSICAL = [
    "Round", "Square", "Flat", "Curved", "Straight", "Crooked", "Bent",
    "Empty", "Full", "Hollow", "Solid", "Whole", "Broken", "Cracked",
    "Open", "Closed", "Locked", "Unlocked", "Sealed", "Loose", "Tight",
    "Near", "Far", "Close", "Distant", "Local", "Remote", "Central",
    "Top", "Bottom", "Left", "Right", "Front", "Back", "Side", "Middle",
    "Inner", "Outer", "Upper", "Lower", "Northern", "Southern",
    "Real", "Fake", "True", "False", "Actual", "Virtual", "Digital",
]

# =============================================================================
# MAGICAL STORIES - Fantasy and adventure narratives
# =============================================================================

MAGIC_OPENINGS = [
    # Story beginnings
    "Once upon a time, in a land far away.",
    "Long ago, when magic still filled the world.",
    "In a kingdom hidden among the clouds.",
    "Deep within an enchanted forest.",
    "Beyond the mountains of mist and shadow.",
    "In an age when dragons ruled the skies.",
    "There lived a young wizard with a secret.",
    "The ancient prophecy spoke of this day.",
    "When the three moons aligned.",
    "In the realm between dreams and waking.",
    "A mysterious stranger arrived at midnight.",
    "The old spell book fell open to a forbidden page.",
    "Legends tell of a powerful artifact.",
    "The portal shimmered with otherworldly light.",
    "Magic had been outlawed for a thousand years.",
]

MAGIC_CHARACTERS = [
    # Character introductions
    "The young apprentice studied her spell.",
    "The wise old wizard stroked his silver beard.",
    "The brave knight drew his enchanted sword.",
    "The elven princess gazed into the crystal ball.",
    "The dragon awakened from centuries of slumber.",
    "The fairy queen summoned her loyal subjects.",
    "The dark sorcerer plotted his revenge.",
    "The humble blacksmith discovered his true destiny.",
    "The ghost of the ancient king appeared.",
    "The shape-shifter revealed her true form.",
    "The enchanted creature spoke in riddles.",
    "The guardian of the sacred grove stood watch.",
    "The chosen one bore a mysterious mark.",
    "The wandering bard knew many secrets.",
    "The cursed prince searched for his cure.",
]

MAGIC_SPELLS = [
    # Spell casting
    "By the power of the ancient ones!",
    "I summon the forces of light!",
    "Let the darkness be vanquished!",
    "Rise, spirits of the forest!",
    "Shield of starlight, protect us!",
    "Time itself shall bend to my will!",
    "Fire and ice, heed my command!",
    "Winds of change, carry my words!",
    "I bind you with chains of silver light!",
    "Reveal what has been hidden!",
    "Let the healing waters flow!",
    "Transform and take flight!",
    "Open the gateway between worlds!",
    "I call upon the power within!",
    "May the blessing of the moon be upon you!",
    "By earth, air, fire, and water!",
    "Awaken the magic that sleeps within!",
    "Let illusion become reality!",
    "Break the curse that binds you!",
    "The ancient words of power echo forth!",
]

MAGIC_ARTIFACTS = [
    # Magical items
    "The sword glowed with ethereal fire.",
    "The ancient amulet pulsed with energy.",
    "The enchanted mirror showed the future.",
    "The magic carpet soared through the clouds.",
    "The wand chose its new master.",
    "The crystal held a captured soul.",
    "The ring granted invisibility to its wearer.",
    "The staff channeled pure magical energy.",
    "The potion bubbled and changed colors.",
    "The book of shadows contained forbidden spells.",
    "The enchanted armor protected against all harm.",
    "The compass pointed toward true desire.",
    "The chalice could heal any wound.",
    "The cloak concealed its wearer in darkness.",
    "The horn could summon mythical beasts.",
]

MAGIC_CREATURES = [
    # Mythical beings
    "The phoenix rose from the ashes.",
    "The unicorn appeared in the moonlit glade.",
    "The griffin soared above the mountain peaks.",
    "The mermaid sang her haunting melody.",
    "The centaur galloped through the ancient woods.",
    "The goblin lurked in the shadows.",
    "The troll guarded the bridge.",
    "The giant's footsteps shook the earth.",
    "The vampire emerged at twilight.",
    "The werewolf howled at the full moon.",
    "The kraken stirred in the depths below.",
    "The sprite danced among the flowers.",
    "The banshee's wail echoed through the night.",
    "The basilisk's gaze turned all to stone.",
    "The hydra grew two heads for every one lost.",
]

MAGIC_PLACES = [
    # Enchanted locations
    "The enchanted castle floated in the sky.",
    "The magical forest whispered ancient secrets.",
    "The crystal caves sparkled with inner light.",
    "The tower of the moon touched the stars.",
    "The hidden valley remained forever spring.",
    "The cursed ruins held untold treasures.",
    "The labyrinth shifted and changed.",
    "The underwater kingdom gleamed with pearls.",
    "The shadow realm existed between worlds.",
    "The garden of eternal flowers never wilted.",
    "The frozen palace stood at the world's end.",
    "The library contained all knowledge ever known.",
    "The sacred temple housed the divine flame.",
    "The crossroads where all paths converged.",
    "The mountain where the gods once dwelt.",
]

MAGIC_ADVENTURES = [
    # Quest narratives
    "The quest to find the lost kingdom began.",
    "They journeyed through treacherous lands.",
    "The map revealed a hidden passage.",
    "The riddle's answer opened the ancient door.",
    "Danger lurked around every corner.",
    "The final battle approached.",
    "Allies joined from unexpected places.",
    "The enemy's fortress loomed ahead.",
    "A sacrifice was required to proceed.",
    "The heroes faced their greatest fear.",
    "Hope flickered but did not die.",
    "The tide of battle turned.",
    "Victory seemed within reach.",
    "The cost of success weighed heavily.",
    "The adventure changed them forever.",
]

MAGIC_ENDINGS = [
    # Story conclusions
    "And peace returned to the land.",
    "The curse was finally broken.",
    "Magic had been restored to the world.",
    "The heroes were celebrated throughout the realm.",
    "But the story was far from over.",
    "And so the legend was born.",
    "The kingdom entered a new golden age.",
    "Some mysteries remained unsolved.",
    "They lived happily ever after.",
    "The cycle would begin again.",
    "Evil was vanquished, for now.",
    "A new chapter was about to begin.",
    "The world would never be the same.",
    "Hope had returned to all who believed.",
    "And the magic continues to this day.",
]

MAGIC_DIALOGUE = [
    # Character speech
    "I sense a great darkness approaching.",
    "The prophecy must be fulfilled.",
    "Trust in the magic within you.",
    "We must reach the tower before dawn.",
    "The ancient ones have awakened.",
    "Your destiny awaits, young one.",
    "The balance must be restored.",
    "Beware the shadows that follow.",
    "Only together can we succeed.",
    "The time for hiding is over.",
    "I have foreseen this moment.",
    "The power was within you all along.",
    "Take this; you will need it.",
    "The portal will close at midnight.",
    "Remember who you truly are.",
    "Do not trust what your eyes see.",
    "The enchantment is weakening.",
    "We are the last hope.",
    "The legends were true.",
    "Magic always comes with a price.",
]

# =============================================================================
# CATEGORY DISTRIBUTION FOR GENERATION
# =============================================================================

CATEGORY_DISTRIBUTION = {
    # === ATOMIC COMPONENTS (for combining) ===
    # Navigation
    'nav_action': 1500,
    'nav_street': 1200,
    'nav_preposition': 400,

    # Numbers & Counting
    'distance_number': 1200,
    'distance_unit': 600,
    'ordinal': 500,
    'digit': 800,  # 0-9 across voices
    'number': 1500,  # larger numbers
    'counting': 600,

    # Alphabet
    'letter': 1200,  # A-Z across many voices
    'phonetic': 1200,  # NATO alphabet

    # Time & Date
    'time_hour': 600,
    'time_minute': 1200,
    'time_period': 500,
    'day': 600,
    'month': 600,

    # UI & System
    'ui_element': 600,
    'ui_action': 1000,
    'system': 800,

    # Money
    'currency': 600,

    # Connectors
    'connector': 600,

    # === NEW: COLORS ===
    'color': 2000,  # All color names and variations

    # === NEW: EXPANDED WEATHER ===
    'weather_expanded': 2500,  # Comprehensive weather descriptions

    # === NEW: COMMON NOUNS ===
    'noun_object': 3000,     # Household, clothing, tech, tools, transport
    'noun_place': 2000,      # Buildings, outdoor, geographic
    'noun_people': 2000,     # Family, occupations, general
    'noun_concept': 1500,    # Time, abstract concepts
    'noun_nature': 2000,     # Animals, plants, elements
    'noun_food': 1500,       # Meals, foods, drinks

    # === NEW: COMMON VERBS ===
    'verb_action': 4000,     # Movement, interaction, communication, mental, states
    'verb_command': 2000,    # Imperative commands

    # === NEW: COMMON ADJECTIVES ===
    'adj_size': 1500,        # Size-related
    'adj_quality': 3000,     # Quality/state descriptors
    'adj_emotion': 2000,     # Emotional states
    'adj_character': 2000,   # Character traits
    'adj_physical': 2000,    # Physical properties

    # === NEW: MAGICAL STORIES ===
    'magic_opening': 1000,   # Story beginnings
    'magic_character': 1000, # Character introductions
    'magic_spell': 1500,     # Spell casting
    'magic_artifact': 1000,  # Magical items
    'magic_creature': 1000,  # Mythical beings
    'magic_place': 1000,     # Enchanted locations
    'magic_adventure': 1000, # Quest narratives
    'magic_ending': 1000,    # Story conclusions
    'magic_dialogue': 1500,  # Character speech

    # === COMPLETE PHRASES (standalone) ===
    # Common phrases
    'greeting': 800,
    'farewell': 600,
    'confirmation': 1000,
    'denial': 500,
    'warning': 800,
    'thanks': 500,
    'apology': 400,
    'question': 600,

    # Announcements & Media
    'announcement': 1200,
    'news': 600,
    'weather': 800,
    'sports': 600,
    'traffic': 500,
    'radio': 500,
    'podcast': 500,

    # Entertainment
    'game_voice': 1000,
    'dramatic': 800,
    'character': 800,
    'commercial': 800,

    # Cinematic/Story (longer sentences for cutscenes)
    'cinematic': 1500,
    'villain': 800,
    'hero': 800,

    # Instructions
    'tutorial': 1000,
    'interjection': 600,

    # === BYK3S GAME-SPECIFIC ===
    'byk3s_narrator': 800,
    'byk3s_commander': 600,
    'byk3s_graphling': 500,
    'byk3s_intel': 400,
    'byk3s_stargates': 600,
    'byk3s_rider': 400,
    'byk3s_regions': 300,
    'byk3s_outcomes': 300,
}

# =============================================================================
# TEMPLATE MAPPING
# =============================================================================

CATEGORY_TEMPLATES = {
    # Navigation
    'nav_action': NAV_ACTIONS,
    'nav_street': NAV_STREETS,
    'nav_preposition': NAV_PREPOSITIONS,

    # Numbers & Counting
    'distance_number': DISTANCE_NUMBERS,
    'distance_unit': DISTANCE_UNITS,
    'ordinal': ORDINALS,
    'digit': DIGITS,
    'number': NUMBERS,
    'counting': COUNTING,

    # Alphabet
    'letter': LETTERS,
    'phonetic': PHONETIC,

    # Time & Date
    'time_hour': TIME_HOURS,
    'time_minute': TIME_MINUTES,
    'time_period': TIME_PERIODS,
    'day': DAYS,
    'month': MONTHS,

    # UI & System
    'ui_element': UI_ELEMENTS,
    'ui_action': UI_ACTIONS,
    'system': SYSTEM,

    # Money
    'currency': CURRENCY,

    # Connectors
    'connector': CONNECTORS,

    # === NEW: COLORS ===
    'color': COLORS,

    # === NEW: EXPANDED WEATHER ===
    'weather_expanded': WEATHER_EXPANDED,

    # === NEW: COMMON NOUNS ===
    'noun_object': NOUNS_OBJECTS,
    'noun_place': NOUNS_PLACES,
    'noun_people': NOUNS_PEOPLE,
    'noun_concept': NOUNS_CONCEPTS,
    'noun_nature': NOUNS_NATURE,
    'noun_food': NOUNS_FOOD,

    # === NEW: COMMON VERBS ===
    'verb_action': VERBS_ACTIONS,
    'verb_command': VERBS_COMMANDS,

    # === NEW: COMMON ADJECTIVES ===
    'adj_size': ADJECTIVES_SIZE,
    'adj_quality': ADJECTIVES_QUALITY,
    'adj_emotion': ADJECTIVES_EMOTION,
    'adj_character': ADJECTIVES_CHARACTER,
    'adj_physical': ADJECTIVES_PHYSICAL,

    # === NEW: MAGICAL STORIES ===
    'magic_opening': MAGIC_OPENINGS,
    'magic_character': MAGIC_CHARACTERS,
    'magic_spell': MAGIC_SPELLS,
    'magic_artifact': MAGIC_ARTIFACTS,
    'magic_creature': MAGIC_CREATURES,
    'magic_place': MAGIC_PLACES,
    'magic_adventure': MAGIC_ADVENTURES,
    'magic_ending': MAGIC_ENDINGS,
    'magic_dialogue': MAGIC_DIALOGUE,

    # Common phrases
    'greeting': GREETINGS,
    'farewell': FAREWELLS,
    'confirmation': CONFIRMATIONS,
    'denial': DENIALS,
    'warning': WARNINGS,
    'thanks': THANKS,
    'apology': APOLOGIES,
    'question': QUESTIONS,

    # Announcements & Media
    'announcement': ANNOUNCEMENTS,
    'news': NEWS,
    'weather': WEATHER,
    'sports': SPORTS,
    'traffic': TRAFFIC,
    'radio': RADIO,
    'podcast': PODCAST,

    # Entertainment
    'game_voice': GAME_VOICE,
    'dramatic': DRAMATIC,
    'character': CHARACTER,
    'commercial': COMMERCIAL,

    # Cinematic/Story
    'cinematic': CINEMATIC,
    'villain': VILLAIN,
    'hero': HERO,

    # Instructions
    'tutorial': TUTORIAL,
    'interjection': INTERJECTIONS,

    # Byk3s Game-Specific
    'byk3s_narrator': BYKZS_NARRATOR,
    'byk3s_commander': BYKZS_COMMANDER,
    'byk3s_graphling': BYKZS_GRAPHLING,
    'byk3s_intel': BYKZS_INTEL,
    'byk3s_stargates': BYKZS_STARGATES,
    'byk3s_rider': BYKZS_RIDER,
    'byk3s_regions': BYKZS_REGIONS,
    'byk3s_outcomes': BYKZS_OUTCOMES,
}


def get_all_prompts():
    """
    Generate prompts for all categories based on distribution.
    Each prompt includes the text and category tag.
    """
    prompts = []

    for category, target_count in CATEGORY_DISTRIBUTION.items():
        templates = CATEGORY_TEMPLATES.get(category, [])
        if not templates:
            continue

        # Generate prompts by cycling through templates
        for i in range(target_count):
            template = templates[i % len(templates)]
            prompts.append({
                'text': template,
                'category': category,
            })

    return prompts


def get_prompts_by_category(category):
    """Get all prompts for a specific category."""
    templates = CATEGORY_TEMPLATES.get(category, [])
    return [{'text': t, 'category': category} for t in templates]


# Quick stats
if __name__ == '__main__':
    print("Speech Template Statistics - Component-Based System")
    print("=" * 60)

    total_unique = 0
    total_generated = 0

    print("\nATOMIC COMPONENTS (for combining):")
    print("-" * 40)
    atomic = ['nav_action', 'nav_street', 'nav_preposition', 'distance_number',
              'distance_unit', 'ordinal', 'letter', 'phonetic', 'digit', 'number',
              'time_hour', 'time_minute', 'time_period', 'ui_element', 'ui_action', 'connector']
    for cat in atomic:
        templates = CATEGORY_TEMPLATES.get(cat, [])
        target = CATEGORY_DISTRIBUTION.get(cat, 0)
        print(f"  {cat:20s}: {len(templates):3d} unique -> {target:5d} clips")
        total_unique += len(templates)
        total_generated += target

    print(f"\n  Atomic subtotal: {total_generated:,} clips")

    phrase_total = 0
    print("\nCOMPLETE PHRASES (standalone):")
    print("-" * 40)
    phrases = ['greeting', 'farewell', 'confirmation', 'denial', 'warning', 'thanks',
               'apology', 'question', 'announcement', 'dramatic', 'character',
               'commercial', 'tutorial', 'interjection']
    for cat in phrases:
        templates = CATEGORY_TEMPLATES.get(cat, [])
        target = CATEGORY_DISTRIBUTION.get(cat, 0)
        print(f"  {cat:20s}: {len(templates):3d} unique -> {target:5d} clips")
        total_unique += len(templates)
        total_generated += target
        phrase_total += target

    print(f"\n  Phrase subtotal: {phrase_total:,} clips")

    print("\n" + "=" * 60)
    print(f"TOTAL unique templates: {total_unique}")
    print(f"TOTAL clips to generate: {total_generated:,}")

#!/usr/bin/env python3
"""
Batch speech generation script for populating the library with tagged speech samples.
Generates diverse speech content across all categories with multiple voices.
"""

import requests
import time
import json
import sys

BASE_URL = "http://localhost:5309"

# Voice configurations - mapping voice IDs to gender/style
VOICES = {
    # Male voices
    'en_US-ryan-medium': {'gender': 'male', 'style': 'natural', 'quality': 'medium'},
    'en_US-joe-medium': {'gender': 'male', 'style': 'professional', 'quality': 'medium'},
    'en_US-john-medium': {'gender': 'male', 'style': 'natural', 'quality': 'medium'},
    'en_GB-alan-medium': {'gender': 'male', 'style': 'professional', 'quality': 'medium'},
    'en_GB-northern_english_male-medium': {'gender': 'male', 'style': 'casual', 'quality': 'medium'},

    # Female voices
    'en_US-amy-medium': {'gender': 'female', 'style': 'natural', 'quality': 'medium'},
    'en_US-lessac-medium': {'gender': 'female', 'style': 'professional', 'quality': 'medium'},
    'en_US-kristin-medium': {'gender': 'female', 'style': 'natural', 'quality': 'medium'},
    'en_US-kathleen-low': {'gender': 'female', 'style': 'casual', 'quality': 'low'},
    'en_GB-jenny_dioco-medium': {'gender': 'female', 'style': 'professional', 'quality': 'medium'},
    'en_GB-cori-medium': {'gender': 'female', 'style': 'natural', 'quality': 'medium'},

    # Neutral/Other
    'en_US-hfc_male-medium': {'gender': 'male', 'style': 'robotic', 'quality': 'medium'},
    'en_US-hfc_female-medium': {'gender': 'female', 'style': 'robotic', 'quality': 'medium'},
}

# Speech prompts organized by category
# Each entry: (text, categories_to_tag, preferred_voice_gender)
SPEECH_PROMPTS = {
    # ===== NUMBERS & DATA =====
    'numbers': [
        ("Zero.", ['numbers'], None),
        ("One.", ['numbers'], None),
        ("Two.", ['numbers'], None),
        ("Three.", ['numbers'], None),
        ("Four.", ['numbers'], None),
        ("Five.", ['numbers'], None),
        ("Six.", ['numbers'], None),
        ("Seven.", ['numbers'], None),
        ("Eight.", ['numbers'], None),
        ("Nine.", ['numbers'], None),
        ("Ten.", ['numbers'], None),
        ("Eleven.", ['numbers'], None),
        ("Twelve.", ['numbers'], None),
        ("Thirteen.", ['numbers'], None),
        ("Fourteen.", ['numbers'], None),
        ("Fifteen.", ['numbers'], None),
        ("Twenty.", ['numbers'], None),
        ("Thirty.", ['numbers'], None),
        ("Forty.", ['numbers'], None),
        ("Fifty.", ['numbers'], None),
        ("One hundred.", ['numbers'], None),
        ("One thousand.", ['numbers'], None),
        ("One million.", ['numbers'], None),
    ],

    'counting': [
        ("One, two, three.", ['counting', 'numbers'], None),
        ("One, two, three, four, five.", ['counting', 'numbers'], None),
        ("Counting down: five, four, three, two, one.", ['counting', 'numbers'], None),
        ("Three, two, one, go!", ['counting', 'numbers'], None),
        ("Ten, nine, eight, seven, six, five, four, three, two, one, zero.", ['counting', 'numbers'], None),
        ("First, second, third.", ['counting', 'numbers'], None),
    ],

    'time': [
        ("It is now twelve o'clock.", ['time'], None),
        ("The time is three thirty.", ['time'], None),
        ("Five forty-five PM.", ['time'], None),
        ("It's quarter past nine.", ['time'], None),
        ("Half past two.", ['time'], None),
        ("Ten minutes to midnight.", ['time'], None),
        ("The current time is eight fifteen AM.", ['time', 'announcement'], None),
        ("You have five minutes remaining.", ['time', 'alert'], None),
        ("Time's up!", ['time', 'alert'], None),
    ],

    'date': [
        ("Today is Monday.", ['date'], None),
        ("Tuesday, January first.", ['date'], None),
        ("Wednesday, March fifteenth, twenty twenty-four.", ['date'], None),
        ("It's Friday!", ['date'], None),
        ("This weekend.", ['date'], None),
        ("Happy New Year!", ['date', 'greeting'], None),
        ("Merry Christmas!", ['date', 'greeting'], None),
    ],

    'currency': [
        ("One dollar.", ['currency', 'numbers'], None),
        ("Five dollars and ninety-nine cents.", ['currency', 'numbers'], None),
        ("That will be twenty-three fifty.", ['currency', 'numbers'], None),
        ("The total is one hundred dollars.", ['currency', 'numbers'], None),
        ("Fifty percent off.", ['currency', 'numbers'], None),
        ("Your balance is zero.", ['currency', 'numbers'], None),
    ],

    'phone_number': [
        ("Please call five five five, one two three four.", ['phone_number', 'numbers'], None),
        ("Dial nine one one for emergencies.", ['phone_number', 'numbers', 'alert'], None),
        ("Press one for English.", ['phone_number', 'prompt'], None),
        ("Please hold.", ['phone_number'], None),
        ("Your call is important to us.", ['phone_number'], None),
    ],

    # ===== COMMON PHRASES =====
    'greeting': [
        ("Hello.", ['greeting'], None),
        ("Hi there!", ['greeting'], None),
        ("Good morning.", ['greeting'], None),
        ("Good afternoon.", ['greeting'], None),
        ("Good evening.", ['greeting'], None),
        ("Hey, how's it going?", ['greeting', 'casual'], None),
        ("Welcome!", ['greeting'], None),
        ("Welcome back!", ['greeting'], None),
        ("Nice to meet you.", ['greeting'], None),
        ("How are you today?", ['greeting', 'question'], None),
    ],

    'farewell': [
        ("Goodbye.", ['farewell'], None),
        ("Bye bye!", ['farewell'], None),
        ("See you later.", ['farewell'], None),
        ("Take care.", ['farewell'], None),
        ("Have a nice day.", ['farewell'], None),
        ("Until next time.", ['farewell'], None),
        ("Catch you later!", ['farewell', 'casual'], None),
        ("Farewell.", ['farewell'], None),
    ],

    'thanks': [
        ("Thank you.", ['thanks'], None),
        ("Thanks!", ['thanks'], None),
        ("Thank you very much.", ['thanks'], None),
        ("Thanks a lot!", ['thanks'], None),
        ("I appreciate it.", ['thanks'], None),
        ("You're welcome.", ['thanks'], None),
        ("No problem.", ['thanks'], None),
        ("My pleasure.", ['thanks'], None),
    ],

    'confirmation': [
        ("Yes.", ['confirmation'], None),
        ("Correct.", ['confirmation'], None),
        ("That's right.", ['confirmation'], None),
        ("Affirmative.", ['confirmation'], None),
        ("Confirmed.", ['confirmation'], None),
        ("Okay.", ['confirmation'], None),
        ("Sure.", ['confirmation'], None),
        ("Absolutely.", ['confirmation'], None),
        ("Got it.", ['confirmation'], None),
        ("Understood.", ['confirmation'], None),
    ],

    'denial': [
        ("No.", ['denial'], None),
        ("Negative.", ['denial'], None),
        ("Incorrect.", ['denial'], None),
        ("That's not right.", ['denial'], None),
        ("I don't think so.", ['denial'], None),
        ("Denied.", ['denial'], None),
        ("Access denied.", ['denial', 'alert'], None),
        ("Permission denied.", ['denial', 'alert'], None),
        ("Sorry, that's not possible.", ['denial'], None),
    ],

    'question': [
        ("What?", ['question'], None),
        ("Why?", ['question'], None),
        ("How?", ['question'], None),
        ("When?", ['question'], None),
        ("Where?", ['question'], None),
        ("Who?", ['question'], None),
        ("Really?", ['question'], None),
        ("Are you sure?", ['question'], None),
        ("Can you repeat that?", ['question'], None),
        ("What did you say?", ['question'], None),
    ],

    # ===== INSTRUCTIONS =====
    'directions': [
        ("Turn left.", ['directions'], None),
        ("Turn right.", ['directions'], None),
        ("Go straight ahead.", ['directions'], None),
        ("Make a U-turn.", ['directions'], None),
        ("In one hundred meters, turn left.", ['directions'], None),
        ("Your destination is on the right.", ['directions'], None),
        ("Take the next exit.", ['directions'], None),
        ("Merge onto the highway.", ['directions'], None),
        ("Continue for two miles.", ['directions'], None),
        ("You have arrived at your destination.", ['directions', 'announcement'], None),
    ],

    'tutorial': [
        ("Step one.", ['tutorial'], None),
        ("Step two.", ['tutorial'], None),
        ("Step three.", ['tutorial'], None),
        ("First, click the button.", ['tutorial'], None),
        ("Next, enter your information.", ['tutorial'], None),
        ("Finally, press submit.", ['tutorial'], None),
        ("Let me show you how.", ['tutorial'], None),
        ("Follow these instructions.", ['tutorial'], None),
        ("Here's how it works.", ['tutorial'], None),
    ],

    'warning': [
        ("Warning!", ['warning', 'alert'], None),
        ("Caution!", ['warning', 'alert'], None),
        ("Be careful.", ['warning'], None),
        ("Watch out!", ['warning', 'alert'], None),
        ("Danger ahead.", ['warning', 'alert'], None),
        ("Please proceed with caution.", ['warning'], None),
        ("This action cannot be undone.", ['warning'], None),
        ("Are you sure you want to continue?", ['warning', 'question'], None),
    ],

    'alert': [
        ("Alert!", ['alert'], None),
        ("Attention please.", ['alert', 'announcement'], None),
        ("Notice.", ['alert'], None),
        ("Important!", ['alert'], None),
        ("Emergency!", ['alert'], None),
        ("Incoming message.", ['alert', 'notification'], None),
        ("You have a new notification.", ['alert', 'notification'], None),
        ("System alert.", ['alert'], None),
    ],

    'reminder': [
        ("Don't forget.", ['reminder'], None),
        ("Remember to save your work.", ['reminder'], None),
        ("This is a reminder.", ['reminder'], None),
        ("Reminder: your appointment is in one hour.", ['reminder'], None),
        ("Please remember to log out.", ['reminder'], None),
    ],

    'prompt': [
        ("Please enter your password.", ['prompt'], None),
        ("Type your message here.", ['prompt'], None),
        ("Press any key to continue.", ['prompt'], None),
        ("Click here to proceed.", ['prompt'], None),
        ("Select an option.", ['prompt'], None),
        ("Please make a selection.", ['prompt'], None),
        ("Enter your name.", ['prompt'], None),
        ("What would you like to do?", ['prompt', 'question'], None),
    ],

    # ===== MEDIA & ENTERTAINMENT =====
    'commercial': [
        ("Buy now!", ['commercial'], None),
        ("Limited time offer.", ['commercial'], None),
        ("Order today.", ['commercial'], None),
        ("Call now and receive a free gift.", ['commercial'], None),
        ("Don't miss out!", ['commercial'], None),
        ("Available for a limited time only.", ['commercial'], None),
        ("Act now while supplies last.", ['commercial'], None),
    ],

    'trailer_voice': [
        ("In a world...", ['trailer_voice', 'dramatic'], 'male'),
        ("This summer...", ['trailer_voice', 'dramatic'], 'male'),
        ("Coming soon.", ['trailer_voice'], 'male'),
        ("One man.", ['trailer_voice', 'dramatic'], 'male'),
        ("Everything changes.", ['trailer_voice', 'dramatic'], 'male'),
        ("The adventure begins.", ['trailer_voice', 'dramatic'], 'male'),
        ("Rated PG thirteen.", ['trailer_voice'], None),
        ("Now playing in theaters everywhere.", ['trailer_voice', 'announcement'], None),
    ],

    'podcast': [
        ("Hey everyone, welcome back to the show.", ['podcast', 'casual'], None),
        ("Today we're going to talk about...", ['podcast'], None),
        ("Before we get started, a word from our sponsors.", ['podcast', 'commercial'], None),
        ("Thanks for listening!", ['podcast', 'farewell'], None),
        ("Don't forget to subscribe.", ['podcast', 'prompt'], None),
        ("Leave a comment below.", ['podcast', 'prompt'], None),
        ("Let's dive right in.", ['podcast'], None),
    ],

    'radio': [
        ("You're listening to...", ['radio', 'announcement'], None),
        ("That was...", ['radio', 'announcement'], None),
        ("Coming up next...", ['radio', 'announcement'], None),
        ("Stay tuned.", ['radio'], None),
        ("We'll be right back.", ['radio'], None),
        ("It's ten o'clock. Here's the news.", ['radio', 'news', 'time'], None),
    ],

    'game_voice': [
        ("Player one, ready!", ['game_voice'], None),
        ("Game over.", ['game_voice'], None),
        ("You win!", ['game_voice'], None),
        ("You lose.", ['game_voice'], None),
        ("Level complete.", ['game_voice'], None),
        ("New high score!", ['game_voice'], None),
        ("Get ready!", ['game_voice'], None),
        ("Fight!", ['game_voice'], None),
        ("Round one.", ['game_voice'], None),
        ("Final round.", ['game_voice'], None),
        ("K.O.!", ['game_voice'], None),
        ("Perfect!", ['game_voice'], None),
        ("Excellent!", ['game_voice'], None),
        ("Mission accomplished.", ['game_voice'], None),
        ("Mission failed.", ['game_voice'], None),
        ("Respawning in three, two, one.", ['game_voice', 'counting'], None),
    ],

    'character': [
        ("I'll be back.", ['character', 'dramatic'], 'male'),
        ("May the force be with you.", ['character'], None),
        ("Elementary, my dear Watson.", ['character'], 'male'),
        ("To infinity and beyond!", ['character'], None),
        ("I am your father.", ['character', 'dramatic'], 'male'),
    ],

    # ===== INFORMATIONAL =====
    'news': [
        ("Breaking news.", ['news', 'alert'], None),
        ("In today's headlines...", ['news'], None),
        ("This just in.", ['news', 'alert'], None),
        ("Developing story.", ['news'], None),
        ("We now go live to our correspondent.", ['news'], None),
        ("That's all for now. Good night.", ['news', 'farewell'], None),
    ],

    'weather': [
        ("Today's forecast.", ['weather', 'announcement'], None),
        ("Sunny with clear skies.", ['weather'], None),
        ("Partly cloudy.", ['weather'], None),
        ("Chance of rain.", ['weather'], None),
        ("Thunderstorms expected.", ['weather', 'warning'], None),
        ("High of seventy-five degrees.", ['weather'], None),
        ("Low of forty degrees.", ['weather'], None),
        ("Bundle up, it's going to be cold.", ['weather', 'reminder'], None),
    ],

    'sports': [
        ("And the crowd goes wild!", ['sports'], None),
        ("What a play!", ['sports'], None),
        ("Goal!", ['sports'], None),
        ("Home run!", ['sports'], None),
        ("Touchdown!", ['sports'], None),
        ("It's good!", ['sports'], None),
        ("And the winner is...", ['sports', 'announcement'], None),
        ("Final score.", ['sports', 'announcement'], None),
    ],

    'traffic': [
        ("Traffic report.", ['traffic', 'announcement'], None),
        ("Heavy congestion on the highway.", ['traffic', 'warning'], None),
        ("Accident reported ahead.", ['traffic', 'alert'], None),
        ("Expect delays.", ['traffic', 'warning'], None),
        ("All lanes are open.", ['traffic'], None),
        ("Construction zone ahead.", ['traffic', 'warning'], None),
    ],

    # ===== ALPHABET & SPELLING =====
    'alphabet': [
        ("A.", ['alphabet'], None),
        ("B.", ['alphabet'], None),
        ("C.", ['alphabet'], None),
        ("D.", ['alphabet'], None),
        ("E.", ['alphabet'], None),
        ("F.", ['alphabet'], None),
        ("G.", ['alphabet'], None),
        ("H.", ['alphabet'], None),
        ("I.", ['alphabet'], None),
        ("J.", ['alphabet'], None),
        ("K.", ['alphabet'], None),
        ("L.", ['alphabet'], None),
        ("M.", ['alphabet'], None),
        ("N.", ['alphabet'], None),
        ("O.", ['alphabet'], None),
        ("P.", ['alphabet'], None),
        ("Q.", ['alphabet'], None),
        ("R.", ['alphabet'], None),
        ("S.", ['alphabet'], None),
        ("T.", ['alphabet'], None),
        ("U.", ['alphabet'], None),
        ("V.", ['alphabet'], None),
        ("W.", ['alphabet'], None),
        ("X.", ['alphabet'], None),
        ("Y.", ['alphabet'], None),
        ("Z.", ['alphabet'], None),
    ],

    'phonetic': [
        ("Alpha.", ['phonetic', 'alphabet'], None),
        ("Bravo.", ['phonetic', 'alphabet'], None),
        ("Charlie.", ['phonetic', 'alphabet'], None),
        ("Delta.", ['phonetic', 'alphabet'], None),
        ("Echo.", ['phonetic', 'alphabet'], None),
        ("Foxtrot.", ['phonetic', 'alphabet'], None),
        ("Golf.", ['phonetic', 'alphabet'], None),
        ("Hotel.", ['phonetic', 'alphabet'], None),
        ("India.", ['phonetic', 'alphabet'], None),
        ("Juliet.", ['phonetic', 'alphabet'], None),
        ("Kilo.", ['phonetic', 'alphabet'], None),
        ("Lima.", ['phonetic', 'alphabet'], None),
        ("Mike.", ['phonetic', 'alphabet'], None),
        ("November.", ['phonetic', 'alphabet'], None),
        ("Oscar.", ['phonetic', 'alphabet'], None),
        ("Papa.", ['phonetic', 'alphabet'], None),
        ("Quebec.", ['phonetic', 'alphabet'], None),
        ("Romeo.", ['phonetic', 'alphabet'], None),
        ("Sierra.", ['phonetic', 'alphabet'], None),
        ("Tango.", ['phonetic', 'alphabet'], None),
        ("Uniform.", ['phonetic', 'alphabet'], None),
        ("Victor.", ['phonetic', 'alphabet'], None),
        ("Whiskey.", ['phonetic', 'alphabet'], None),
        ("X-ray.", ['phonetic', 'alphabet'], None),
        ("Yankee.", ['phonetic', 'alphabet'], None),
        ("Zulu.", ['phonetic', 'alphabet'], None),
    ],

    # ===== ANNOUNCEMENTS =====
    'announcement': [
        ("Your attention please.", ['announcement'], None),
        ("May I have your attention.", ['announcement'], None),
        ("This is an announcement.", ['announcement'], None),
        ("Please stand by.", ['announcement'], None),
        ("The meeting will begin shortly.", ['announcement'], None),
        ("Last call.", ['announcement', 'alert'], None),
        ("Final boarding call.", ['announcement', 'alert'], None),
        ("Please proceed to gate seven.", ['announcement', 'directions'], None),
        ("The store will be closing in fifteen minutes.", ['announcement', 'time'], None),
    ],

    # ===== CONTENT TYPES =====
    'narration': [
        ("Once upon a time.", ['narration', 'audiobook'], None),
        ("And so the story begins.", ['narration', 'audiobook'], None),
        ("Meanwhile, in another part of town.", ['narration'], None),
        ("Little did they know.", ['narration'], None),
        ("The end.", ['narration', 'audiobook'], None),
        ("Chapter one.", ['narration', 'audiobook'], None),
    ],

    'voiceover': [
        ("In the beginning.", ['voiceover', 'narration'], None),
        ("As we can see here.", ['voiceover', 'tutorial'], None),
        ("This diagram shows.", ['voiceover', 'tutorial'], None),
        ("Let's take a closer look.", ['voiceover'], None),
    ],
}


def get_voice_for_gender(preferred_gender):
    """Get a voice ID matching the preferred gender, or any if None."""
    import random

    if preferred_gender:
        matching = [vid for vid, info in VOICES.items() if info['gender'] == preferred_gender]
        if matching:
            return random.choice(matching)

    return random.choice(list(VOICES.keys()))


def generate_speech(text, voice_id, categories):
    """Generate a single speech sample and save to library."""
    try:
        response = requests.post(
            f"{BASE_URL}/api/tts/generate",
            json={
                'text': text,
                'voice': voice_id,
                'save_to_library': True
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            gen_id = data.get('gen_id')

            # Add categories via tag suggestions API
            if gen_id and categories:
                voice_info = VOICES.get(voice_id, {})
                all_categories = list(categories)

                # Add voice gender category
                if voice_info.get('gender'):
                    all_categories.append(voice_info['gender'])

                # Add voice style category if applicable
                if voice_info.get('style') and voice_info['style'] != 'natural':
                    all_categories.append(voice_info['style'])

                for cat in all_categories:
                    try:
                        requests.post(
                            f"{BASE_URL}/api/library/{gen_id}/suggest-tag",
                            json={'category': cat, 'action': 'add'},
                            timeout=5
                        )
                    except requests.RequestException:
                        pass  # Tag suggestion is non-critical, continue on failure

            return True, data
        else:
            return False, response.text

    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def main():
    print("Speech Batch Generation Script")
    print("=" * 50)

    # Count total prompts
    total = sum(len(prompts) for prompts in SPEECH_PROMPTS.values())
    print(f"Total prompts to generate: {total}")

    for category, count in sorted([(k, len(v)) for k, v in SPEECH_PROMPTS.items()], key=lambda x: -x[1]):
        print(f"  - {category}: {count}")

    print()

    # Check server is running
    try:
        response = requests.get(f"{BASE_URL}/status", timeout=5)
        if response.status_code != 200:
            print("Error: Server not responding properly")
            return
    except requests.RequestException as e:
        print(f"Error: Cannot connect to server at {BASE_URL}: {e}")
        return

    # Generate all speech
    success_count = 0
    error_count = 0
    current = 0

    for category, prompts in SPEECH_PROMPTS.items():
        for text, categories, preferred_gender in prompts:
            current += 1
            voice_id = get_voice_for_gender(preferred_gender)

            # Truncate text for display
            display_text = text[:50] + "..." if len(text) > 50 else text
            print(f"[{current}/{total}] {category}: {display_text}", end=" ", flush=True)

            success, result = generate_speech(text, voice_id, categories)

            if success:
                print("OK")
                success_count += 1
            else:
                print(f"[ERR {result[:20]}]")
                error_count += 1

            # Small delay between generations
            time.sleep(0.1)

    print()
    print("=" * 50)
    print(f"Complete! Success: {success_count}, Errors: {error_count}")


if __name__ == "__main__":
    main()

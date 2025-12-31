"""
Voice Metadata for Bulk Generation

Contains accurate gender, accent, and speaker information for all voices.
VCTK speaker genders sourced from VCTK corpus speaker-info.txt
"""

# VCTK Speaker Gender Map (109 speakers)
# Source: https://github.com/CODEJIN/HierSpeech/blob/master/Pattern_Generator.py
# and VCTK corpus speaker-info.txt
VCTK_FEMALE_SPEAKERS = {
    'p225', 'p228', 'p229', 'p230', 'p231', 'p233', 'p234', 'p236',
    'p238', 'p239', 'p240', 'p244', 'p248', 'p249', 'p250', 'p253',
    'p257', 'p261', 'p262', 'p264', 'p265', 'p266', 'p267', 'p268',
    'p269', 'p276', 'p277', 'p280', 'p282', 'p288', 'p293', 'p294',
    'p295', 'p297', 'p299', 'p300', 'p301', 'p303', 'p305', 'p306',
    'p307', 'p308', 'p310', 'p312', 'p313', 'p314', 'p317', 'p318',
    'p323', 'p329', 'p330', 'p333', 'p335', 'p336', 'p339', 'p340',
    'p341', 'p343', 'p351', 'p361', 'p362',
}

VCTK_MALE_SPEAKERS = {
    'p226', 'p227', 'p232', 'p237', 'p241', 'p243', 'p245', 'p246',
    'p247', 'p251', 'p252', 'p254', 'p255', 'p256', 'p258', 'p259',
    'p260', 'p263', 'p270', 'p271', 'p272', 'p273', 'p274', 'p275',
    'p278', 'p279', 'p281', 'p283', 'p284', 'p285', 'p286', 'p287',
    'p292', 'p298', 'p302', 'p304', 'p311', 'p316', 'p326', 'p334',
    'p345', 'p347', 'p360', 'p363', 'p364', 'p374', 'p376',
}

# Voice definitions with metadata
VOICE_METADATA = {
    # British Female - Jenny Dioco
    'en_GB-jenny_dioco-medium': {
        'gender': 'female',
        'accent': 'british',
        'locale': 'en-GB',
        'name': 'Jenny Dioco',
        'num_speakers': 1,
        'speaker_id': None,  # Single speaker, no ID needed
    },

    # American Male - Sam
    'en_US-sam-medium': {
        'gender': 'male',
        'accent': 'american',
        'locale': 'en-US',
        'name': 'Sam',
        'num_speakers': 1,
        'speaker_id': None,
    },

    # American Male - Kusal
    'en_US-kusal-medium': {
        'gender': 'male',
        'accent': 'american',
        'locale': 'en-US',
        'name': 'Kusal',
        'num_speakers': 1,
        'speaker_id': None,
    },

    # American Neutral - Lessac
    'en_US-lessac-medium': {
        'gender': 'neutral',  # Lessac has a neutral quality
        'accent': 'american',
        'locale': 'en-US',
        'name': 'Lessac',
        'num_speakers': 1,
        'speaker_id': None,
    },

    # British Multi-speaker - VCTK
    'en_GB-vctk-medium': {
        'gender': 'multi',  # Determined by speaker_id
        'accent': 'british',
        'locale': 'en-GB',
        'name': 'VCTK',
        'num_speakers': 109,
        'speaker_id': None,  # Must be specified per generation
    },
}


def get_vctk_gender(speaker_id: int) -> str:
    """
    Get gender for a VCTK speaker ID.

    Args:
        speaker_id: Integer speaker ID (0-108) used by Piper

    Returns:
        'female' or 'male'
    """
    # Map speaker ID to speaker name
    # The Piper model uses a different ordering than raw VCTK
    # We need to look up the speaker name from the model's speaker_id_map
    # For now, use the known mapping from the model

    # Exact mapping from en_GB-vctk-medium.onnx.json speaker_id_map
    # This maps Piper's speaker_id (0-108) to VCTK speaker name
    PIPER_VCTK_SPEAKER_NAMES = [
        'p239', 'p236', 'p264', 'p250', 'p259', 'p247', 'p261', 'p263',
        'p283', 'p286', 'p274', 'p276', 'p270', 'p281', 'p277', 'p231',
        'p271', 'p238', 'p257', 'p273', 'p284', 'p329', 'p361', 'p287',
        'p360', 'p374', 'p376', 'p310', 'p304', 'p334', 'p340', 'p323',
        'p347', 'p330', 'p308', 'p314', 'p317', 'p339', 'p311', 'p294',
        'p305', 'p266', 'p335', 'p318', 'p351', 'p333', 'p313', 'p316',
        'p244', 'p307', 'p363', 'p336', 'p297', 'p312', 'p267', 'p275',
        'p295', 'p258', 'p288', 'p301', 'p232', 'p292', 'p272', 'p280',
        'p278', 'p341', 'p268', 'p298', 'p299', 'p279', 'p285', 'p326',
        'p300', 's5', 'p230', 'p345', 'p254', 'p269', 'p293', 'p252',
        'p262', 'p243', 'p227', 'p343', 'p255', 'p229', 'p240', 'p248',
        'p253', 'p233', 'p228', 'p282', 'p251', 'p246', 'p234', 'p226',
        'p260', 'p245', 'p241', 'p303', 'p265', 'p306', 'p237', 'p249',
        'p256', 'p302', 'p364', 'p225', 'p362',
    ]

    if speaker_id < 0 or speaker_id >= len(PIPER_VCTK_SPEAKER_NAMES):
        return 'neutral'  # Fallback

    speaker_name = PIPER_VCTK_SPEAKER_NAMES[speaker_id].lower()

    if speaker_name in VCTK_FEMALE_SPEAKERS:
        return 'female'
    elif speaker_name in VCTK_MALE_SPEAKERS:
        return 'male'
    else:
        return 'neutral'


def get_voice_tags(voice_id: str, speaker_id: int = None) -> list:
    """
    Get tags for a voice based on its metadata.

    Args:
        voice_id: Voice ID string (e.g., 'en_GB-jenny_dioco-medium')
        speaker_id: Optional speaker ID for multi-speaker voices

    Returns:
        List of tags [gender, accent, voice_name]
    """
    if voice_id not in VOICE_METADATA:
        return []

    meta = VOICE_METADATA[voice_id]
    tags = []

    # Determine gender
    if meta['gender'] == 'multi' and speaker_id is not None:
        # Multi-speaker voice - look up gender by speaker
        gender = get_vctk_gender(speaker_id)
    else:
        gender = meta['gender']

    tags.append(gender)  # 'male', 'female', or 'neutral'
    tags.append(meta['accent'])  # 'british', 'american', etc.

    return tags


def get_available_voices() -> list:
    """Get list of available voice configurations for bulk generation."""
    voices = []

    # Single-speaker voices (use as-is)
    for voice_id, meta in VOICE_METADATA.items():
        if meta['num_speakers'] == 1:
            voices.append({
                'voice_id': voice_id,
                'speaker_id': None,
                'gender': meta['gender'],
                'accent': meta['accent'],
                'name': meta['name'],
            })

    # VCTK multi-speaker - add a selection of speakers
    # Using a mix of male and female speakers for variety
    vctk_selections = [
        # Female speakers (diverse accents)
        (0, 'p239'),   # Female
        (1, 'p236'),   # Female
        (14, 'p277'),  # Female
        (21, 'p329'),  # Female
        (30, 'p318'),  # Female
        # Male speakers
        (4, 'p259'),   # Male
        (7, 'p263'),   # Male
        (8, 'p283'),   # Male
        (9, 'p286'),   # Male
        (23, 'p287'),  # Male
    ]

    for speaker_idx, speaker_name in vctk_selections:
        gender = get_vctk_gender(speaker_idx)
        voices.append({
            'voice_id': 'en_GB-vctk-medium',
            'speaker_id': speaker_idx,
            'gender': gender,
            'accent': 'british',
            'name': f'VCTK-{speaker_name}',
        })

    return voices


# Quick test
if __name__ == '__main__':
    voices = get_available_voices()
    print(f"Available voices ({len(voices)}):")
    for v in voices:
        print(f"  {v['name']}: {v['gender']}, {v['accent']}")

    # Test VCTK gender lookup
    print("\nVCTK gender test:")
    for i in [0, 1, 4, 7, 8, 9, 14, 21, 23, 30]:
        print(f"  Speaker {i}: {get_vctk_gender(i)}")

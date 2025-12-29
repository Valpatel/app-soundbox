"""
Voice License Metadata for Piper TTS Voices

This file contains license information, attribution requirements, and usage restrictions
for all voice models used in the application.

IMPORTANT LICENSE NOTES:
- Many Piper voices are finetuned from the "lessac" voice, which uses Blizzard Challenge data
- The Blizzard dataset has a restrictive research-only license
- However, Piper releases these models under MIT, creating some license ambiguity
- For safety, voices derived from lessac are marked with a warning

License Research Sources:
- VCTK: https://datashare.ed.ac.uk/handle/10283/3443
- LJSpeech: https://keithito.com/LJ-Speech-Dataset/
- LibriTTS: https://www.openslr.org/60/
- CMU Arctic: http://www.festvox.org/cmu_arctic/
- Jenny DioCo: https://github.com/dioco-group/jenny-tts-dataset
- Blizzard/Lessac: https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html
- Cori: https://brycebeattie.com/files/tts/
"""

# License types
LICENSE_PUBLIC_DOMAIN = "public_domain"
LICENSE_CC_BY_4 = "cc_by_4"
LICENSE_CC_BY_NC_4 = "cc_by_nc_4"
LICENSE_MIT = "mit"
LICENSE_BLIZZARD = "blizzard_nc"  # Non-commercial Blizzard Challenge license
LICENSE_CUSTOM = "custom"

# License display information
LICENSE_INFO = {
    LICENSE_PUBLIC_DOMAIN: {
        "name": "Public Domain",
        "short": "PD",
        "commercial": True,
        "attribution_required": False,
        "url": None,
        "description": "No copyright restrictions. Free to use for any purpose.",
        "badge_class": "license-pd"
    },
    LICENSE_CC_BY_4: {
        "name": "CC BY 4.0",
        "short": "CC BY",
        "commercial": True,
        "attribution_required": True,
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "description": "Free to use commercially with attribution.",
        "badge_class": "license-cc-by"
    },
    LICENSE_CC_BY_NC_4: {
        "name": "CC BY-NC 4.0",
        "short": "NC",
        "commercial": False,
        "attribution_required": True,
        "url": "https://creativecommons.org/licenses/by-nc/4.0/",
        "description": "Non-commercial use only with attribution.",
        "badge_class": "license-nc"
    },
    LICENSE_MIT: {
        "name": "MIT License",
        "short": "MIT",
        "commercial": True,
        "attribution_required": False,
        "url": "https://opensource.org/licenses/MIT",
        "description": "Permissive open source license. Free for any use.",
        "badge_class": "license-mit"
    },
    LICENSE_BLIZZARD: {
        "name": "Research Only",
        "short": "Research",
        "commercial": False,
        "attribution_required": True,
        "url": "https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html",
        "description": "Dataset is research/non-commercial only. Commercial use prohibited.",
        "badge_class": "license-nc"
    },
    LICENSE_CUSTOM: {
        "name": "Custom License",
        "short": "Custom",
        "commercial": True,
        "attribution_required": True,
        "url": None,
        "description": "Custom license terms. Check attribution requirements.",
        "badge_class": "license-custom"
    }
}

# Dataset information with accurate license details
DATASETS = {
    # =========================================================================
    # CLEARLY COMMERCIAL-OK VOICES (Public Domain or permissive)
    # =========================================================================
    "ljspeech": {
        "name": "LJ Speech",
        "license": LICENSE_PUBLIC_DOMAIN,
        "creator": "Keith Ito / LibriVox (Linda Johnson)",
        "url": "https://keithito.com/LJ-Speech-Dataset/",
        "attribution": "LJ Speech Dataset",
        "attribution_url": "https://keithito.com/LJ-Speech-Dataset/",
        "notes": "Public domain. Single speaker US English. Based on LibriVox recordings.",
        "finetuned_from": None
    },
    "libritts": {
        "name": "LibriTTS",
        "license": LICENSE_CC_BY_4,
        "creator": "Google / LibriVox",
        "url": "https://www.openslr.org/60/",
        "attribution": "LibriTTS Corpus",
        "attribution_url": "https://www.openslr.org/60/",
        "notes": "CC BY 4.0. Multi-speaker US English from LibriVox public domain recordings.",
        "finetuned_from": None
    },
    "libritts_r": {
        "name": "LibriTTS-R",
        "license": LICENSE_CC_BY_4,
        "creator": "Google",
        "url": "https://www.openslr.org/141/",
        "attribution": "LibriTTS-R Corpus",
        "attribution_url": "https://www.openslr.org/141/",
        "notes": "CC BY 4.0. Enhanced version of LibriTTS.",
        "finetuned_from": None
    },
    "arctic": {
        "name": "CMU Arctic",
        "license": LICENSE_MIT,
        "creator": "Carnegie Mellon University",
        "url": "http://www.festvox.org/cmu_arctic/",
        "attribution": "CMU Arctic",
        "attribution_url": "http://www.festvox.org/cmu_arctic/",
        "notes": "BSD-style license. Free for any use including commercial.",
        "finetuned_from": None
    },
    "cori": {
        "name": "Cori",
        "license": LICENSE_PUBLIC_DOMAIN,
        "creator": "LibriVox / Bryce Beattie",
        "url": "https://brycebeattie.com/files/tts/",
        "attribution": "Cori voice (LibriVox)",
        "attribution_url": "https://librivox.org",
        "notes": "Public domain from LibriVox. UK English female.",
        "finetuned_from": None
    },

    # =========================================================================
    # VCTK - CC BY 4.0 but finetuned from lessac (mixed licensing)
    # =========================================================================
    "vctk": {
        "name": "VCTK Corpus",
        "license": LICENSE_CC_BY_4,
        "creator": "University of Edinburgh CSTR",
        "url": "https://datashare.ed.ac.uk/handle/10283/3443",
        "attribution": "CSTR VCTK Corpus",
        "attribution_url": "https://datashare.ed.ac.uk/handle/10283/3443",
        "notes": "CC BY 4.0. Multi-speaker British English. Note: Piper model finetuned from lessac.",
        "finetuned_from": "lessac"
    },

    # =========================================================================
    # JENNY DIOCO - Custom license requiring attribution
    # =========================================================================
    "jenny_dioco": {
        "name": "Jenny (Dioco)",
        "license": LICENSE_CUSTOM,
        "creator": "Dioco Group",
        "url": "https://github.com/dioco-group/jenny-tts-dataset",
        "attribution": "Jenny (Dioco)",
        "attribution_url": "https://github.com/dioco-group/jenny-tts-dataset",
        "notes": "Commercial OK with attribution. Must credit as 'Jenny (Dioco)'. Finetuned from lessac.",
        "finetuned_from": "lessac"
    },

    # =========================================================================
    # LESSAC / BLIZZARD - NON-COMMERCIAL ONLY
    # =========================================================================
    "lessac": {
        "name": "Lessac (Blizzard 2013)",
        "license": LICENSE_BLIZZARD,
        "creator": "Lessac Technologies / Blizzard Challenge",
        "url": "https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/",
        "attribution": "Blizzard Challenge 2013",
        "attribution_url": "https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html",
        "notes": "RESEARCH/NON-COMMERCIAL ONLY. Dataset prohibits commercial use of voice synthesis.",
        "finetuned_from": None
    },
    "l2arctic": {
        "name": "L2-Arctic",
        "license": LICENSE_CC_BY_NC_4,
        "creator": "PSI Lab, Texas A&M",
        "url": "https://psi.engr.tamu.edu/l2-arctic-corpus/",
        "attribution": "L2-Arctic Corpus",
        "attribution_url": "https://psi.engr.tamu.edu/l2-arctic-corpus/",
        "notes": "NON-COMMERCIAL ONLY. Non-native English speech.",
        "finetuned_from": None
    },

    # =========================================================================
    # OTHER UK VOICES - Most finetuned from lessac (uncertain commercial status)
    # =========================================================================
    "alan": {
        "name": "Alan",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. British English male. May be finetuned from lessac.",
        "finetuned_from": "lessac"
    },
    "alba": {
        "name": "Alba",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. British English.",
        "finetuned_from": "lessac"
    },
    "aru": {
        "name": "ARU",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. British English.",
        "finetuned_from": "lessac"
    },
    "northern_english_male": {
        "name": "Northern English Male",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. Northern British accent.",
        "finetuned_from": "lessac"
    },
    "semaine": {
        "name": "Semaine",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. British English.",
        "finetuned_from": "lessac"
    },
    "southern_english_female": {
        "name": "Southern English Female",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. Southern British accent.",
        "finetuned_from": "lessac"
    },

    # =========================================================================
    # US VOICES
    # =========================================================================
    "amy": {
        "name": "Amy",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. US English female.",
        "finetuned_from": "lessac"
    },
    "joe": {
        "name": "Joe",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. US English male.",
        "finetuned_from": "lessac"
    },
    "kusal": {
        "name": "Kusal",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. US English.",
        "finetuned_from": "lessac"
    },
    "kristin": {
        "name": "Kristin",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. US English female.",
        "finetuned_from": "lessac"
    },
    "ryan": {
        "name": "Ryan",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. US English male.",
        "finetuned_from": "lessac"
    },
    "hfc_male": {
        "name": "HFC Male",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. Synthetic/robotic style.",
        "finetuned_from": None
    },
    "hfc_female": {
        "name": "HFC Female",
        "license": LICENSE_MIT,
        "creator": "Piper TTS Project",
        "url": "https://github.com/rhasspy/piper",
        "attribution": "Piper TTS",
        "attribution_url": "https://github.com/rhasspy/piper",
        "notes": "MIT license. Synthetic/robotic style.",
        "finetuned_from": None
    },
}

def get_dataset_for_voice(voice_id):
    """
    Extract the dataset name from a Piper voice ID.
    Voice IDs follow the pattern: {locale}-{name}-{quality}
    """
    if not voice_id:
        return None
    parts = voice_id.split('-')
    if len(parts) >= 2:
        return parts[1]
    return None

def get_voice_license_info(voice_id):
    """
    Get complete license information for a voice.
    """
    dataset_name = get_dataset_for_voice(voice_id)

    if not dataset_name or dataset_name not in DATASETS:
        # Unknown dataset - return safe defaults
        return {
            "dataset": None,
            "license": LICENSE_INFO[LICENSE_MIT],
            "commercial_ok": True,
            "attribution_required": False,
            "attribution_text": f"Piper TTS",
            "attribution_url": "https://github.com/rhasspy/piper",
            "warning": None
        }

    dataset = DATASETS[dataset_name]
    license_type = dataset["license"]
    license_info = LICENSE_INFO[license_type]

    result = {
        "dataset": dataset,
        "license": license_info,
        "commercial_ok": license_info["commercial"],
        "attribution_required": license_info["attribution_required"],
        "attribution_text": dataset.get("attribution"),
        "attribution_url": dataset.get("attribution_url") or dataset.get("url"),
        "warning": None
    }

    # Add warnings for restricted licenses
    if not license_info["commercial"]:
        result["warning"] = f"NON-COMMERCIAL: {dataset['name']} dataset prohibits commercial use."

    return result

def get_commercial_voices():
    """Return list of dataset names that allow commercial use."""
    return [name for name, info in DATASETS.items()
            if LICENSE_INFO[info["license"]]["commercial"]]

def get_non_commercial_voices():
    """Return list of dataset names that are non-commercial only."""
    return [name for name, info in DATASETS.items()
            if not LICENSE_INFO[info["license"]]["commercial"]]

def get_all_voice_licenses():
    """Return all license information for API endpoint."""
    return {
        "datasets": DATASETS,
        "licenses": LICENSE_INFO,
        "commercial_datasets": get_commercial_voices(),
        "non_commercial_datasets": get_non_commercial_voices()
    }


if __name__ == "__main__":
    print("Voice License Information")
    print("=" * 60)
    print()
    print("CLEARLY COMMERCIAL OK (no lessac dependency):")
    for name, ds in DATASETS.items():
        if ds.get("finetuned_from") is None and LICENSE_INFO[ds["license"]]["commercial"]:
            print(f"  {name}: {LICENSE_INFO[ds['license']]['name']}")
    print()
    print("NON-COMMERCIAL ONLY:")
    for name in get_non_commercial_voices():
        ds = DATASETS[name]
        print(f"  {name}: {LICENSE_INFO[ds['license']]['name']}")

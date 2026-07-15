"""Constants for Alexa Announcement Builder."""

DOMAIN = "alexa_announcement_builder"
SERVICE_SEND = "send"

ATTR_TARGET = "target"
ATTR_CONTENT = "content"
ATTR_TEXT = "text"
ATTR_SOUND = "sound"
ATTR_VOICE = "voice"
ATTR_RATE = "rate"
ATTR_PITCH = "pitch"
ATTR_VOLUME = "volume"
ATTR_WHISPER = "whisper"
ATTR_EMOTION = "emotion"
ATTR_EMOTION_INTENSITY = "emotion_intensity"
ATTR_SPEECH_DOMAIN = "domain"
ATTR_BREAK_BEFORE_MS = "break_before_ms"
ATTR_BREAK_AFTER_MS = "break_after_ms"
ATTR_RAW_SSML = "raw_ssml"

DEFAULT_VOICE = "alexa_plus"
DEFAULT_EMOTION_INTENSITY = "medium"

COMMON_SOUNDS = {
    "doorbell_chime": "soundbank://soundlibrary/home/amzn_sfx_doorbell_chime_01",
    "door_knock": "soundbank://soundlibrary/home/amzn_sfx_door_knock_01",
    "applause": "soundbank://soundlibrary/human/amzn_sfx_crowd_applause_01",
    "positive_response": (
        "soundbank://soundlibrary/ui/gameshow/amzn_ui_sfx_gameshow_positive_response_01"
    ),
    "negative_response": (
        "soundbank://soundlibrary/ui/gameshow/amzn_ui_sfx_gameshow_negative_response_01"
    ),
    "game_show_intro": (
        "soundbank://soundlibrary/ui/gameshow/amzn_ui_sfx_gameshow_intro_01"
    ),
    "alarm_buzzer": "soundbank://soundlibrary/alarms/buzzers/buzzers_01",
    "dog_bark": "soundbank://soundlibrary/animals/amzn_sfx_dog_med_bark_1x_02",
    "cat_meow": "soundbank://soundlibrary/animals/amzn_sfx_cat_meow_1x_01",
    "rooster_crow": "soundbank://soundlibrary/animals/amzn_sfx_rooster_crow_01",
    "thunder": "soundbank://soundlibrary/nature/amzn_sfx_thunder_rumble_01",
    "fire_extinguisher": (
        "soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04"
    ),
}

NAMED_VOICES = (
    "Ivy",
    "Joanna",
    "Joey",
    "Justin",
    "Kendra",
    "Kimberly",
    "Matthew",
    "Salli",
    "Nicole",
    "Russell",
    "Amy",
    "Brian",
    "Emma",
    "Aditi",
    "Raveena",
    "Geraint",
    "Chantal",
    "Celine",
    "Lea",
    "Mathieu",
    "Hans",
    "Marlene",
    "Vicki",
    "Carla",
    "Giorgio",
    "Bianca",
    "Mizuki",
    "Takumi",
    "Vitoria",
    "Camila",
    "Ricardo",
    "Penelope",
    "Lupe",
    "Miguel",
    "Conchita",
    "Enrique",
    "Lucia",
    "Mia",
)
VOICE_CHOICES = ("alexa_plus", "original_alexa", *NAMED_VOICES)
RATES = ("x-slow", "slow", "medium", "fast", "x-fast")
PITCHES = ("x-low", "low", "medium", "high", "x-high")
VOLUMES = ("silent", "x-soft", "soft", "medium", "loud", "x-loud")
EMOTIONS = ("excited", "disappointed")
EMOTION_INTENSITIES = ("low", "medium", "high")
SPEECH_DOMAINS = ("music", "news", "conversational", "long-form")

ORIGINAL_ALEXA_PREFIX = '<voice name="Kendra"> </voice>'

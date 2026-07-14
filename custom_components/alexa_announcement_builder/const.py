"""Constants for Alexa Announcement Builder."""

DOMAIN = "alexa_announcement_builder"
SERVICE_SEND = "send"

ATTR_TARGET = "target"
ATTR_TEXT = "text"
ATTR_MODE = "mode"
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

DEFAULT_MODE = "speak"
DEFAULT_VOICE = "alexa_plus"
DEFAULT_EMOTION_INTENSITY = "medium"

MODES = ("speak", "announce")
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

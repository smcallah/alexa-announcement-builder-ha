# Alexa Announcement Builder

Alexa Announcement Builder is a service-only Home Assistant custom integration
that combines ordered messages, sounds, and optional raw markup into
Alexa-compatible SSML. Each message can use its own voice and speech options.
The completed sequence is sent through an existing Alexa Devices notify entity
using Home Assistant's `notify.send_message` action.

The integration creates no entities and does not connect to Amazon itself. An
Alexa Devices integration that provides notify entities such as
`notify.office_echo_speak` or `notify.office_echo_announce` must already be
installed and working.

## Installation

### HACS custom repository

1. In HACS, open **Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add this GitHub repository URL and select **Integration** as the category.
4. Search for **Alexa Announcement Builder** and install it.
5. Restart Home Assistant.

### Manual installation

Copy `custom_components/alexa_announcement_builder` into the
`custom_components` directory in your Home Assistant configuration directory,
then restart Home Assistant.

### Enable the integration

1. Go to **Settings → Devices & services**.
2. Select **Add Integration**.
3. Search for **Alexa Announcement Builder**.
4. Select **Submit** to create the integration entry.

No `configuration.yaml` entry is required. The
`alexa_announcement_builder.send` action will then be available in Developer
Tools and automations.

## Basic usage

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.office_echo_speak
  sequence:
    - content:
        active_choice: Message
        Message:
          text: "The garage door is still open."
          voice: original_alexa
          rate:
            active_choice: Named rate
            Named rate: x-slow
          volume:
            active_choice: Named volume
            Named volume: loud
```

The selected notify entity decides whether Alexa speaks or announces the
message. Choose the corresponding `_speak` or `_announce` entity as the target.
Any sequence containing Sound must use a `_speak` entity because the Alexa
Devices Announce path plays its announcement chime but does not play embedded
audio markup.

## Sequence builder

The **Sequence** field starts with an **Add** button. Each added item opens a
chooser for **Message**, **Sound**, or **Raw SSML** and displays only the options
for that content type. Saved items collapse into compact rows with Edit and
Delete controls. Drag the handle on a row to change the playback order.

Add as many items as needed. Message items keep their own voice, prosody,
whisper, emotion, and speech-domain settings. The integration normalizes every
item independently and then concatenates the generated SSML in list order.

For example, this sequence speaks with Joanna, plays a door knock, and finishes
with the original Alexa voice:

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.office_echo_speak
  sequence:
    - content:
        active_choice: Message
        Message:
          text: "Someone is at the door."
          voice: Joanna
    - content:
        active_choice: Sound
        Sound: door_knock
    - content:
        active_choice: Message
        Message:
          text: "Please check the camera."
          voice: original_alexa
```

Rate, pitch, and volume each offer a named-value dropdown and a bounded custom
number box. Home Assistant stores the selected option as a `choose` value. For
example, a custom 80% rate, +20% pitch, and -3 dB volume adjustment are written
as:

```yaml
sequence:
  - content:
      active_choice: Message
      Message:
        text: "Example message."
        rate:
          active_choice: Enter %-age
          Enter %-age: 80
        pitch:
          active_choice: Enter %-age
          Enter %-age: 20
        volume:
          active_choice: Enter dB adjustment
          Enter dB adjustment: -3
```

Custom rate values are limited to 20 through 200, pitch values to -33.3 through
50, and volume adjustments to -6 through 6 dB.

## Sound selection

Choose **Sound** as the content type, then select a curated Alexa sound from the
dropdown:

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.office_echo_speak
  sequence:
    - content:
        active_choice: Sound
        Sound: doorbell_chime
```

The Sound dropdown also accepts a custom value in any of these forms:

- A public HTTPS URL for an Alexa-compatible MP3.
- An Alexa sound-library URI beginning with
  `soundbank://soundlibrary/`.
- A complete `<audio src="..."/>` tag copied from Amazon's sound library.

For example:

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.office_echo_speak
  sequence:
    - content:
        active_choice: Sound
        Sound: '<audio src="soundbank://soundlibrary/air/fire_extinguisher/fire_extinguisher_04"/>'
```

Copied tags are parsed and rebuilt rather than passed through as trusted
markup. Custom HTTPS audio must be publicly reachable with a trusted TLS
certificate and must meet Amazon's MP3 encoding, sample-rate, bit-rate, and
duration requirements. The integration validates the URL format but does not
download or inspect the remote file.

Each Sound item stores one preset name or custom URI, so changing between them
replaces the previous value instead of combining both. The per-item content
chooser prevents attaching message-only voice or speech effects to Sound.
Sounds can be placed anywhere in the ordered sequence. Selecting an Announce
target for a sequence containing Sound is rejected with a clear validation
error; select the matching Speak target instead.

## Voice selection

The `voice` dropdown puts both Alexa defaults first, followed by every supported
named Polly voice:

- **Alexa+ default voice** (`alexa_plus`) leaves the generated speech outside a
  voice tag, allowing the current default Alexa voice to handle it.
- **Original Alexa default voice** (`original_alexa`) inserts
  `<voice name="Kendra"> </voice>` before the speech. The single space is
  intentional and works around Alexa+ taking over speech on devices where the
  behavior has been observed.
- A named voice such as `Joanna` wraps the speech in the corresponding Amazon
  Polly voice tag. Each option shows its locale; voices from a different locale
  may pronounce the supplied text differently.

Example with a named voice:

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.kitchen_echo_speak
  sequence:
    - content:
        active_choice: Message
        Message:
          text: "Dinner is ready."
          voice: Joanna
          rate:
            active_choice: Named rate
            Named rate: slow
          emotion: excited
          emotion_intensity: medium
```

Example announcement automation:

```yaml
alias: Announce an open garage door
triggers:
  - trigger: state
    entity_id: cover.garage_door
    to: open
    for: "00:10:00"
actions:
  - action: alexa_announcement_builder.send
    data:
      target: notify.office_echo_announce
      sequence:
        - content:
            active_choice: Message
            Message:
              text: "The garage door has been open for ten minutes."
              voice: original_alexa
              volume:
                active_choice: Named volume
                Named volume: loud
      break_before_ms: 250
mode: single
```

For trusted, hand-authored markup, `raw_ssml` bypasses generation and escaping:

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.office_echo_speak
  sequence:
    - content:
        active_choice: Raw SSML
        Raw SSML: '<prosody rate="slow">This markup is sent unchanged.</prosody>'
```

Message text is XML-escaped automatically. Raw SSML items are deliberately not
escaped or validated and must not contain outer `<speak>` tags. Existing YAML
using the former single `content` chooser or separate `text`, `sound`, and
`raw_ssml` fields remains accepted, but single-content fields cannot be combined
with `sequence`.

## Alexa SSML caveats

Alexa+ appears to interpret some SSML pitch values as speed changes rather than
pitch changes. Amazon SSML behavior can also vary by Echo model, account,
language, Alexa backend, and upstream Alexa Devices integration. Test voice,
emotion, domain, and prosody combinations on the actual target device.

## Development

The project targets Python 3.12 and current Home Assistant service APIs. Install
the lightweight test dependencies and run the checks:

```bash
python -m pip install -r requirements-test.txt
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

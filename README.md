# Alexa Announcement Builder

Alexa Announcement Builder is a service-only Home Assistant custom integration
that turns plain text and a small set of options into Alexa-compatible SSML. It
then sends that SSML through an existing Alexa Devices notify entity using
Home Assistant's `notify.send_message` action.

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
  text: "The garage door is still open."
  mode: speak
  voice: original_alexa
  rate: x-slow
  volume: loud
```

`mode` is descriptive in this first release. The selected notify entity decides
whether Alexa speaks or announces the message.

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
  text: "Dinner is ready."
  voice: Joanna
  rate: slow
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
      text: "The garage door has been open for ten minutes."
      mode: announce
      voice: original_alexa
      break_before_ms: 250
      volume: loud
mode: single
```

For trusted, hand-authored markup, `raw_ssml` bypasses generation and escaping:

```yaml
action: alexa_announcement_builder.send
data:
  target: notify.office_echo_speak
  raw_ssml: '<prosody rate="slow">This markup is sent unchanged.</prosody>'
```

Plain `text` is XML-escaped automatically. `raw_ssml` is deliberately not
escaped or validated and must not contain outer `<speak>` tags.

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

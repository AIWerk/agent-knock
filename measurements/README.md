# Measurements

What has been measured so far, and what has not. Raw call logs and recordings are not
published: they contain call metadata from a production phone line.

## 1. Simulation: in-band DTMF over codecs (2026-11-13)

`simulate_inband.py` generates frames as audio tones, sends them through a codec
(ffmpeg) with added noise, decodes them with a Goertzel detector and checks the frame.
Results for 10 trials per case: `simulate_inband_result.txt`.

| Codec | 5 symbols/s | 7 symbols/s |
|---|---|---|
| G.711 (landline, SIP) | 10/10 all frames | 10/10 all frames |
| G.726, Opus 12 kbit/s | 10/10 all frames | 10/10 all frames |
| GSM (legacy mobile) | short frames 9-10/10, long OFFER 7-9/10 | long OFFER 3-7/10 |
| Opus 6 kbit/s (weak mobile data) | noisy: 0-1/10 | 0-5/10 |

The script was written for the v0.2 frame layout; frame lengths are comparable to v0.3.

## 2. Real line, test 1 (2026-11-13/14)

Chain: mobile phone → Swiss mobile network → Swiss SIP provider → Asterisk.

| Transmission | Result |
|---|---|
| In-band (laptop speaker held to the phone microphone, 12 frames) | **0/12.** A 1000 Hz start tone got through but dropped to about one sixth of its level within a second; only single-frequency fragments of the DTMF remained. Likely cause: noise suppression in the phone or network (inferred, not proven). |
| Out-of-band (phone keypad, 7 symbols `1 2 3 4 5 * #`) | **7/7**, in order. The network normalised every event to 70 ms. Asterisk extends events below 80 ms instead of dropping them. |

Conclusion: in-band frames cannot be relied on when speech processing is in the path.
Hence the RFC 4733 requirement in section 5 of the spec.

## 3. Real line, test 2 (2026-11-14)

Chain: mobile phone → Swiss mobile network → Swiss SIP provider → Asterisk → ElevenLabs
voice agent (test agent, not in production use). Asterisk sends ANNOUNCE at pickup.

| Direction | Result |
|---|---|
| Caller → callee (`*10#`, a keypad test sequence rather than a valid frame, typed while the agent was greeting) | **Delivered end to end, out of band.** Provider leg RFC 4733 payload type 97, ElevenLabs leg payload type 101. The agent received it as DTMF input and it interrupted the greeting. Digits arrived at about 57-61 ms each. |
| Callee → caller (ANNOUNCE `*140360#` at pickup) | **Sent by Asterisk** (about 80 RFC 4733 packets, 7 digits, 100 ms each), **but not audible on the mobile phone.** Lost or not rendered on the provider/mobile side. For a human caller this is the intended outcome. |

## Not measured yet

- Whether ANNOUNCE reaches a calling agent that is itself on SIP, through a different provider (agent-to-agent).
- Full handshake timing between two real agents, including language model latency.
- Sending side of the ElevenLabs keypad-tone tool (RFC 4733 or in-band, pace).

Contributions with measurements from other networks and platforms are very welcome.

# Agent Knock

**Two AI phone agents recognise each other during a call and continue over the internet.**

More and more phone calls are answered and placed by AI voice agents. When an agent calls
a business and an agent answers, both still talk, slowly and with transcription errors,
although they could exchange structured data in milliseconds. Agent Knock is a short
handshake over DTMF tones that lets the two agents find out about each other and switch
to an [A2A](https://a2a-protocol.org) channel over HTTPS. If the other side is a human,
the call simply continues as a normal conversation.

Status: **v0.3 draft, request for comments.** Not a standard, not affiliated with the A2A project.

## When it applies

Only when the caller knows nothing but the phone number. If the caller can find the
callee's A2A endpoint before the call (DNS, a directory, the website), it should not call
at all and connect directly instead.

## How it works

```
callee (answers)                         caller
  ANNOUNCE  *140360#      ───────▶        "I am an agent, I speak Agent Knock v03"
            ◀───────       HELLO  *10 03 <code A> CC#
  OFFER     *11 03 <session> <code B> <len> <domain...> CC#   ───────▶
  (DOMAIN continuation frames for long domains)
            ◀───────       ACK    *1262#
  caller: HTTPS to the callee's domain; the endpoint proves code A first, then the caller proves code B; then A2A
```

- Frames are `* type data checkdigits #`, check digits ISO 7064 MOD 97-10 (as in IBAN).
- In SIP calls, frames MUST be sent out of band (RFC 4733). In-band tones did not survive our mobile-network test (see measurements).
- The callee sends ANNOUNCE at pickup, waits half a second, then greets as usual; a HELLO that arrives during the greeting interrupts it. A caller sends HELLO only after an ANNOUNCE, so humans, IVR menus and agents that do not know the protocol never receive one.
- The callee's domain comes from the call itself, never from a third-party source. This is what prevents a relay (man-in-the-middle) attack.

Details, timing, error handling and security considerations: **[SPEC.md](SPEC.md)**.

## What has been tested

On a real line (Swiss mobile → SIP provider → Asterisk → ElevenLabs voice agent),
2026-11-14: a caller's out-of-band DTMF sequence reached the voice agent as DTMF input and
interrupted its greeting. The callee's ANNOUNCE was sent but is not audible on a mobile
phone, which is the intended behaviour for human callers. Agent-to-agent over SIP through
different providers is **not yet measured**. See [measurements/](measurements/).

## Repository

| Path | Content |
|---|---|
| `SPEC.md` | The specification, v0.3 draft |
| `reference/agent_knock.py` | Reference encoder/decoder for frames (Python, no dependencies) |
| `reference/test_agent_knock.py` | Tests against the example frames in the spec (`python3 -m pytest reference/`) |
| `measurements/` | Codec simulation and real-line results |

## How you can help

- Measurements from other networks, SIP providers and voice-agent platforms, especially agent-to-agent calls.
- Review of the security section (relay attacks, a PAKE-based variant).
- Implementations on voice-agent platforms.

Open an issue or a pull request.

## License

- Specification and documentation: [CC BY 4.0](LICENSE-SPEC)
- Code: [Apache License 2.0](LICENSE-CODE)

Author: Attila Bergsmann, [AIWerk](https://aiwerk.ch), Switzerland.

"""Agent Knock v0.3 - reference encoder/decoder for DTMF frames.

Frame:  *  TT  data  CC  #
- TT: two-digit type (never starts with 0)
- CC: ISO 7064 MOD 97-10 check digits over TT+data
- the frame without the closing '#' is at most 50 symbols

This module only builds and parses frames. Sending them (RFC 4733),
timing, and the HTTPS hand-off are out of scope. See SPEC.md.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

VERSION = "03"
MAX_FRAME = 50          # symbols without the closing '#'
OFFER_CHARS = 15        # domain characters carried in OFFER
DOMAIN_CHARS = 22       # domain characters per DOMAIN frame
MAX_DOMAIN = OFFER_CHARS + 2 * DOMAIN_CHARS  # 59

ANNOUNCE, HELLO, OFFER, ACK, DOMAIN, NAK, ABORT = "14", "10", "11", "12", "13", "19", "99"
NAMES = {ANNOUNCE: "ANNOUNCE", HELLO: "HELLO", OFFER: "OFFER", ACK: "ACK",
         DOMAIN: "DOMAIN", NAK: "NAK", ABORT: "ABORT"}

_ENC = {**{chr(97 + i): f"{i + 1:02d}" for i in range(26)},
        **{str(i): str(30 + i) for i in range(10)}, "-": "40", ".": "41"}
_DEC = {v: k for k, v in _ENC.items()}


class FrameError(ValueError):
    pass


# --- check digits -----------------------------------------------------------

def check_digits(digits: str) -> str:
    """CC = 98 - (N * 100 mod 97), two digits."""
    return f"{98 - (int(digits) * 100 % 97):02d}"


def frame(body: str) -> str:
    if not body.isdigit() or body[0] == "0":
        raise FrameError("body must be digits and must not start with 0")
    f = "*" + body + check_digits(body) + "#"
    if len(f) - 1 > MAX_FRAME:
        raise FrameError(f"frame too long: {len(f) - 1} > {MAX_FRAME}")
    return f


# --- domain -----------------------------------------------------------------

def encode_domain(domain: str) -> str:
    d = domain.strip().lower()
    if not 1 <= len(d) <= MAX_DOMAIN:
        raise FrameError(f"domain length must be 1-{MAX_DOMAIN}")
    try:
        return "".join(_ENC[c] for c in d)
    except KeyError as e:
        raise FrameError(f"character not allowed: {e.args[0]!r} (use the xn-- form)") from None


def decode_domain(digits: str) -> str:
    if len(digits) % 2:
        raise FrameError("odd number of domain digits")
    try:
        return "".join(_DEC[digits[i:i + 2]] for i in range(0, len(digits), 2))
    except KeyError as e:
        raise FrameError(f"reserved domain code: {e.args[0]}") from None


# --- builders ---------------------------------------------------------------

def new_code() -> str:
    """Six-digit A or B code from a CSPRNG."""
    return f"{secrets.randbelow(10**6):06d}"


def announce(version: str = VERSION) -> str:
    return frame(ANNOUNCE + version)


def hello(code_a: str, version: str = VERSION) -> str:
    return frame(HELLO + version + code_a)


def offer_group(domain: str, session: str, code_b: str, version: str = VERSION) -> list[str]:
    """OFFER plus the DOMAIN continuation frames needed for `domain`."""
    d = domain.strip().lower()
    enc = encode_domain(d)
    frames = [frame(OFFER + version + session + code_b + f"{len(d):02d}" + enc[:2 * OFFER_CHARS])]
    rest = enc[2 * OFFER_CHARS:]
    seq = 1
    while rest:
        frames.append(frame(DOMAIN + str(seq) + rest[:2 * DOMAIN_CHARS]))
        rest = rest[2 * DOMAIN_CHARS:]
        seq += 1
    return frames


def ack() -> str: return frame(ACK)
def nak() -> str: return frame(NAK)
def abort() -> str: return frame(ABORT)


# --- parser -----------------------------------------------------------------

@dataclass
class Frame:
    type: str
    name: str
    fields: dict


def parse(f: str) -> Frame:
    """Validate symbols, check digits and per-type length; return the fields."""
    if len(f) < 6 or f[0] != "*" or f[-1] != "#":
        raise FrameError("frame must start with * and end with #")
    if len(f) - 1 > MAX_FRAME:
        raise FrameError("frame too long")
    digits = f[1:-1]
    if not digits.isdigit():
        raise FrameError("only 0-9 allowed between * and #")
    if int(digits) % 97 != 1:
        raise FrameError("check digits do not match")
    t, data = digits[:2], digits[2:-2]
    n = len(digits)
    if t == ANNOUNCE:
        if n != 6: raise FrameError("ANNOUNCE must have 6 digits")
        return Frame(t, "ANNOUNCE", {"version": data})
    if t == HELLO:
        if n != 12: raise FrameError("HELLO must have 12 digits")
        return Frame(t, "HELLO", {"version": data[:2], "code_a": data[2:]})
    if t == OFFER:
        if n < 20: raise FrameError("OFFER too short")
        length = int(data[12:14])
        if not 1 <= length <= MAX_DOMAIN:
            raise FrameError("domain length out of range")
        if n != 18 + 2 * min(length, OFFER_CHARS):
            raise FrameError("OFFER length does not match L")
        return Frame(t, "OFFER", {"version": data[:2], "session": data[2:6], "code_b": data[6:12],
                                  "length": length, "domain_part": decode_domain(data[14:])})
    if t == DOMAIN:
        if n < 7 or (n - 5) % 2: raise FrameError("bad DOMAIN length")
        seq = int(data[0])
        if seq not in (1, 2): raise FrameError("DOMAIN sequence must be 1 or 2")
        if (n - 5) // 2 > DOMAIN_CHARS: raise FrameError("DOMAIN carries too many characters")
        return Frame(t, "DOMAIN", {"seq": seq, "domain_part": decode_domain(data[1:])})
    if t in (ACK, NAK, ABORT):
        if n != 4: raise FrameError(f"{NAMES[t]} must have 4 digits")
        return Frame(t, NAMES[t], {})
    raise FrameError(f"unknown frame type {t}")


def assemble_domain(offer: Frame, domains: list[Frame]) -> str:
    """Join OFFER and DOMAIN parts; check the count and total length against L."""
    need = max(0, -(-(offer.fields["length"] - OFFER_CHARS) // DOMAIN_CHARS))
    if [d.fields["seq"] for d in domains] != list(range(1, need + 1)):
        raise FrameError(f"expected DOMAIN frames 1..{need}")
    domain = offer.fields["domain_part"] + "".join(d.fields["domain_part"] for d in domains)
    if len(domain) != offer.fields["length"]:
        raise FrameError("assembled domain length does not match L")
    return domain


if __name__ == "__main__":
    print("ANNOUNCE", announce())
    print("HELLO   ", hello("739104"))
    for f in offer_group("fogaszat-muster.ch", "4821", "520466"):
        print("OFFER/DOMAIN", f, len(f), "symbols")
    print("ACK NAK ABORT", ack(), nak(), abort())

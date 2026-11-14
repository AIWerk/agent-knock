"""Checks the reference code against the example frames in SPEC.md. Run: python3 -m pytest reference/"""
import pytest

from agent_knock import (FrameError, abort, ack, announce, assemble_domain, hello, nak,
                         offer_group, parse)

SPEC_EXAMPLES = {
    "ANNOUNCE": "*140360#",
    "HELLO": "*100373910455#",
    "OFFER aiwerk.ch": "*110348215204660901092305181141030863#",
    "OFFER fogaszat-muster.ch": "*110348215204661806150701192601204013211920051841#",
    "DOMAIN 1 .ch": "*13141030866#",
    "ACK": "*1262#",
    "NAK": "*1941#",
    "ABORT": "*9992#",
}


def test_builders_match_spec():
    assert announce() == SPEC_EXAMPLES["ANNOUNCE"]
    assert hello("739104") == SPEC_EXAMPLES["HELLO"]
    assert offer_group("aiwerk.ch", "4821", "520466") == [SPEC_EXAMPLES["OFFER aiwerk.ch"]]
    assert offer_group("fogaszat-muster.ch", "4821", "520466") == [
        SPEC_EXAMPLES["OFFER fogaszat-muster.ch"], SPEC_EXAMPLES["DOMAIN 1 .ch"]]
    assert (ack(), nak(), abort()) == (SPEC_EXAMPLES["ACK"], SPEC_EXAMPLES["NAK"], SPEC_EXAMPLES["ABORT"])


@pytest.mark.parametrize("f", SPEC_EXAMPLES.values())
def test_examples_parse(f):
    parse(f)
    assert len(f) - 1 <= 50


def test_roundtrip_long_domain():
    dom = "a" * 20 + "-" + "b" * 20 + "." + "c" * 17   # 59 characters
    group = offer_group(dom, "0001", "123456")
    assert len(group) == 3
    frames = [parse(f) for f in group]
    assert assemble_domain(frames[0], frames[1:]) == dom


@pytest.mark.parametrize("bad", [
    "*140361#",          # wrong check digits
    "*1403600#",         # extra digit
    "*14036#",           # missing digit
    "140360#",           # no start symbol
    "*14A360#",          # A-D not allowed
])
def test_rejects(bad):
    with pytest.raises(FrameError):
        parse(bad)


def test_missing_domain_frame_detected():
    o, _ = (parse(f) for f in offer_group("fogaszat-muster.ch", "4821", "520466"))
    with pytest.raises(FrameError):
        assemble_domain(o, [])

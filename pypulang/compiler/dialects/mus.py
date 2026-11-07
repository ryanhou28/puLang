"""
The `mus` dialect: attributes every other dialect shares.

Time is an exact rational number of quarter notes, never a float. A triplet is
1/3 and stays 1/3 until the `daw` lowering has to round it to ticks.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from xdsl.dialects.builtin import (
    ArrayAttr,
    BoolAttr,
    DictionaryAttr,
    FloatAttr,
    IntAttr,
    IntegerAttr,
    StringAttr,
    f64,
    i64,
)
from xdsl.ir import Attribute, Data, Dialect
from xdsl.irdl import irdl_attr_definition
from xdsl.parser import AttrParser
from xdsl.printer import Printer

from pypulang.harmony import format_roman, parse_roman
from pypulang.ir.intent import Chord, Key, TimeSignature


def format_rational(value: Fraction) -> str:
    return (
        str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    )


def print_rational(printer: Printer, value: Fraction) -> None:
    printer.print_string(format_rational(value))


def parse_rational(parser: AttrParser) -> Fraction:
    numerator = parser.parse_integer(allow_boolean=False, allow_negative=True)
    denominator = 1
    if parser.parse_optional_characters("/"):
        denominator = parser.parse_integer(allow_boolean=False, allow_negative=False)
    return Fraction(numerator, denominator)


@irdl_attr_definition
class RationalAttr(Data[Fraction]):
    """An exact fraction, usually a time in quarter notes."""

    name = "mus.r"

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> Fraction:
        with parser.in_angle_brackets():
            return parse_rational(parser)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            print_rational(printer, self.data)


@irdl_attr_definition
class KeyAttr(Data[Key]):
    """A key, written `#mus.key<"G major">`."""

    name = "mus.key"

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> Key:
        with parser.in_angle_brackets():
            return Key.parse(parser.parse_str_literal())

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            printer.print_string_literal(f"{self.data.root} {self.data.mode}")


@irdl_attr_definition
class MeterAttr(Data[TimeSignature]):
    """A time signature, written `#mus.meter<7/8>`."""

    name = "mus.meter"

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> TimeSignature:
        with parser.in_angle_brackets():
            numerator = parser.parse_integer(allow_boolean=False, allow_negative=False)
            parser.parse_characters("/")
            denominator = parser.parse_integer(allow_boolean=False, allow_negative=False)
        return TimeSignature(numerator, denominator)

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            printer.print_string(f"{self.data.numerator}/{self.data.denominator}")


@irdl_attr_definition
class ChordAttr(Data[Chord]):
    """A roman-numeral chord, written `#mus.chord<"V(7,b9)">`."""

    name = "mus.chord"

    @classmethod
    def parse_parameter(cls, parser: AttrParser) -> Chord:
        with parser.in_angle_brackets():
            return parse_roman(parser.parse_str_literal())

    def print_parameter(self, printer: Printer) -> None:
        with printer.in_angle_brackets():
            printer.print_string_literal(format_roman(self.data))


Mus = Dialect("mus", [], [RationalAttr, KeyAttr, MeterAttr, ChordAttr])


def to_attr(value: Any) -> Attribute:
    """Turn a plain Python parameter value into an attribute."""
    if isinstance(value, Attribute):
        return value
    if isinstance(value, bool):
        return BoolAttr.from_bool(value)
    if isinstance(value, int):
        return IntegerAttr(value, i64)
    if isinstance(value, Fraction):
        return RationalAttr(value)
    if isinstance(value, float):
        # Binary fractions such as 1/16 stay exact; 1/3 written as a float comes back as 1/3.
        return RationalAttr(Fraction(value).limit_denominator(3840))
    if isinstance(value, str):
        return StringAttr(value)
    if isinstance(value, (list, tuple)):
        return ArrayAttr([to_attr(v) for v in value])
    if isinstance(value, dict):
        return DictionaryAttr({str(k): to_attr(v) for k, v in value.items()})
    if value is None:
        return StringAttr("")
    raise TypeError(f"Cannot store {type(value).__name__} in the IR: {value!r}")


def from_attr(attr: Attribute) -> Any:
    """The inverse of `to_attr`."""
    if isinstance(attr, IntegerAttr):
        if attr.type.bitwidth == 1 if hasattr(attr.type, "bitwidth") else False:
            return bool(attr.value.data)
        return attr.value.data
    if isinstance(attr, IntAttr):
        return attr.data
    if isinstance(attr, FloatAttr):
        return attr.value.data
    if isinstance(attr, RationalAttr):
        return attr.data
    if isinstance(attr, StringAttr):
        return attr.data
    if isinstance(attr, ArrayAttr):
        return [from_attr(a) for a in attr.data]
    if isinstance(attr, DictionaryAttr):
        return {k: from_attr(v) for k, v in attr.data.items()}
    return attr


def float_attr(value: float) -> FloatAttr:
    return FloatAttr(float(value), f64)

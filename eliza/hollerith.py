"""IBM 7094 Hollerith (BCD) encoding and the SLIP HASH function.

ELIZA chooses the MEMORY transformation with ``HASH.(BOT.(INPUT),2)``:
the 2-bit hash of the last SLIP cell of the input sentence. A SLIP cell
holds six 6-bit BCD characters, left-justified and space padded; a longer
word continues in the next cell. To reproduce the original choices we
must encode the last cell exactly as the 7094 did.

References: Anthony Hay, "The HASH algorithm used by ELIZA"
(github.com/anthay/ELIZA, doc/Eliza_part_3.md) and the FAP source of
HASH in rupertl/eliza-ctss (eliza/src/SLIP/SLIP-fap/hash.fap).
"""

from __future__ import annotations

# BCD code -> character, from Sherman (1963) p. 62, with code 14 (octal)
# being a prime (single quote), per the 1964 University of Michigan
# Executive System manual. None marks an unused code.
_BCD_TABLE = (
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", None, "=", "'", None, None, None,
    "+", "A", "B", "C", "D", "E", "F", "G", "H", "I", None, ".", ")", None, None, None,
    "-", "J", "K", "L", "M", "N", "O", "P", "Q", "R", None, "$", "*", None, None, None,
    " ", "/", "S", "T", "U", "V", "W", "X", "Y", "Z", None, ",", "(", None, None, None,
)

HOLLERITH = {ch: code for code, ch in enumerate(_BCD_TABLE) if ch is not None}

# Byte -> 6-bit code. Bytes outside the Hollerith set cannot occur in an
# original conversation, so (as eliza.cpp does) their low six bits are
# used: any stable value will do.
_BYTE_TO_BCD = [HOLLERITH.get(chr(b), b & 0o77) if b < 0x80 else b & 0o77 for b in range(256)]

CELL_CHARS = 6


def last_chunk_as_bcd(word: str) -> int:
    """Return the 36-bit BCD datum of the last SLIP cell holding ``word``.

    The word is measured in UTF-8 bytes, exactly like eliza.cpp, so that
    scripts in other languages pick the same MEMORY rules in both programs.
    e.g. "HERE" -> 0o302551256060, "INVENTED" -> "ED    " -> 0o252460606060
    """
    data = word.encode("utf-8")
    start = ((len(data) - 1) // CELL_CHARS) * CELL_CHARS if data else 0
    chunk = data[start:].ljust(CELL_CHARS, b" ")
    datum = 0
    for b in chunk:
        datum = (datum << 6) | _BYTE_TO_BCD[b]
    return datum


def slip_hash(datum: int, n: int) -> int:
    """Return the n-bit SLIP HASH of a 36-bit datum (von Neumann mid-square).

    The 7094 is sign-magnitude: only the low 35 bits are squared. The
    70-bit product is shifted so that its middle n bits are returned.
    """
    if not 0 <= n <= 15:
        raise ValueError("n must be in 0..15")
    d = datum & 0o377777777777  # 35-bit magnitude
    return ((d * d) >> (35 - n // 2)) & ((1 << n) - 1)

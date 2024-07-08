#
# QR Code generator library (Python)
#
# Copyright (c) Project Nayuki. (MIT License)
# https://www.nayuki.io/page/qr-code-generator-library
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
# - The Software is provided "as is", without warranty of any kind, express or
#   implied, including but not limited to the warranties of merchantability,
#   fitness for a particular purpose and noninfringement. In no event shall the
#   authors or copyright holders be liable for any claim, damages or other
#   liability, whether in an action of contract, tort or otherwise, arising from,
#   out of or in connection with the Software or the use or other dealings in the
#   Software.
#

from __future__ import annotations
import collections
import itertools
import re
from collections.abc import Sequence
from typing import Callable, Dict, List, Optional, Tuple, Union


class QrCode:
    @staticmethod
    def encode_text(text: str, ecl: QrCode.Ecc) -> QrCode:
        segs: List[QrSegment] = QrSegment.make_segments(text)
        return QrCode.encode_segments(segs, ecl)

    @staticmethod
    def encode_binary(
            data: Union[bytes, Sequence[int]],
            ecl: QrCode.Ecc) -> QrCode:
        return QrCode.encode_segments([QrSegment.make_bytes(data)], ecl)

    @staticmethod
    def encode_segments(
            segs: Sequence[QrSegment],
            ecl: QrCode.Ecc,
            minversion: int = 1,
            maxversion: int = 40,
            mask: int = -1,
            boostecl: bool = True) -> QrCode:
        if not (QrCode.MIN_VERSION <= minversion <= maxversion <=
                QrCode.MAX_VERSION) or not (-1 <= mask <= 7):
            raise ValueError("Invalid value")

        # Find the minimal version number to use
        for version in range(minversion, maxversion + 1):
            datacapacitybits: int = QrCode._get_num_data_codewords(
                version, ecl) * 8  # Number of data bits available
            datausedbits: Optional[int] = QrSegment.get_total_bits(
                segs, version)
            if (datausedbits is not None) and (
                    datausedbits <= datacapacitybits):
                break  # This version number is found to be suitable
            if version >= maxversion:  # All versions in the range could not fit the given data
                msg: str = "Segment too long"
                if datausedbits is not None:
                    msg = f"Data length = {datausedbits} bits, Max capacity = {
                        datacapacitybits} bits"
                raise DataTooLongError(msg)
        assert datausedbits is not None

        bb = _BitBuffer()
        for seg in segs:
            bb.append_bits(seg.get_mode().get_mode_bits(), 4)
            bb.append_bits(seg.get_num_chars(),
                           seg.get_mode().num_char_count_bits(version))
            bb.extend(seg._bitdata)
        assert len(bb) == datausedbits

        # Add terminator and pad up to a byte if applicable
        datacapacitybits = QrCode._get_num_data_codewords(version, ecl) * 8
        assert len(bb) <= datacapacitybits
        bb.append_bits(0, min(4, datacapacitybits - len(bb)))
        # Note: Python's modulo on negative numbers behaves better than C
        # family languages
        bb.append_bits(0, -len(bb) % 8)
        assert len(bb) % 8 == 0

        # Pad with alternating bytes until data capacity is reached
        for padbyte in itertools.cycle((0xEC, 0x11)):
            if len(bb) >= datacapacitybits:
                break
            bb.append_bits(padbyte, 8)

        # Pack bits into bytes in big endian
        datacodewords = bytearray([0] * (len(bb) // 8))
        for (i, bit) in enumerate(bb):
            datacodewords[i >> 3] |= bit << (7 - (i & 7))

        # Create the QR Code object
        return QrCode(version, ecl, datacodewords, mask)

    _version: int

    _errcorlvl: QrCode.Ecc

    _modules: List[List[bool]]

    _isfunction: List[List[bool]]

    def __init__(
            self, version: int, errcorlvl: QrCode.Ecc,
            datacodewords: Union[bytes, Sequence[int]],
            msk: int) -> None:
        # Check scalar arguments and set fields
        if not (QrCode.MIN_VERSION <= version <= QrCode.MAX_VERSION):
            raise ValueError("Version value out of range")
        if not (-1 <= msk <= 7):
            raise ValueError("Mask value out of range")
        self._version = version
        self._errcorlvl = errcorlvl
        self._add_ecc_and_interleave(bytearray(datacodewords))

    def get_version(self) -> int:
        """Returns this QR Code's version number, in the range [1, 40]."""
        return self._version

    def get_error_correction_level(self) -> QrCode.Ecc:
        """Returns this QR Code's error correction level."""
        return self._errcorlvl

    def get_error_correcting_codeword_count(self) -> int:
        """Returns the number of 8-bit data (i.e. not error correction) codewords contained in this QR Code."""
        return QrCode._ECC_CODEWORDS_PER_BLOCK[self._errcorlvl.ordinal][self._version]

    def _add_ecc_and_interleave(self, data: bytearray) -> bytes:
        """Returns a new byte string representing the given data with the appropriate error correction
        codewords appended to it, based on this object's version and error correction level."""
        version: int = self._version
        assert len(data) == QrCode._get_num_data_codewords(
            version, self._errcorlvl)

        # Calculate parameter numbers
        numblocks: int = QrCode._NUM_ERROR_CORRECTION_BLOCKS[self._errcorlvl.ordinal][version]
        blockecclen: int = QrCode._ECC_CODEWORDS_PER_BLOCK[self._errcorlvl.ordinal][version]
        rawcodewords: int = QrCode._get_num_raw_data_modules(version) // 8
        numshortblocks: int = numblocks - rawcodewords % numblocks
        shortblocklen: int = rawcodewords // numblocks

        # Split data into blocks and append ECC to each block
        blocks: List[bytes] = []
        rsdiv: bytes = QrCode._reed_solomon_compute_divisor(blockecclen)
        k: int = 0
        for i in range(numblocks):
            dat: bytearray = data[k: k +
                                  shortblocklen -
                                  blockecclen +
                                  (0 if i < numshortblocks else 1)]
            k += len(dat)
            ecc: bytes = QrCode._reed_solomon_compute_remainder(dat, rsdiv)
            blocks.append(dat + ecc)
        assert k == len(data)
        self.blocks = blocks.copy()

    @staticmethod
    def _get_num_raw_data_modules(ver: int) -> int:
        """Returns the number of data bits that can be stored in a QR Code of the given version number, after
        all function modules are excluded. This includes remainder bits, so it might not be a multiple of 8.
        The result is in the range [208, 29648]. This could be implemented as a 40-entry lookup table."""
        if not (QrCode.MIN_VERSION <= ver <= QrCode.MAX_VERSION):
            raise ValueError("Version number out of range")
        result: int = (16 * ver + 128) * ver + 64
        if ver >= 2:
            numalign: int = ver // 7 + 2
            result -= (25 * numalign - 10) * numalign - 55
            if ver >= 7:
                result -= 36
        assert 208 <= result <= 29648
        return result

    @staticmethod
    def _get_num_data_codewords(ver: int, ecl: QrCode.Ecc) -> int:
        """Returns the number of 8-bit data (i.e. not error correction) codewords contained in any
        QR Code of the given version number and error correction level, with remainder bits discarded.
        This stateless pure function could be implemented as a (40*4)-cell lookup table."""
        return QrCode._get_num_raw_data_modules(ver) // 8 \
            - QrCode._ECC_CODEWORDS_PER_BLOCK[ecl.ordinal][ver] \
            * QrCode._NUM_ERROR_CORRECTION_BLOCKS[ecl.ordinal][ver]

    @staticmethod
    def _reed_solomon_compute_divisor(degree: int) -> bytes:
        """Returns a Reed-Solomon ECC generator polynomial for the given degree. This could be
        implemented as a lookup table over all possible parameter values, instead of as an algorithm."""
        if not (1 <= degree <= 255):
            raise ValueError("Degree out of range")
        # Polynomial coefficients are stored from highest to lowest power, excluding the leading term which is always 1.
        # For example the polynomial x^3 + 255x^2 + 8x + 93 is stored as the
        # uint8 array [255, 8, 93].
        # Start off with the monomial x^0
        result = bytearray([0] * (degree - 1) + [1])

        # Compute the product polynomial (x - r^0) * (x - r^1) * (x - r^2) * ... * (x - r^{degree-1}),
        # and drop the highest monomial term which is always 1x^degree.
        # Note that r = 0x02, which is a generator element of this field
        # GF(2^8/0x11D).
        root: int = 1
        for _ in range(degree):  # Unused variable i
            # Multiply the current product by (x - r^i)
            for j in range(degree):
                result[j] = QrCode._reed_solomon_multiply(result[j], root)
                if j + 1 < degree:
                    result[j] ^= result[j + 1]
            root = QrCode._reed_solomon_multiply(root, 0x02)
        return result

    @staticmethod
    def _reed_solomon_compute_remainder(data: bytes, divisor: bytes) -> bytes:
        """Returns the Reed-Solomon error correction codeword for the given data and divisor polynomials."""
        result = bytearray([0] * len(divisor))
        for b in data:  # Polynomial division
            factor: int = b ^ result.pop(0)
            result.append(0)
            for (i, coef) in enumerate(divisor):
                result[i] ^= QrCode._reed_solomon_multiply(coef, factor)
        return result

    @staticmethod
    def _reed_solomon_multiply(x: int, y: int) -> int:
        """Returns the product of the two given field elements modulo GF(2^8/0x11D). The arguments and result
        are unsigned 8-bit integers. This could be implemented as a lookup table of 256*256 entries of uint8."""
        if (x >> 8 != 0) or (y >> 8 != 0):
            raise ValueError("Byte out of range")
        # Russian peasant multiplication
        z: int = 0
        for i in reversed(range(8)):
            z = (z << 1) ^ ((z >> 7) * 0x11D)
            z ^= ((y >> i) & 1) * x
        assert z >> 8 == 0
        return z

    def _finder_penalty_count_patterns(
            self, runhistory: collections.deque) -> int:
        """Can only be called immediately after a light run is added, and
        returns either 0, 1, or 2. A helper function for _get_penalty_score()."""
        n: int = runhistory[1]
        assert n <= self._size * 3
        core: bool = n > 0 and (
            runhistory[2] == runhistory[4] == runhistory[5] == n) and runhistory[3] == n * 3
        return (1 if (core and runhistory[0] >= n * 4 and runhistory[6] >= n) else 0) \
            + (1 if (core and runhistory[6] >= n * 4 and runhistory[0] >= n) else 0)

    def _finder_penalty_terminate_and_count(
            self, currentruncolor: bool, currentrunlength: int,
            runhistory: collections.deque) -> int:
        """Must be called at the end of a line (row or column) of modules. A helper function for _get_penalty_score()."""
        if currentruncolor:  # Terminate dark run
            self._finder_penalty_add_history(currentrunlength, runhistory)
            currentrunlength = 0
        currentrunlength += self._size  # Add light border to final run
        self._finder_penalty_add_history(currentrunlength, runhistory)
        return self._finder_penalty_count_patterns(runhistory)

    def _finder_penalty_add_history(
            self,
            currentrunlength: int,
            runhistory: collections.deque) -> None:
        if runhistory[0] == 0:
            currentrunlength += self._size  # Add light border to initial run
        runhistory.appendleft(currentrunlength)

    # ---- Constants and tables ----

    # The minimum version number supported in the QR Code Model 2 standard
    MIN_VERSION: int = 1
    # The maximum version number supported in the QR Code Model 2 standard
    MAX_VERSION: int = 40

    # For use in _get_penalty_score(), when evaluating which mask is best.
    _PENALTY_N1: int = 3
    _PENALTY_N2: int = 3
    _PENALTY_N3: int = 40
    _PENALTY_N4: int = 10

    _ECC_CODEWORDS_PER_BLOCK: Sequence[Sequence[int]] = (
        # Version: (note that index 0 is for padding, and is set to an illegal value)
        # 0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40    Error correction level
        (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # Low
        (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),  # Medium
        (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),  # Quartile
        (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30))  # High

    _NUM_ERROR_CORRECTION_BLOCKS: Sequence[Sequence[int]] = (
        # Version: (note that index 0 is for padding, and is set to an illegal value)
        # 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40    Error correction level
        (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),  # Low
        (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),  # Medium
        (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),  # Quartile
        (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81))  # High

    # ---- Public helper enumeration ----

    class Ecc:
        ordinal: int  # (Public) In the range 0 to 3 (unsigned 2-bit integer)
        # (Package-private) In the range 0 to 3 (unsigned 2-bit integer)
        formatbits: int

        """The error correction level in a QR Code symbol. Immutable."""
        # Private constructor

        def __init__(self, i: int, fb: int) -> None:
            self.ordinal = i
            self.formatbits = fb

        # Placeholders
        LOW: QrCode.Ecc
        MEDIUM: QrCode.Ecc
        QUARTILE: QrCode.Ecc
        HIGH: QrCode.Ecc

    # Public constants. Create them outside the class.
    # The QR Code can tolerate about  7% erroneous codewords
    Ecc.LOW = Ecc(0, 1)
    # The QR Code can tolerate about 15% erroneous codewords
    Ecc.MEDIUM = Ecc(1, 0)
    # The QR Code can tolerate about 25% erroneous codewords
    Ecc.QUARTILE = Ecc(2, 3)
    # The QR Code can tolerate about 30% erroneous codewords
    Ecc.HIGH = Ecc(3, 2)


# ---- Data segment class ----

class QrSegment:
    """A segment of character/binary/control data in a QR Code symbol.
    Instances of this class are immutable.
    The mid-level way to create a segment is to take the payload data
    and call a static factory function such as QrSegment.make_numeric().
    The low-level way to create a segment is to custom-make the bit buffer
    and call the QrSegment() constructor with appropriate values.
    This segment class imposes no length restrictions, but QR Codes have restrictions.
    Even in the most favorable conditions, a QR Code can only hold 7089 characters of data.
    Any segment longer than this is meaningless for the purpose of generating QR Codes."""

    # ---- Static factory functions (mid level) ----

    @staticmethod
    def make_bytes(data: Union[bytes, Sequence[int]]) -> QrSegment:
        """Returns a segment representing the given binary data encoded in byte mode.
        All input byte lists are acceptable. Any text string can be converted to
        UTF-8 bytes (s.encode("UTF-8")) and encoded as a byte mode segment."""
        bb = _BitBuffer()
        for b in data:
            bb.append_bits(b, 8)
        return QrSegment(QrSegment.Mode.BYTE, len(data), bb)

    @staticmethod
    def make_numeric(digits: str) -> QrSegment:
        """Returns a segment representing the given string of decimal digits encoded in numeric mode."""
        if not QrSegment.is_numeric(digits):
            raise ValueError("String contains non-numeric characters")
        bb = _BitBuffer()
        i: int = 0
        while i < len(digits):  # Consume up to 3 digits per iteration
            n: int = min(len(digits) - i, 3)
            bb.append_bits(int(digits[i: i + n]), n * 3 + 1)
            i += n
        return QrSegment(QrSegment.Mode.NUMERIC, len(digits), bb)

    @staticmethod
    def make_alphanumeric(text: str) -> QrSegment:
        """Returns a segment representing the given text string encoded in alphanumeric mode.
        The characters allowed are: 0 to 9, A to Z (uppercase only), space,
        dollar, percent, asterisk, plus, hyphen, period, slash, colon."""
        if not QrSegment.is_alphanumeric(text):
            raise ValueError(
                "String contains unencodable characters in alphanumeric mode")
        bb = _BitBuffer()
        for i in range(0, len(text) - 1, 2):  # Process groups of 2
            temp: int = QrSegment._ALPHANUMERIC_ENCODING_TABLE[text[i]] * 45
            temp += QrSegment._ALPHANUMERIC_ENCODING_TABLE[text[i + 1]]
            bb.append_bits(temp, 11)
        if len(text) % 2 > 0:  # 1 character remaining
            bb.append_bits(QrSegment._ALPHANUMERIC_ENCODING_TABLE[text[-1]], 6)
        return QrSegment(QrSegment.Mode.ALPHANUMERIC, len(text), bb)

    @staticmethod
    def make_segments(text: str) -> List[QrSegment]:
        """Returns a new mutable list of zero or more segments to represent the given Unicode text string.
        The result may use various segment modes and switch modes to optimize the length of the bit stream."""

        # Select the most efficient segment encoding automatically
        if text == "":
            return []
        elif QrSegment.is_numeric(text):
            return [QrSegment.make_numeric(text)]
        elif QrSegment.is_alphanumeric(text):
            return [QrSegment.make_alphanumeric(text)]
        else:
            return [QrSegment.make_bytes(text.encode("UTF-8"))]

    @staticmethod
    def make_eci(assignval: int) -> QrSegment:
        """Returns a segment representing an Extended Channel Interpretation
        (ECI) designator with the given assignment value."""
        bb = _BitBuffer()
        if assignval < 0:
            raise ValueError("ECI assignment value out of range")
        elif assignval < (1 << 7):
            bb.append_bits(assignval, 8)
        elif assignval < (1 << 14):
            bb.append_bits(0b10, 2)
            bb.append_bits(assignval, 14)
        elif assignval < 1000000:
            bb.append_bits(0b110, 3)
            bb.append_bits(assignval, 21)
        else:
            raise ValueError("ECI assignment value out of range")
        return QrSegment(QrSegment.Mode.ECI, 0, bb)

    # Tests whether the given string can be encoded as a segment in numeric mode.
    # A string is encodable iff each character is in the range 0 to 9.

    @staticmethod
    def is_numeric(text: str) -> bool:
        return QrSegment._NUMERIC_REGEX.fullmatch(text) is not None

    # Tests whether the given string can be encoded as a segment in alphanumeric mode.
    # A string is encodable iff each character is in the following set: 0 to 9, A to Z
    # (uppercase only), space, dollar, percent, asterisk, plus, hyphen, period, slash, colon.

    @staticmethod
    def is_alphanumeric(text: str) -> bool:
        return QrSegment._ALPHANUMERIC_REGEX.fullmatch(text) is not None

    # ---- Private fields ----

    # The mode indicator of this segment. Accessed through get_mode().
    _mode: QrSegment.Mode

    # The length of this segment's unencoded data. Measured in characters for
    # numeric/alphanumeric/kanji mode, bytes for byte mode, and 0 for ECI mode.
    # Always zero or positive. Not the same as the data's bit length.
    # Accessed through get_num_chars().
    _numchars: int

    # The data bits of this segment. Accessed through get_data().
    _bitdata: List[int]

    # ---- Constructor (low level) ----

    def __init__(
            self,
            mode: QrSegment.Mode,
            numch: int,
            bitdata: Sequence[int]) -> None:
        """Creates a new QR Code segment with the given attributes and data.
        The character count (numch) must agree with the mode and the bit buffer length,
        but the constraint isn't checked. The given bit buffer is cloned and stored."""
        if numch < 0:
            raise ValueError()
        self._mode = mode
        self._numchars = numch
        self._bitdata = list(bitdata)  # Make defensive copy

    # ---- Accessor methods ----

    def get_mode(self) -> QrSegment.Mode:
        """Returns the mode field of this segment."""
        return self._mode

    def get_num_chars(self) -> int:
        """Returns the character count field of this segment."""
        return self._numchars

    def get_data(self) -> List[int]:
        """Returns a new copy of the data bits of this segment."""
        return list(self._bitdata)  # Make defensive copy

    # Package-private function

    @staticmethod
    def get_total_bits(
            segs: Sequence[QrSegment],
            version: int) -> Optional[int]:
        """Calculates the number of bits needed to encode the given segments at
        the given version. Returns a non-negative number if successful. Otherwise
        returns None if a segment has too many characters to fit its length field."""
        result = 0
        for seg in segs:
            ccbits: int = seg.get_mode().num_char_count_bits(version)
            if seg.get_num_chars() >= (1 << ccbits):
                return None  # The segment's length doesn't fit the field's bit width
            result += 4 + ccbits + len(seg._bitdata)
        return result

    # ---- Constants ----

    # Describes precisely all strings that are encodable in numeric mode.
    _NUMERIC_REGEX: re.Pattern = re.compile(r"[0-9]*")

    # Describes precisely all strings that are encodable in alphanumeric mode.
    _ALPHANUMERIC_REGEX: re.Pattern = re.compile(r"[A-Z0-9 $%*+./:-]*")

    # Dictionary of "0"->0, "A"->10, "$"->37, etc.
    _ALPHANUMERIC_ENCODING_TABLE: Dict[str, int] = {ch: i for (
        i, ch) in enumerate("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:")}

    # ---- Public helper enumeration ----

    class Mode:
        """Describes how a segment's data bits are interpreted. Immutable."""

        # The mode indicator bits, which is a uint4 value (range 0 to 15)
        _modebits: int
        # Number of character count bits for three different version ranges
        _charcounts: Tuple[int, int, int]

        # Private constructor
        def __init__(self, modebits: int, charcounts: Tuple[int, int, int]):
            self._modebits = modebits
            self._charcounts = charcounts

        # Package-private method
        def get_mode_bits(self) -> int:
            """Returns an unsigned 4-bit integer value (range 0 to 15) representing the mode indicator bits for this mode object."""
            return self._modebits

        # Package-private method
        def num_char_count_bits(self, ver: int) -> int:
            """Returns the bit width of the character count field for a segment in this mode
            in a QR Code at the given version number. The result is in the range [0, 16]."""
            return self._charcounts[(ver + 7) // 17]

        # Placeholders
        NUMERIC: QrSegment.Mode
        ALPHANUMERIC: QrSegment.Mode
        BYTE: QrSegment.Mode
        KANJI: QrSegment.Mode
        ECI: QrSegment.Mode

    # Public constants. Create them outside the class.
    Mode.NUMERIC = Mode(0x1, (10, 12, 14))
    Mode.ALPHANUMERIC = Mode(0x2, (9, 11, 13))
    Mode.BYTE = Mode(0x4, (8, 16, 16))
    Mode.KANJI = Mode(0x8, (8, 10, 12))
    Mode.ECI = Mode(0x7, (0, 0, 0))


# ---- Private helper class ----

class _BitBuffer(list):
    """An appendable sequence of bits (0s and 1s). Mainly used by QrSegment."""

    def append_bits(self, val: int, n: int) -> None:
        """Appends the given number of low-order bits of the given
        value to this buffer. Requires n >= 0 and 0 <= val < 2^n."""
        if (n < 0) or (val >> n != 0):
            raise ValueError("Value out of range")
        self.extend(((val >> i) & 1) for i in reversed(range(n)))


def _get_bit(x: int, i: int) -> bool:
    """Returns true iff the i'th bit of x is set to 1."""
    return (x >> i) & 1 != 0


class DataTooLongError(ValueError):
    """Raised when the supplied data does not fit any QR Code version. Ways to handle this exception include:
    - Decrease the error correction level if it was greater than Ecc.LOW.
    - If the encode_segments() function was called with a maxversion argument, then increase
      it if it was less than QrCode.MAX_VERSION. (This advice does not apply to the other
      factory functions because they search all versions up to QrCode.MAX_VERSION.)
    - Split the text data into better or optimal segments in order to reduce the number of bits required.
    - Change the text or binary data to be shorter.
    - Change the text to fit the character set of a particular segment mode (e.g. alphanumeric).
    - Propagate the error upward to the caller/user."""
    pass

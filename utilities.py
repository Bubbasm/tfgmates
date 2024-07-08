"""
Posibles funciones utiles:
- compare_changing_bits(text1, text2)
"""


def gen_qr_codes(text: bytes, ecc="L"):
    """
    Generate data codes for the given text
    """
    from qrcodegen import QrCode
    text = list(text)
    if ecc == "L":
        eccQR = QrCode.Ecc.LOW
    elif ecc == "M":
        eccQR = QrCode.Ecc.MEDIUM
    elif ecc == "Q":
        eccQR = QrCode.Ecc.QUARTILE
    elif ecc == "H":
        eccQR = QrCode.Ecc.HIGH
    qr = QrCode.encode_binary(text, eccQR)
    return [bytes(block) for block in qr.blocks], qr


def gen_rs_codes(text, eccCount):
    """
    Generate Reed-Solomon error correction codes for the given text
    """
    from qrcodegen import QrCode
    return bytes(QrCode._reed_solomon_compute_remainder(
        text, QrCode._reed_solomon_compute_divisor(eccCount)))


def byte2bin(input):
    return [format(i, '08b') for i in input]


def bin2byte(input):
    return bytes([int(i, 2) for i in input])


def compare_changing_bits(text1: bytes, text2: bytes):
    """
    Compare two texts and return the number of bits that are different
    """
    ret = []
    text1 = byte2bin(text1)
    text2 = byte2bin(text2)
    for i in range(len(text1)):
        count = 0
        for j in range(len(text1[i])):
            if text1[i][j] != text2[i][j]:
                count += 1
        ret.append(count)
    return ret


def get_changing_bits_count(text1: bytes, text2: bytes, skip=3):
    """
    Get the number of bits that are different between two texts
    """
    a = [i for i in compare_changing_bits(text1, text2)]
    a.sort()
    return sum(a[:-skip])


def get_minimum_byte_change(text1: bytes, index, ecc="L"):
    text1_int, qr = gen_qr_codes(text1,ecc)
    text1_int = text1_int[0]
    skip = (qr.get_error_correcting_codeword_count())//2
    text2 = list(text1)
    minimum = 10000000
    for j in range(256):
        if j == text1[index]:
            continue
        text2[index] = j
        text2_int = gen_qr_codes(bytes(text2),ecc)[0][0]
        aux = get_changing_bits_count(text1_int, text2_int, skip)
        if aux == 0:
            return (-1, -1, -1)
        if aux < minimum:
            minimum = aux
            position = index
            value = j
    return (minimum, position, value)


def get_minimum_byte_change_raw(text1: bytes, index, ecc_codes=7):
    text1_int = text1 + gen_rs_codes(text1, ecc_codes)
    text2 = list(text1)
    minimum = 10000000
    for j in range(256):
        if j == text1[index]:
            continue
        text2[index] = j
        text2_int = bytes(text2) + gen_rs_codes(bytes(text2), ecc_codes)
        aux = get_changing_bits_count(text1_int, text2_int, ecc_codes // 2)
        if aux < minimum:
            minimum = aux
            position = index
            value = j
    return (minimum, position, value)


def _brute_force_helper(text1: bytes, minimum_byte_change_function, ecc_codes):
    minim = []
    for i in range(len(text1)):
        (minimum, position, value) = minimum_byte_change_function(text1, i, ecc_codes)
        if minimum == -1:
            break
        print((minimum, position, value))
        minim.append((minimum, position, value))
    minim.sort()
    for i in minim:
        print("To modify position %2d, from byte %3d to byte %3d ---> %2d bit flips in QR code" %
              (i[1], text1[i[1]], i[2], i[0]))
    return minim


def brute_force_change_text(text1: bytes, ecc="L"):
    """
    Brute force the text to get another text
    with the minimum number of changing bits
    """
    return _brute_force_helper(text1, get_minimum_byte_change, ecc)


def brute_force_change_raw(text1: bytes, ecc_codes=7):
    """
    Brute force the raw bytes to get another codeword
    with the minimum number of changing bits
    """
    return _brute_force_helper(text1, get_minimum_byte_change_raw, ecc_codes)


if __name__ == "__main__":
    text1 = [64, 180, 150, 67, 162, 3, 19, 35, 51, 67, 83, 99, 112,
             196, 144, 22, 34, 115, 74, 89, 202, 212, 234, 197, 39, 150]
    text2 = [64, 180, 150, 67, 162, 3, 19, 35, 51, 67, 83, 99, 96,
             188, 116, 128, 47, 172, 71, 62, 26, 14, 96, 156, 143, 69]

    print(compare_changing_bits(text1, text2))

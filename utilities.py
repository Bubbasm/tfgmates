""" 
Posibles funciones utiles:
- compare_changing_bits(text1, text2)
"""

def gen_qr_codes(text,ecc="L"):
    """
    Generate data codes for the given text
    """
    from qrcodegen import QrCode
    text = bytes2int(text.encode())
    if ecc == "L":
        eccQR = QrCode.Ecc.LOW
    elif ecc == "M":
        eccQR = QrCode.Ecc.MEDIUM
    elif ecc == "Q":
        eccQR = QrCode.Ecc.QUARTILE
    elif ecc == "H":
        eccQR = QrCode.Ecc.HIGH
    qr = QrCode.encode_binary(text, eccQR)
    return bytes(qr.allcodewords)

def gen_rs_codes(text, eccCount):
    """
    Generate Reed-Solomon error correction codes for the given text
    """
    from qrcodegen import QrCode
    # convert text to list of integers
    return QrCode._reed_solomon_compute_remainder(text,QrCode._reed_solomon_compute_divisor(eccCount))

def bytes2int(input):
    return [i for i in input]

def int2bytes(input):
    return bytes([chr(i) for i in input])

def int2bin(input):
    return [format(i,'08b') for i in input]

def bin2int(input):
    return [int(i,2) for i in input]

def compare_changing_bits(text1, text2):
    """
    Compare two texts and return the number of bits that are different
    """
    ret = []
    text1 = int2bin(text1)
    text2 = int2bin(text2)
    for i in range(len(text1)):
        count = 0
        for j in range(len(text1[i])):
            if text1[i][j] != text2[i][j]:
                count += 1
        ret.append(count)
    return ret

def get_changing_bits_count_v1(text1, text2):
    """
    Get the number of bits that are different between two texts
    """
    a=[i for i in compare_changing_bits(text1, text2) if i>0]
    a.sort()
    return sum(a[:1+(len(a)+2)//2])

def brute_force_change_text_v1(text1):
    """
    Brute force the text to get another text with the minimum number of changing bits
    """
    text1_aux = gen_qr_codes(text1)
    minim = []
    i=8
    text2 = list(text1)
    minimum = 10000000
    for j in range(255):
        if j == ord(text1[i]):
            continue
        text2[i] = chr(j)
        text2_aux = gen_qr_codes("".join(text2))
        aux = get_changing_bits_count_v1(text1_aux, text2_aux)
        if aux < minimum:
            minimum = aux
            position = i
            value = j

    minim.append((minimum, position, value))
    print(minim)


if __name__ == "__main__":
    text1 = [64,180,150,67,162,3,19,35,51,67,83,99,112,196,144,22,34,115,74,89,202,212,234,197,39,150]
    text2 = [64,180,150,67,162,3,19,35,51,67,83,99,96,188,116,128,47,172,71,62,26,14,96,156,143,69]

    print(compare_changing_bits(text1, text2))
from utilities import *

byte_count = 1273
ecc = "H"

print("Brute forcing text of length %d with error correcting level %s" % (byte_count, ecc))

bru = brute_force_change_text(byte_count*b"\x00",ecc)

b = bru[0][0]

for a in bru:
    if a[0] != b:
        break
    sett = set()
    for i in range(256):
        x = get_minimum_byte_change(bytes(byte_count*[i]),a[1],ecc)
        sett.add((x[2]^i, x[0]))
    print(a, sett)
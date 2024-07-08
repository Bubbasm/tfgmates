if __name__ == "__main__":
    import qrcode
    # create qr in binary format 
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,

    )
    alt_data = 3*b"\x00"+b"\x26"+(32-4)*b"\x00"
    qr.add_data(alt_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("qr.png")

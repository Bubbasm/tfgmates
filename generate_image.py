if __name__ == "__main__":
    import qrcode
    # create qr in binary format 
    qr = qrcode.QRCode(
        version=3,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,

    )
    qr.add_data(16*b"\x00")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("qr.png")

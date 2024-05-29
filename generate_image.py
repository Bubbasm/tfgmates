if __name__ == "__main__":
    import qrcode
    # create qr in binary format 
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,

    )
    qr.add_data("Id: bhavuksikka")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("qr.png")

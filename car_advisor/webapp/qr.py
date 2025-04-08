import qrcode

def generate_instant_qr(url: str):
    try:
        if not url.startswith(('http://', 'https://')):
            raise ValueError("URL должен начинаться с http:// или https://")

        qr = qrcode.QRCode(
            version=3,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=15,
            border=2
        )

        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        img.show()

    except Exception as e:
        print(f" Ошибка генерации: {str(e)}")

if __name__ == "__main__":
    generate_instant_qr("https://eu.iit.csu.ru/my/?courses")

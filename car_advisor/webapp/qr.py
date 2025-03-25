import qrcode

def generate_instant_qr(url: str):
    """
    Генерирует и мгновенно отображает QR-код без сохранения файла
    :param url: Ссылка для кодирования
    """
    try:
        # Валидация URL
        if not url.startswith(('http://', 'https://')):
            raise ValueError("URL должен начинаться с http:// или https://")

        # Создание объекта QR-кода
        qr = qrcode.QRCode(
            version=3,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=15,
            border=2
        )

        # Добавление данных и генерация
        qr.add_data(url)
        qr.make(fit=True)

        # Создание изображения с кастомизацией
        img = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        # Мгновенное отображение
        img.show()

    except Exception as e:
        print(f"🚨 Ошибка генерации: {str(e)}")


# Пример использования
if __name__ == "__main__":
    # ▼▼▼ Введите свою ссылку ▼▼▼
    generate_instant_qr("https://eu.iit.csu.ru/my/?courses")

from pathlib import Path

import fitz


def make_pdf(path: Path, pages: list[str]) -> Path:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text(
                (72, 72),
                text,
                fontname="korea",
                fontsize=11,
            )
    document.save(path)
    document.close()
    return path


def make_encrypted_pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "protected")
    document.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()
    return path

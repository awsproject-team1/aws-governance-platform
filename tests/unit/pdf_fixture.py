"""Unit test용 작은 PDF를 코드로 만든다. Binary fixture는 commit하지 않는다."""

from __future__ import annotations

import io

from pypdf import PdfWriter


def golden_pdf() -> bytes:
    """서로 다른 heading 크기와 두 페이지를 가진 텍스트 PDF."""
    page_one = _text_stream(
        [
            ("F2", 20, 72, 720, "Access Control Policy"),
            ("F1", 11, 72, 690, "This policy defines the minimum access requirements."),
            ("F2", 15, 72, 650, "Account Management"),
            ("F1", 11, 72, 625, "Shared accounts are prohibited."),
            ("F1", 11, 72, 611, "Exceptions require a recorded approval."),
        ]
    )
    page_two = _text_stream(
        [
            ("F2", 15, 72, 720, "Periodic Review"),
            ("F1", 11, 72, 695, "Access rights are reviewed every quarter."),
        ]
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 7 0 R >>"
        ),
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 8 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        _stream_object(page_one),
        _stream_object(page_two),
    ]
    return _pdf(objects)


def object_stream_pdf() -> bytes:
    """Font 객체를 실제 ObjStm과 xref stream 안에 넣은 PDF 1.5 문서."""
    content = _text_stream([("F1", 11, 72, 720, "Text inside an object-stream PDF.")])
    object_stream_header = b"5 0 "
    compressed_font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    object_stream_payload = object_stream_header + compressed_font
    object_stream = (
        (
            f"<< /Type /ObjStm /N 1 /First {len(object_stream_header)} "
            f"/Length {len(object_stream_payload)} >>\nstream\n"
        ).encode()
        + object_stream_payload
        + b"\nendstream"
    )

    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        4: _stream_object(content),
        6: object_stream,
    }
    payload = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for number, item in objects.items():
        offsets[number] = len(payload)
        payload.extend(f"{number} 0 obj\n".encode())
        payload.extend(item)
        payload.extend(b"\nendobj\n")

    xref_offset = len(payload)
    entries = [
        _xref_entry(0, 0, 65535),
        _xref_entry(1, offsets[1], 0),
        _xref_entry(1, offsets[2], 0),
        _xref_entry(1, offsets[3], 0),
        _xref_entry(1, offsets[4], 0),
        _xref_entry(2, 6, 0),
        _xref_entry(1, offsets[6], 0),
        _xref_entry(1, xref_offset, 0),
    ]
    xref_stream = b"".join(entries)
    payload.extend(b"7 0 obj\n")
    payload.extend(
        (
            f"<< /Type /XRef /Size 8 /Root 1 0 R /W [1 4 2] "
            f"/Index [0 8] /Length {len(xref_stream)} >>\nstream\n"
        ).encode()
    )
    payload.extend(xref_stream)
    payload.extend(b"\nendstream\nendobj\n")
    payload.extend(f"startxref\n{xref_offset}\n%%EOF".encode())
    return bytes(payload)


def scanned_pdf() -> bytes:
    """텍스트 계층 없이 1x1 이미지 XObject만 가진 PDF."""
    image = (
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
        b"stream\n\x00\nendstream"
    )
    content = b"q 100 0 0 100 72 620 cm /Im1 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /XObject << /Im1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        image,
        _stream_object(content),
    ]
    return _pdf(objects)


def mixed_pdf() -> bytes:
    """첫 페이지는 텍스트, 둘째 페이지는 이미지만 가진 PDF."""
    content = _text_stream(
        [
            ("F2", 20, 72, 720, "Mixed Policy"),
            ("F1", 11, 72, 690, "The first page has a text layer."),
        ]
    )
    image = (
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length 1 >>\n"
        b"stream\n\x00\nendstream"
    )
    image_content = b"q 100 0 0 100 72 620 cm /Im1 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 7 0 R >>"
        ),
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /XObject << /Im1 8 0 R >> >> /Contents 9 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        _stream_object(content),
        image,
        _stream_object(image_content),
    ]
    return _pdf(objects)


def blank_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << >> /Contents 4 0 R >>"
        ),
        _stream_object(b""),
    ]
    return _pdf(objects)


def encrypted_pdf() -> bytes:
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("test-password")
    writer.write(stream)
    return stream.getvalue()


def _text_stream(lines: list[tuple[str, int, int, int, str]]) -> bytes:
    commands = []
    for font, size, x, y, text in lines:
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"BT /{font} {size} Tf 1 0 0 1 {x} {y} Tm ({escaped}) Tj ET")
    return "\n".join(commands).encode("ascii")


def _stream_object(content: bytes) -> bytes:
    return f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"


def _xref_entry(entry_type: int, field_two: int, field_three: int) -> bytes:
    return bytes([entry_type]) + field_two.to_bytes(4, "big") + field_three.to_bytes(2, "big")


def _pdf(objects: list[bytes]) -> bytes:
    payload = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, item in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode())
        payload.extend(item)
        payload.extend(b"\nendobj\n")

    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode())
    payload.extend(
        (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF").encode()
    )
    return bytes(payload)

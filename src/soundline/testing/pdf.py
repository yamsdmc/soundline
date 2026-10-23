"""Builds small text PDFs for tests, so fixtures stay readable instead of binary blobs."""


def make_pdf(pages: list[list[str]]) -> bytes:
    """One page per list of lines, in Helvetica (WinAnsi encoding); an empty list makes a page
    without a text layer, like a scan."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",  # the page tree, written once the pages are known
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    kids: list[int] = []
    for lines in pages:
        operations = [b"BT /F1 12 Tf 72 720 Td 14 TL"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            operations.append(b"(" + escaped.encode("cp1252") + b") Tj T*")
        operations.append(b"ET")
        stream = b"\n".join(operations) if lines else b""
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        content = len(objects)
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % content
        )
        kids.append(len(objects))
    references = b" ".join(b"%d 0 R" % kid for kid in kids)
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (references, len(kids))
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)

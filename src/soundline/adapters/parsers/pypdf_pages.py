"""A PDF's text layer, page by page, with pypdf (BSD-3-Clause, pure Python): ING-025.

Layout mode keeps the blank lines between paragraphs, which the domain needs to split pages
into paragraphs. Multi-column layouts and scans are out of scope (ING-025, ING-026).
"""

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from soundline.domain.errors import UnreadableDocumentError


class PypdfPages:
    def pages(self, data: bytes) -> list[str]:
        logging.getLogger("pypdf").setLevel(logging.ERROR)  # malformed files warn loudly
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise UnreadableDocumentError("the PDF is encrypted")
            return [page.extract_text(extraction_mode="layout") for page in reader.pages]
        except (PdfReadError, ValueError, KeyError, TypeError) as error:
            raise UnreadableDocumentError(f"not a readable PDF ({error})") from error

"""Human-only branding and offline Pix donation rendering."""
from __future__ import annotations

import qrcode
from qrcode.constants import ERROR_CORRECT_M


TITLE = "EVOLUTION AD3 DIGITAL"
PIX_KEY = "527f144d-ad3b-4ae9-85b9-87a51a8bf035"
PIX_NAME = "AD3 DIGITAL"
PIX_CITY = "FARROUPILHA"
PIX_TXID = "***"
ASCII = r"""
    _    ____  _____   ____ ___ ____ ___ _____  _    _
   / \  |  _ \|___ /  |  _ \_ _/ ___|_ _|_   _|/ \  | |
  / _ \ | | | | |_ \  | | | | | |  _ | |  | | / _ \ | |
 / ___ \| |_| |___) | | |_| | | |_| || |  | |/ ___ \| |___
/_/   \_\____/|____/  |____/___\____|___| |_|/_/   \_\_____|
""".strip("\n")
TAGLINE = "Ferramenta feita para economizar tokens de agentes de IA."


def _tlv(tag: str, value: str) -> str:
    encoded = value.encode("utf-8")
    return f"{tag}{len(encoded):02d}{value}"


def crc16_ccitt(value: str) -> str:
    crc = 0xFFFF
    for byte in value.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def pix_payload() -> str:
    merchant = _tlv("00", "br.gov.bcb.pix") + _tlv("01", PIX_KEY)
    additional = _tlv("05", PIX_TXID)
    body = "".join((
        _tlv("00", "01"), _tlv("26", merchant), _tlv("52", "0000"),
        _tlv("53", "986"), _tlv("58", "BR"), _tlv("59", PIX_NAME),
        _tlv("60", PIX_CITY), _tlv("62", additional), "6304",
    ))
    return body + crc16_ccitt(body)


def qr_matrix(payload: str | None = None) -> list[list[bool]]:
    code = qrcode.QRCode(version=None, error_correction=ERROR_CORRECT_M, box_size=1, border=4)
    code.add_data(payload or pix_payload())
    code.make(fit=True)
    return code.get_matrix()


def render_qr(matrix: list[list[bool]] | None = None, *, color: bool = True) -> str:
    matrix = matrix or qr_matrix()
    if color:
        dark, light, reset = "\x1b[40m  ", "\x1b[47m  ", "\x1b[0m"
        return "\n".join("".join(dark if cell else light for cell in row) + reset for row in matrix)
    return "\n".join("".join("##" if cell else "  " for cell in row) for row in matrix)


def banner() -> str:
    return f"{TITLE}\n{ASCII}\n{TAGLINE}"


def donation_text(*, color: bool = True) -> str:
    return "\n".join((
        banner(), "", "Doação voluntária via Pix para apoiar a ferramenta.",
        render_qr(color=color), "", "PIX COPIA E COLA", pix_payload(),
        "", f"Chave Pix: {PIX_KEY}",
    ))

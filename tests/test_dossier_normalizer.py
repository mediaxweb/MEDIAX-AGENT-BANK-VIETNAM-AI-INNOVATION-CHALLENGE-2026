from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

import dossier_normalizer
from dossier_normalizer import (
    DossierEvidence,
    DossierExtractionDraft,
    DossierFileReference,
    DossierNormalizationError,
    DossierNormalizationRequest,
    NormalizedCustomer,
    load_dossier_pages,
    normalize_dossier,
)


class FakePage:
    def __init__(self, text: str | None):
        self.text = text

    def extract_text(self) -> str | None:
        return self.text


def _write_pdf_stub(path: Path) -> None:
    path.write_bytes(b"%PDF-1.7\n")


def _request(file_path: Path) -> DossierNormalizationRequest:
    return DossierNormalizationRequest(
        dossier_id="DOSSIER-001",
        routing_batch_id="BATCH-001",
        files=[
            DossierFileReference(
                file_id="FILE-001",
                file_ref=str(file_path),
                original_filename="ho_so.pdf",
                source_path="ho_so.pdf",
            )
        ],
    )


def test_normalize_dossier_returns_page_grounded_facts(tmp_path, monkeypatch):
    pdf_path = tmp_path / "ho_so.pdf"
    _write_pdf_stub(pdf_path)
    page_text = "Mã số doanh nghiệp: 0101234567"
    monkeypatch.setattr(
        dossier_normalizer,
        "PdfReader",
        lambda _path: SimpleNamespace(pages=[FakePage(page_text)]),
    )

    async def fake_runner(_agent, _input, *, max_turns):
        assert max_turns == 1
        return SimpleNamespace(
            final_output=DossierExtractionDraft(
                customer=NormalizedCustomer(tax_code="0101234567"),
                evidence=[
                    DossierEvidence(
                        field="customer.tax_code",
                        file_id="FILE-001",
                        page=1,
                        excerpt=page_text,
                        confidence=0.99,
                    )
                ],
            )
        )

    result = asyncio.run(
        normalize_dossier(_request(pdf_path), allowed_root=tmp_path, runner=fake_runner)
    )

    assert result.dossier_id == "DOSSIER-001"
    assert result.page_count == 1
    assert result.facts.customer.tax_code == "0101234567"
    assert result.facts.evidence[0].page == 1


def test_load_dossier_pages_rejects_file_ref_outside_upload_root(tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    outside_pdf = tmp_path / "outside.pdf"
    _write_pdf_stub(outside_pdf)

    with pytest.raises(DossierNormalizationError) as exc_info:
        load_dossier_pages(_request(outside_pdf), allowed_root=upload_root)

    assert exc_info.value.code == "unsafe_file_ref"


def test_load_dossier_pages_rejects_pdf_without_text(tmp_path, monkeypatch):
    pdf_path = tmp_path / "scan.pdf"
    _write_pdf_stub(pdf_path)
    monkeypatch.setattr(
        dossier_normalizer,
        "PdfReader",
        lambda _path: SimpleNamespace(pages=[FakePage(None)]),
    )

    with pytest.raises(DossierNormalizationError) as exc_info:
        load_dossier_pages(_request(pdf_path), allowed_root=tmp_path)

    assert exc_info.value.code == "no_extractable_text"


def test_load_dossier_pages_rejects_checksum_mismatch(tmp_path):
    pdf_path = tmp_path / "ho_so.pdf"
    _write_pdf_stub(pdf_path)
    request = _request(pdf_path)
    request.files[0].checksum_sha256 = "0" * 64

    with pytest.raises(DossierNormalizationError) as exc_info:
        load_dossier_pages(request, allowed_root=tmp_path)

    assert exc_info.value.code == "checksum_mismatch"


def test_normalize_dossier_rejects_hallucinated_evidence(tmp_path, monkeypatch):
    pdf_path = tmp_path / "ho_so.pdf"
    _write_pdf_stub(pdf_path)
    monkeypatch.setattr(
        dossier_normalizer,
        "PdfReader",
        lambda _path: SimpleNamespace(pages=[FakePage("Số tiền vay: 1 tỷ đồng")]),
    )

    async def fake_runner(_agent, _input, *, max_turns):
        return SimpleNamespace(
            final_output=DossierExtractionDraft(
                evidence=[
                    DossierEvidence(
                        field="loan.requested_amount",
                        file_id="FILE-001",
                        page=1,
                        excerpt="Số tiền vay: 2 tỷ đồng",
                        confidence=0.9,
                    )
                ]
            )
        )

    with pytest.raises(DossierNormalizationError) as exc_info:
        asyncio.run(
            normalize_dossier(
                _request(pdf_path), allowed_root=tmp_path, runner=fake_runner
            )
        )

    assert exc_info.value.code == "invalid_evidence"

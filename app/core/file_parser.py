"""CSV / TXT file parser — extracts headers and rows."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import List, Tuple, Dict


# Delimiters tried in order when auto-detecting TXT files
_DELIMITERS = [",", ";", "\t", "|"]


class FileParser:
    """Parses CSV or TXT files and returns headers + list of row dicts."""

    def parse(self, file_path: str) -> Tuple[List[str], List[Dict[str, str]]]:
        """Return (headers, rows).

        Args:
            file_path: Absolute path to a .csv or .txt file.

        Returns:
            A tuple of (list of header strings, list of row dicts).

        Raises:
            ValueError: If the file cannot be parsed or has no recognisable headers.
        """
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"Arquivo não encontrado: {file_path}")

        raw = path.read_bytes()

        # Detect encoding — try UTF-8-BOM, UTF-8, then latin-1
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError("Não foi possível detectar a codificação do arquivo.")

        suffix = path.suffix.lower()

        if suffix == ".csv":
            return self._parse_text(text, dialect="csv")
        else:
            # TXT: auto-detect delimiter
            return self._parse_text(text, dialect="txt")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_text(
        self, text: str, dialect: str
    ) -> Tuple[List[str], List[Dict[str, str]]]:
        """Parse raw text content."""
        delimiter = self._detect_delimiter(text)
        reader = csv.DictReader(
            io.StringIO(text),
            delimiter=delimiter,
            quotechar='"',
            skipinitialspace=True,
        )

        try:
            rows = [
                {k.strip(): v.strip() if v else "" for k, v in row.items()}
                for row in reader
                if any(v and v.strip() for v in row.values())
            ]
        except csv.Error as exc:
            raise ValueError(f"Erro ao ler o arquivo: {exc}") from exc

        if reader.fieldnames is None or not reader.fieldnames:
            raise ValueError(
                "Nenhum cabeçalho encontrado. Verifique se a primeira linha "
                "contém os nomes das colunas."
            )

        headers = [h.strip() for h in reader.fieldnames if h and h.strip()]

        if not headers:
            raise ValueError("Cabeçalhos vazios — verifique o arquivo.")

        if not rows:
            raise ValueError("Nenhuma linha de dados encontrada no arquivo.")

        return headers, rows

    def _detect_delimiter(self, text: str) -> str:
        """Return the most likely delimiter for the text."""
        first_line = text.split("\n", 1)[0]
        counts = {d: first_line.count(d) for d in _DELIMITERS}
        best = max(counts, key=lambda d: counts[d])
        # Fallback to comma if all counts are 0
        return best if counts[best] > 0 else ","

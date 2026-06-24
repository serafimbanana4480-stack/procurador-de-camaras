"""
Export JSON — formato estruturado completo.

Inclui todas as câmaras (mesmo não-LIVE) e metadados.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from procurador.core.models import ScanResult


def export_json(
    result: ScanResult,
    output_path: str,
    include_all: bool = True,
    indent: int = 2,
) -> str:
    """Exporta ScanResult para JSON.

    Args:
        result: ScanResult.
        output_path: Caminho do ficheiro de output.
        include_all: Se True, inclui câmaras não-LIVE também.
        indent: Indentação JSON.

    Returns:
        Caminho do ficheiro escrito.
    """
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = result.to_dict()
    if include_all:
        # Adicionar câmaras não-LIVE ao JSON
        data["cameras"] = [c.to_dict() for c in result.cameras]
        data["stats"]["total_scanned"] = result.total_ips
        data["stats"]["included"] = len(data["cameras"])

    # Adicionar metadata
    data["meta"] = {
        "tool": "Procurador de Câmara",
        "version": "1.0.0",
        "exported_at": datetime.now().isoformat(),
        "format_version": "1.0",
    }

    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False, default=str)

    return str(p)

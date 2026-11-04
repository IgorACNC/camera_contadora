"""Registra no MLflow um treino que já existe em python/runs/<nome>/ e publica o modelo no Registry.

Útil para o modelo versionado no git (ovos_yolo26s-2), treinado antes do MLflow: importa os
parâmetros (args.yaml), as métricas por época (results.csv), os gráficos e o best.pt, e cria uma
versão de "contador-ovos-aedes" com o conf_contagem.txt. Não precisa do dataset nem de GPU.
"""

import argparse
import sys
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))

import rastreio_mlflow as rm  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--treino", default=str(PYTHON_DIR / "runs" / "ovos_yolo26s-2"), help="pasta do treino")
    parser.add_argument("--alias", default="producao", help='alias da versão (padrão "producao"; "" para nenhum)')
    parser.add_argument("--sem-modelo", action="store_true", help="só importar o treino, sem registrar o modelo")
    args = parser.parse_args()

    pasta = Path(args.treino).resolve()
    run_id = rm.registrar_treino_existente(pasta)
    if not args.sem_modelo:
        rm.registrar_modelo(pasta / "weights" / "best.pt", run_id, alias=args.alias or None)

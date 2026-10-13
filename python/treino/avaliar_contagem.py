"""Avalia o modelo treinado pela contagem de ovos por imagem.

1. mAP50, mAP50-95, precisão e recall no teste.
2. Escolhe o limiar de confiança de menor MAE na validação (0.10 a 0.60, passo 0.05).
3. Mede MAE e erro percentual no teste com esse limiar.
O limiar escolhido é salvo em weights/conf_contagem.txt (lido por contar_ovos.py).
"""

import argparse
from pathlib import Path

import numpy as np
from ultralytics import YOLO

PYTHON_DIR = Path(__file__).resolve().parent.parent
DATASET = PYTHON_DIR / "datasets" / "ovos"
MODELO_PADRAO = PYTHON_DIR / "runs" / "ovos_yolo26s" / "weights" / "best.pt"
CONFS = np.round(np.arange(0.10, 0.601, 0.05), 2)
MAX_DET = 1000


def confiancas_e_rotulos(model, split):
    """Para cada imagem do split: confianças previstas (conf >= menor limiar) e nº de ovos do rótulo."""
    pastas = DATASET / split
    confs, reais = [], []
    resultados = model.predict(
        source=str(pastas / "images"), conf=CONFS.min(), max_det=MAX_DET, imgsz=640, stream=True, verbose=False
    )
    for r in resultados:
        confs.append(r.boxes.conf.cpu().numpy())
        rotulo = pastas / "labels" / (Path(r.path).stem + ".txt")
        reais.append(sum(1 for l in rotulo.read_text().splitlines() if l.strip()))
    return confs, np.array(reais)


def erros(confs, reais, conf):
    previstos = np.array([(c >= conf).sum() for c in confs])
    mae = np.abs(previstos - reais).mean()
    com_ovos = reais > 0  # erro percentual só faz sentido em imagens com ovos
    erro_pct = (np.abs(previstos - reais)[com_ovos] / reais[com_ovos]).mean() * 100
    return mae, erro_pct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelo", default=str(MODELO_PADRAO))
    args = parser.parse_args()
    model = YOLO(args.modelo)

    m = model.val(data=str(DATASET / "data.yaml"), split="test", max_det=MAX_DET, imgsz=640, verbose=False)
    print("\n=== Detecção no TESTE ===")
    print(f"mAP50     {m.box.map50:.3f}")
    print(f"mAP50-95  {m.box.map:.3f}")
    print(f"Precisão  {m.box.mp:.3f}")
    print(f"Recall    {m.box.mr:.3f}")

    confs_val, reais_val = confiancas_e_rotulos(model, "valid")
    print("\n=== Contagem na VALIDAÇÃO ===")
    print(" conf    MAE   erro %")
    tabela = []
    for c in CONFS:
        mae, pct = erros(confs_val, reais_val, c)
        tabela.append((mae, c))
        print(f" {c:.2f} {mae:6.2f} {pct:7.1f}")
    conf_escolhido = float(min(tabela)[1])

    confs_test, reais_test = confiancas_e_rotulos(model, "test")
    mae, pct = erros(confs_test, reais_test, conf_escolhido)
    print("\n=== Contagem no TESTE ===")
    print(f"conf escolhido (menor MAE na validação): {conf_escolhido:.2f}")
    print(f"MAE: {mae:.2f} ovos por imagem")
    print(f"Erro percentual médio: {pct:.1f}% (só imagens com ovos)")
    print(f"Imagens: {len(reais_test)}, ovos reais: {reais_test.sum()}")

    arquivo_conf = Path(args.modelo).parent / "conf_contagem.txt"
    arquivo_conf.write_text(f"{conf_escolhido:.2f}\n")
    print(f"\nconf salvo em {arquivo_conf}")


if __name__ == "__main__":
    main()

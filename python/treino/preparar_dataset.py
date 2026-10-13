"""Prepara o dataset Roboflow "aedes eggs v6" para treino com uma única classe "ovo".

- Extrai o zip para python/datasets/aedes_raw/.
- Gera python/datasets/ovos/{train,valid,test}/{images,labels} com a classe trocada para 0.
- Remove do treino as imagens cuja foto de origem (nome antes de ".rf.") aparece na
  validação ou no teste, para evitar vazamento.
- Escreve python/datasets/ovos/data.yaml.
"""

import shutil
import zipfile
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parent.parent
ZIP = PYTHON_DIR / "aedes eggs.v6i.yolov8.zip"
RAW = PYTHON_DIR / "datasets" / "aedes_raw"
SAIDA = PYTHON_DIR / "datasets" / "ovos"
SPLITS = ["train", "valid", "test"]


def origem(img: Path) -> str:
    return img.stem.split(".rf.")[0]


def main():
    if RAW.exists():
        shutil.rmtree(RAW)
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(RAW)

    imagens = {s: sorted(p for p in (RAW / s / "images").iterdir() if p.is_file()) for s in SPLITS}

    origens_avaliacao = {origem(p) for s in ("valid", "test") for p in imagens[s]}
    removidas = [p for p in imagens["train"] if origem(p) in origens_avaliacao]
    imagens["train"] = [p for p in imagens["train"] if origem(p) not in origens_avaliacao]

    if SAIDA.exists():
        shutil.rmtree(SAIDA)

    resumo = {}
    max_ovos = (0, "")
    for s in SPLITS:
        (SAIDA / s / "images").mkdir(parents=True)
        (SAIDA / s / "labels").mkdir(parents=True)
        caixas = 0
        for img in imagens[s]:
            shutil.copy2(img, SAIDA / s / "images" / img.name)
            rotulo = RAW / s / "labels" / (img.stem + ".txt")
            linhas = rotulo.read_text().splitlines() if rotulo.exists() else []
            linhas = ["0 " + l.split(maxsplit=1)[1] for l in linhas if l.strip()]
            (SAIDA / s / "labels" / (img.stem + ".txt")).write_text("\n".join(linhas) + ("\n" if linhas else ""))
            caixas += len(linhas)
            if len(linhas) > max_ovos[0]:
                max_ovos = (len(linhas), f"{s}/{img.name}")
        resumo[s] = (len(imagens[s]), caixas)

    (SAIDA / "data.yaml").write_text(
        f"path: {SAIDA.as_posix()}\n"
        "train: train/images\n"
        "val: valid/images\n"
        "test: test/images\n"
        "nc: 1\n"
        "names: ['ovo']\n"
    )

    origens = {s: {origem(p) for p in imagens[s]} for s in SPLITS}
    comuns = (origens["train"] & origens["valid"]) | (origens["train"] & origens["test"]) | (
        origens["valid"] & origens["test"]
    )

    print("Split   Imagens  Caixas")
    for s in SPLITS:
        print(f"{s:<7} {resumo[s][0]:>7}  {resumo[s][1]:>6}")
    print(f"Imagens removidas do treino (vazamento): {len(removidas)}")
    print(f"Máximo de ovos numa imagem: {max_ovos[0]} ({max_ovos[1]})")
    print(f"Origens em comum entre splits: {len(comuns)}")
    print(f"data.yaml: {SAIDA / 'data.yaml'}")


if __name__ == "__main__":
    main()

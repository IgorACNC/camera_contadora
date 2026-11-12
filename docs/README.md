# Documentação

Esta pasta guarda os relatórios do projeto:

- `Relatorio_CheckPoint_Grupo7.pdf`: relatório do checkpoint (17/11).
- O relatório final, no modelo CSBC/ABNT2, será entregue em 03/12.

## Resultados do modelo

YOLO26s (run `ovos_yolo26s-2`), medido no conjunto de teste com conf 0,40 e `max_det=1000`.

| Métrica | Valor |
|---|---|
| Imagens de teste | 60 |
| Ovos reais | 2362 |
| Ovos contados | 2361 |
| Esquecidos | 198 (8,4%) |
| Falsos positivos | 197 |
| mAP50 | 0,944 |
| Precisão | 0,920 |
| Recall | 0,909 |
| MAE | 3,48 ovos/imagem |
| Desvio-padrão do erro | 7,98 |
| Limiar de confiança | 0,40 |

O erro se concentra em imagens com mais de 100 ovos (MAE 18,6). Até 100 ovos, o MAE fica em até 2.

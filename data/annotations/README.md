# Annotations de recherche

Ce dossier accueille les jeux de requêtes et de résultats pertinents vérifiés manuellement. Les étiquettes ne doivent pas être déduites du statut d’une issue ni des résultats produits par le moteur.

Une ligne JSONL par requête :

```json
{"query":"Grafana renvoie 401 après connexion","relevant_keys":["github_issue:123","documentation:7"]}
```

Utiliser des clés `type_source:id` pour distinguer une issue d’un extrait documentaire. Lancer la comparaison avec :

```powershell
python .\scripts\evaluate_retrieval.py .\data\annotations\gold.jsonl --mode LIGHT --mode STANDARD
```

Le rapport contient MRR, nDCG@5, Recall@K, Precision@K, latence moyenne et p95. Les résultats ne sont significatifs que si les annotations ont été relues.

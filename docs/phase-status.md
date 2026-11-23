# État technique

## Fonctionnalités disponibles

- API FastAPI avec schéma SQLAlchemy, migrations Alembic et stockage SQLite.
- Collecte GitHub paginée, reprise incrémentale, dédoublonnage, conservation des URL sources et exclusion des pull requests.
- Exploration limitée de documentation officielle avec vérification du domaine, de `robots.txt` et enregistrement de la provenance.
- Recherche lexicale avec bonus sur les codes d’erreur ; en mode STANDARD, embeddings Sentence-Transformers, index FAISS CPU, fusion RRF et reclassement Cross-Encoder.
- Analyse de ticket avec résultats sourcés, informations à préciser et brouillon soumis à validation humaine.
- Interface React/TypeScript pour le tableau de bord, la base de connaissances, les sources et la recherche.
- Extraction de journaux avec masquage de données sensibles courantes, normalisation de signatures et analyse de documents HTML, Markdown, texte, JSON et CSV.

## Corpus local de démonstration

Vérifié le 3 novembre 2026 : 360 incidents issus de quatre dépôts GitHub, 18 pages de documentation, 15 références média et 42 relations incident–pull request. La base SQLite, les réponses brutes et l’index dense restent des fichiers locaux ignorés par Git.

## Limites connues

- Les modèles d’embedding et de reclassement nécessitent l’installation des dépendances STANDARD et peuvent être téléchargés au premier chargement si leur cache est vide.
- Aucun score de benchmark n’est publié sans annotations révisées manuellement. Le format et l’évaluateur sont décrits dans `data/annotations/README.md`.
- L’OCR, les embeddings d’images, la transcription audio et le raisonnement via Ollama ne sont pas intégrés.
- Une issue fermée n’est pas considérée automatiquement comme une résolution confirmée.

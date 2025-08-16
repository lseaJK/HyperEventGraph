#!/usr/bin/env python3
"""
Lightweight clustering evaluation for HyperEventGraph (minimal-cost C).

Produces:
 - CSV with sampled events per cluster for human review
 - JSON report with cluster cohesion/separation and silhouette (where applicable)

Strategy: TF-IDF (with jieba tokenization when available) + cosine similarity.
"""

import os
import json
import argparse
from pathlib import Path
import time
from collections import defaultdict

project_root = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import silhouette_score

try:
    import jieba
    _HAS_JIEBA = True
except Exception:
    _HAS_JIEBA = False


def tokenize_for_tfidf(text: str) -> str:
    if not text:
        return ""
    if _HAS_JIEBA:
        return " ".join(jieba.lcut(text))
    # fallback: return raw text (TF-IDF will use whitespace/token heuristics)
    return text


def load_events(db_manager: DatabaseManager, include_status: str | None = None) -> pd.DataFrame:
    # If include_status provided, restrict to that status; otherwise read entire table
    if include_status:
        df = db_manager.get_records_by_status_as_df(include_status)
    else:
        # read all rows
        with db_manager._get_connection() as conn:
            df = pd.read_sql_query('SELECT * FROM master_state', conn)
    return df


def build_groups(df: pd.DataFrame, group_by: str = 'story_id') -> dict:
    groups = defaultdict(list)
    for _, row in df.iterrows():
        label = row.get(group_by)
        # normalize empty strings / None
        if label is None or (isinstance(label, float) and pd.isna(label)):
            continue
        groups[str(label)].append({
            'id': row['id'],
            'source_text': row.get('source_text', ''),
            'assigned_event_type': row.get('assigned_event_type', ''),
            'involved_entities': row.get('involved_entities', ''),
            'story_id': row.get('story_id', None),
            'cluster_id': row.get('cluster_id', None)
        })
    return dict(groups)


def evaluate_groups(groups: dict, sample_per_group: int = 3, min_group_size: int = 2, out_dir: Path = Path('outputs')) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {
        'created_at': int(time.time()),
        'groups_evaluated': 0,
        'total_events': 0,
        'clusters': {}
    }

    # Flatten corpus and keep mapping
    texts = []
    index_to_meta = []
    label_for_index = []

    for label, events in groups.items():
        if len(events) < min_group_size:
            continue
        for ev in events:
            texts.append(tokenize_for_tfidf(ev['source_text'] or ''))
            index_to_meta.append(ev)
            label_for_index.append(label)

    if not texts:
        raise RuntimeError('No groups with sufficient size found for evaluation')

    vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)
    # Convert sparse matrix to dense array to avoid np.matrix compatibility issues
    X = X.toarray()

    unique_labels = sorted(set(label_for_index))
    label_to_indices = {lab: [] for lab in unique_labels}
    for idx, lab in enumerate(label_for_index):
        label_to_indices[lab].append(idx)

    # Compute centroids
    centroids = {}
    intra_sim = {}
    for lab, indices in label_to_indices.items():
        mat = X[indices]
        centroid = np.asarray(mat.mean(axis=0)).ravel()
        centroids[lab] = centroid
        # compute similarity of members to centroid
        sims = cosine_similarity(mat, centroid.reshape(1, -1))
        # sims shape (n,1)
        intra_sim[lab] = float(np.mean(sims)) if sims.size else 0.0

    # inter-centroid similarity
    lab_list = list(centroids.keys())
    cent_mat = np.array([centroids[lab] for lab in lab_list])
    if len(lab_list) >= 2:
        inter_sim_matrix = cosine_similarity(cent_mat)
        # exclude diagonal
        n = inter_sim_matrix.shape[0]
        inter_sims = inter_sim_matrix[np.triu_indices(n, k=1)]
        mean_inter_sim = float(np.mean(inter_sims)) if inter_sims.size else 0.0
    else:
        mean_inter_sim = 0.0

    # silhouette
    label_to_int = {lab: i for i, lab in enumerate(lab_list)}
    labels_int = np.array([label_to_int[lab] for lab in label_for_index])
    silhouette = None
    try:
        if len(set(labels_int)) >= 2 and X.shape[0] > len(set(labels_int)):
            # Convert sparse matrix to dense for silhouette_score
            X_dense = X.toarray() if hasattr(X, 'toarray') else X
            silhouette = float(silhouette_score(X_dense, labels_int, metric='cosine'))
    except Exception:
        silhouette = None

    # assemble per-cluster stats and sample rows
    rows = []
    total_events = 0
    clusters_info = {}
    for lab in lab_list:
        indices = label_to_indices[lab]
        total_events += len(indices)
        clusters_info[lab] = {
            'size': len(indices),
            'intra_cohesion_mean': intra_sim.get(lab, 0.0)
        }
        # sample events
        sample_indices = indices[:sample_per_group]
        for si in sample_indices:
            meta = index_to_meta[si]
            rows.append({
                'group_label': lab,
                'group_size': len(indices),
                'intra_cohesion_mean': clusters_info[lab]['intra_cohesion_mean'],
                'event_id': meta['id'],
                'assigned_event_type': meta.get('assigned_event_type', ''),
                'story_id': meta.get('story_id'),
                'cluster_id': meta.get('cluster_id'),
                'text_sample': (meta.get('source_text') or '')[:300]
            })

    results.update({
        'groups_evaluated': len(lab_list),
        'total_events': total_events,
        'mean_inter_centroid_similarity': mean_inter_sim,
        'silhouette_cosine': silhouette,
        'clusters': clusters_info
    })

    ts = int(time.time())
    csv_path = out_dir / f'clustering_evaluation_samples_{ts}.csv'
    report_path = out_dir / f'clustering_evaluation_report_{ts}.json'

    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding='utf-8-sig')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return {'csv': str(csv_path), 'report': str(report_path), 'results': results}


def main():
    parser = argparse.ArgumentParser(description='Evaluate clustering quality and create human-sampling CSV')
    parser.add_argument('--group-by', choices=['story_id', 'cluster_id'], default='story_id', help='Which DB field to use as cluster label')
    parser.add_argument('--status', default=None, help="Optional DB status filter, e.g. 'pending_relationship_analysis' or leave empty to scan all records")
    parser.add_argument('--sample-per-group', type=int, default=3, help='How many examples per cluster to include in CSV')
    parser.add_argument('--min-group-size', type=int, default=2, help='Minimum cluster size to include in metrics')
    parser.add_argument('--out-dir', default='outputs', help='Directory to write outputs')

    args = parser.parse_args()

    load_config(project_root / 'config.yaml')
    cfg = get_config()
    db_path = cfg.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)

    print(f'Loading records from DB (status filter={args.status})...')
    df = load_events(db_manager, include_status=args.status)
    print(f'Total records loaded: {len(df)}')

    groups = build_groups(df, group_by=args.group_by)
    print(f'Found {len(groups)} groups by {args.group_by}.')

    try:
        res = evaluate_groups(groups, sample_per_group=args.sample_per_group, min_group_size=args.min_group_size, out_dir=Path(args.out_dir))
        print('Evaluation complete.')
        print('CSV:', res['csv'])
        print('Report:', res['report'])
    except Exception as e:
        import traceback
        print('Evaluation failed:', e)
        print('Full traceback:')
        traceback.print_exc()


if __name__ == '__main__':
    main()

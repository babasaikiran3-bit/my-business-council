"""
Re-analyze with improved extraction and filtering
"""
import pandas as pd
import json
import re

def extract_improved(raw_output, dataset):
    """Improved extraction"""
    if not raw_output:
        return "unknown"

    text = raw_output.strip()

    if dataset == "pubmedqa":
        last_line = text.split("\n")[-1].strip().lower()

        for label in ["maybe", "yes", "no"]:
            if label == last_line or last_line == f"{label}.":
                return label

        match = re.search(r'\b(yes|no|maybe)\b', text.lower())
        if match:
            return match.group(1)

        return "unknown"

    else:  # medqa, mmlu
        last_line = text.split("\n")[-1].strip().upper()

        if last_line in ["A.", "B.", "C.", "D.", "A", "B", "C", "D"]:
            return last_line.rstrip(".")

        match = re.match(r'^([A-D])\b', last_line)
        if match:
            return match.group(1)

        match = re.search(r'(?:answer\s*(?:is|:)\s*)([A-D])\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        last_100 = text[-100:] if len(text) > 100 else text
        match = re.search(r'\b([A-D])\b', last_100.upper())
        if match:
            return match.group(1).upper()

        return "unknown"


# Load data
results_df = pd.read_csv('analysis_results/db_results.csv')
experiments_df = pd.read_csv('analysis_results/db_experiments.csv')

merged = results_df.merge(
    experiments_df[['id', 'dataset', 'n_stages']],
    left_on='experiment_id',
    right_on='id',
    suffixes=('', '_exp')
)

print("="*80)
print("RE-ANALYSIS WITH IMPROVED EXTRACTION")
print("="*80)
print(f"\nOriginal: {len(merged)} predictions, {len(merged[merged['predicted']=='unknown'])} unknown ({len(merged[merged['predicted']=='unknown'])/len(merged)*100:.1f}%)")

# Re-extract
improved_preds = []
for _, row in merged.iterrows():
    try:
        debate_log = json.loads(row['debate_log'])
        raw = debate_log.get('judge_output') or debate_log.get('generator_output') or ""
        improved_preds.append(extract_improved(raw, row['dataset']))
    except:
        improved_preds.append(row['predicted'])

merged['pred_improved'] = improved_preds
merged['pred_imp_norm'] = merged['pred_improved'].str.lower().str.strip()
merged['gold_norm'] = merged['gold'].astype(str).str.lower().str.strip()
merged['correct_improved'] = merged['pred_imp_norm'] == merged['gold_norm']

print(f"Improved: {len(merged[merged['pred_improved']=='unknown'])} unknown ({len(merged[merged['pred_improved']=='unknown'])/len(merged)*100:.1f}%)")
print(f"Reduction: {len(merged[merged['predicted']=='unknown']) - len(merged[merged['pred_improved']=='unknown'])} fewer unknowns")

orig_acc = merged['correct'].mean()
new_acc = merged['correct_improved'].mean()
print(f"\nAccuracy: {orig_acc:.4f} -> {new_acc:.4f} ({new_acc-orig_acc:+.4f})")

print("\nBy dataset and stage:")
comp = merged.groupby(['dataset', 'n_stages']).agg({
    'correct': 'mean',
    'correct_improved': 'mean',
    'pred_improved': lambda x: (x == 'unknown').sum()
}).round(4)
comp.columns = ['acc_orig', 'acc_improved', 'unknown_count']
comp['change'] = comp['acc_improved'] - comp['acc_orig']
print(comp)

# Filter high quality (< 20% unknown)
unk_rate = merged.groupby('experiment_id')['pred_improved'].apply(lambda x: (x == 'unknown').sum() / len(x))
quality_exps = unk_rate[unk_rate < 0.20].index.tolist()

filtered = merged[merged['experiment_id'].isin(quality_exps)]

print(f"\n{'='*80}")
print("FILTERED HIGH-QUALITY (<20% unknown)")
print(f"{'='*80}")
print(f"Experiments: {len(quality_exps)} / {len(unk_rate)}")
print(f"Predictions: {len(filtered)} / {len(merged)}")
print(f"Unknown rate: {len(filtered[filtered['pred_improved']=='unknown'])/len(filtered)*100:.1f}%")
print(f"Accuracy: {filtered['correct_improved'].mean():.4f}")

print("\nBy dataset:")
print(filtered.groupby(['dataset', 'n_stages']).agg({
    'correct_improved': 'mean',
    'experiment_id': 'nunique'
}).round(4))

# Save
merged[['experiment_id', 'question_id', 'predicted', 'pred_improved', 'gold', 'correct', 'correct_improved']].to_csv(
    'analysis_results/results_reanalyzed.csv', index=False
)
filtered.to_csv('analysis_results/results_filtered_highquality.csv', index=False)

print("\nSaved:")
print("  - analysis_results/results_reanalyzed.csv")
print("  - analysis_results/results_filtered_highquality.csv")
print(f"\n{'='*80}")

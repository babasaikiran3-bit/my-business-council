"""
Audit evaluation quality - check for data issues
"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import json

print("="*80)
print("EVALUATION QUALITY AUDIT")
print("="*80)

# Load data
experiments_df = pd.read_csv('analysis_results/db_experiments.csv')
results_df = pd.read_csv('analysis_results/db_results.csv')

print("\n1. EXPERIMENT STATUS CHECK")
print("-"*80)
print(f"Total experiments: {len(experiments_df)}")
print(f"Status breakdown:")
print(experiments_df['status'].value_counts())

completed = experiments_df[experiments_df['status'] == 'completed']
print(f"\nCompleted experiments: {len(completed)}")
print(f"  By dataset: {completed['dataset'].value_counts().to_dict()}")
print(f"  By stage: {completed['n_stages'].value_counts().to_dict()}")

print("\n2. UNKNOWN PREDICTIONS CHECK")
print("-"*80)
print(f"Total predictions: {len(results_df)}")
print(f"\nPrediction distribution:")
pred_counts = results_df['predicted'].value_counts().head(15)
print(pred_counts)

unknown = results_df[results_df['predicted'] == 'unknown']
print(f"\n⚠ Unknown predictions: {len(unknown)} / {len(results_df)} ({len(unknown)/len(results_df)*100:.1f}%)")

if len(unknown) > 0:
    print(f"\nBy experiment (experiments with unknown predictions):")
    unknown_by_exp = unknown.groupby('experiment_id').size().sort_values(ascending=False)
    for exp_id, count in unknown_by_exp.head(10).items():
        exp_info = experiments_df[experiments_df['id'] == exp_id].iloc[0]
        total = len(results_df[results_df['experiment_id'] == exp_id])
        print(f"  {exp_id[:40]:40s} - {count:3d}/{total:3d} ({count/total*100:5.1f}%) unknown")
        print(f"    Model: {exp_info['model']}, Dataset: {exp_info['dataset']}, Stages: {exp_info['n_stages']}")

print("\n3. ACCURACY VS CONFUSION MATRIX CHECK")
print("-"*80)
print("Verifying stored accuracy matches actual correct/total...")

for _, exp in completed.iterrows():
    exp_id = exp['id']

    # Get results for this experiment
    exp_results = results_df[results_df['experiment_id'] == exp_id]

    # Calculate actual accuracy
    actual_correct = exp_results['correct'].sum()
    actual_total = len(exp_results)
    actual_accuracy = actual_correct / actual_total if actual_total > 0 else 0

    # Stored accuracy
    stored_accuracy = exp['accuracy']

    # Check match
    diff = abs(actual_accuracy - stored_accuracy)
    if diff > 0.01:  # Allow 1% tolerance for rounding
        print(f"⚠ MISMATCH: {exp_id[:50]}")
        print(f"  Stored: {stored_accuracy:.4f}, Actual: {actual_accuracy:.4f}, Diff: {diff:.4f}")

print("✓ Accuracy verification complete")

print("\n4. MAYBE RECALL CALCULATION CHECK (PubMedQA)")
print("-"*80)
pubmedqa_exps = completed[completed['dataset'] == 'pubmedqa']

for _, exp in pubmedqa_exps.iterrows():
    exp_id = exp['id']
    exp_results = results_df[results_df['experiment_id'] == exp_id]

    # Calculate actual maybe recall
    maybe_gold = exp_results[exp_results['gold'].str.lower() == 'maybe']
    if len(maybe_gold) > 0:
        maybe_correct = maybe_gold[maybe_gold['correct'] == 1]
        actual_maybe_recall = len(maybe_correct) / len(maybe_gold)
    else:
        actual_maybe_recall = 0.0

    # Stored maybe recall
    stored_maybe_recall = exp['maybe_recall']

    if pd.notna(stored_maybe_recall):
        diff = abs(actual_maybe_recall - stored_maybe_recall)
        if diff > 0.01:
            print(f"⚠ MISMATCH: {exp_id[:50]}")
            print(f"  Stored: {stored_maybe_recall:.4f}, Actual: {actual_maybe_recall:.4f}")

print("✓ Maybe recall verification complete")

print("\n5. F1-MACRO VERIFICATION")
print("-"*80)
from sklearn.metrics import f1_score

for _, exp in completed.head(3).iterrows():  # Check first 3 as examples
    exp_id = exp['id']
    dataset = exp['dataset']
    exp_results = results_df[results_df['experiment_id'] == exp_id]

    predicted = exp_results['predicted'].str.lower().str.strip().tolist()
    gold = exp_results['gold'].str.lower().str.strip().tolist()

    # Define labels
    if dataset == 'pubmedqa':
        labels = ['yes', 'no', 'maybe']
    else:
        labels = ['a', 'b', 'c', 'd']

    # Calculate F1
    actual_f1 = f1_score(gold, predicted, labels=labels, average='macro', zero_division=0)
    stored_f1 = exp['f1_macro']

    diff = abs(actual_f1 - stored_f1) if pd.notna(stored_f1) else 0
    status = "✓" if diff < 0.01 else "⚠"

    print(f"{status} {exp_id[:50]}")
    print(f"  Stored F1: {stored_f1:.4f}, Actual F1: {actual_f1:.4f}, Diff: {diff:.4f}")

print("\n6. CASE SENSITIVITY CHECK")
print("-"*80)
print("Checking if predicted/gold have mixed case issues...")
pred_sample = results_df['predicted'].head(100)
gold_sample = results_df['gold'].head(100)

pred_mixed = pred_sample[pred_sample.str.contains('[A-Z]', na=False) & pred_sample.str.contains('[a-z]', na=False)]
gold_mixed = gold_sample[gold_sample.str.contains('[A-Z]', na=False) & gold_sample.str.contains('[a-z]', na=False)]

print(f"Predicted with mixed case: {len(pred_mixed)}")
print(f"Gold with mixed case: {len(gold_mixed)}")

if len(pred_mixed) > 0:
    print(f"Sample: {pred_mixed.head(5).tolist()}")
if len(gold_mixed) > 0:
    print(f"Sample: {gold_mixed.head(5).tolist()}")

print("\n7. STATISTICAL TESTS DATA CHECK")
print("-"*80)
print("Checking if we have proper pairing for statistical tests...")

# Group by dataset, prompt, model to check pairing
grouped = completed.groupby(['dataset', 'model', 'prompt_version'])

print(f"Total experiment groups: {len(grouped)}")
print("\nGroups with both 1-stage and 3-stage (needed for paired tests):")

paired_count = 0
for (dataset, model, prompt), group in grouped:
    stages = sorted(group['n_stages'].unique())
    if 1 in stages and 3 in stages:
        paired_count += 1
        n_1stage = len(group[group['n_stages'] == 1])
        n_3stage = len(group[group['n_stages'] == 3])
        print(f"  {dataset:10s} | {model[:30]:30s} | {prompt:20s} | 1-stage: {n_1stage}, 3-stage: {n_3stage}")

print(f"\n✓ Total paired groups: {paired_count}")

print("\n" + "="*80)
print("AUDIT COMPLETE")
print("="*80)

"""
Analysis script for LLM Council experiments
Implements statistical analysis from Project Plan Sections 6.2-6.4:
- Paired t-tests (1-stage vs 3-stage)
- Cohen's d effect sizes
- 95% confidence intervals
- Confusion matrices
- Maybe Recall analysis
- Qualitative debate log analysis framework
"""

import sys
import io

# Fix Windows console UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from pathlib import Path
import json
from typing import Dict, List, Tuple

# Configuration
DB_PATH = "llm-council/data/experiments.db"
OUTPUT_DIR = "analysis_results"
Path(OUTPUT_DIR).mkdir(exist_ok=True)

def load_experiments():
    """Load all experiments from database"""
    if not Path(DB_PATH).exists():
        print(f"❌ Database not found at {DB_PATH}")
        print("\n📋 Action needed:")
        print("1. Get experiments.db from Yu Taek")
        print("2. Place it at: llm-council/data/experiments.db")
        print("3. Run this script again")
        return None

    conn = sqlite3.connect(DB_PATH)

    # Load experiments
    df = pd.read_sql_query("""
        SELECT
            id, timestamp, model, prompt_version, dataset,
            n_samples, n_stages, status, accuracy, f1_macro,
            maybe_recall, total_tokens, notes, tags
        FROM experiments
        WHERE status = 'completed'
        ORDER BY timestamp DESC
    """, conn)

    conn.close()

    print(f"✅ Loaded {len(df)} completed experiments")
    return df

def load_question_results():
    """Load per-question results from database"""
    if not Path(DB_PATH).exists():
        return None

    conn = sqlite3.connect(DB_PATH)

    # Load results with experiment metadata
    results_df = pd.read_sql_query("""
        SELECT
            r.experiment_id,
            r.question_id,
            r.predicted,
            r.gold,
            r.correct,
            r.debate_log,
            r.token_usage,
            e.model,
            e.prompt_version,
            e.dataset,
            e.n_stages
        FROM results r
        JOIN experiments e ON r.experiment_id = e.id
        WHERE e.status = 'completed'
    """, conn)

    conn.close()

    print(f"✅ Loaded {len(results_df)} question-level results")
    return results_df

def compute_confidence_interval(data: np.ndarray, confidence=0.95) -> Tuple[float, float]:
    """Compute confidence interval for mean"""
    n = len(data)
    if n < 2:
        return (np.nan, np.nan)

    mean = np.mean(data)
    std_err = stats.sem(data)
    margin = std_err * stats.t.ppf((1 + confidence) / 2, n - 1)

    return (mean - margin, mean + margin)

def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Compute Cohen's d effect size"""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

    if pooled_std == 0:
        return 0.0

    return (np.mean(group1) - np.mean(group2)) / pooled_std

def analyze_debate_impact(df):
    """Compare 1-stage vs 3-stage performance with paired t-tests"""
    print("\n" + "="*60)
    print("ANALYSIS 1: Single-Agent vs Multi-Agent Debate")
    print("="*60)

    single = df[df['n_stages'] == 1]
    multi = df[df['n_stages'] == 3]

    if len(single) == 0 or len(multi) == 0:
        print("⚠️ Need both 1-stage and 3-stage experiments")
        return

    results_list = []

    # Analyze by dataset
    for dataset in df['dataset'].unique():
        print(f"\n📊 DATASET: {dataset.upper()}")
        print("-" * 60)

        dataset_df = df[df['dataset'] == dataset]

        # Try paired comparison first (match by model + prompt_version)
        single_data = dataset_df[dataset_df['n_stages'] == 1]
        multi_data = dataset_df[dataset_df['n_stages'] == 3]

        # Create matched pairs
        merged = pd.merge(
            single_data,
            multi_data,
            on=['dataset', 'model', 'prompt_version'],
            suffixes=('_1stage', '_3stage')
        )

        metrics = ['accuracy', 'f1_macro', 'maybe_recall']

        for metric in metrics:
            col_1 = f'{metric}_1stage'
            col_3 = f'{metric}_3stage'

            # Skip if no data
            if col_1 not in merged.columns or col_3 not in merged.columns:
                continue

            paired_data = merged[[col_1, col_3]].dropna()

            if len(paired_data) == 0:
                continue

            vals_1stage = paired_data[col_1].values
            vals_3stage = paired_data[col_3].values

            # Compute statistics
            mean_1 = vals_1stage.mean()
            mean_3 = vals_3stage.mean()
            improvement = ((mean_3 - mean_1) / mean_1) * 100 if mean_1 > 0 else 0

            # Paired t-test
            if len(vals_1stage) >= 2:
                t_stat, p_value = stats.ttest_rel(vals_3stage, vals_1stage)
            else:
                t_stat, p_value = np.nan, np.nan

            # Cohen's d
            effect_size = cohens_d(vals_3stage, vals_1stage)

            # 95% CI for difference
            diff = vals_3stage - vals_1stage
            ci_lower, ci_upper = compute_confidence_interval(diff)

            # 95% CI for each group
            ci_1_lower, ci_1_upper = compute_confidence_interval(vals_1stage)
            ci_3_lower, ci_3_upper = compute_confidence_interval(vals_3stage)

            print(f"\n   {metric.upper().replace('_', ' ')}")
            print(f"      1-stage: {mean_1:.4f} (95% CI: [{ci_1_lower:.4f}, {ci_1_upper:.4f}])")
            print(f"      3-stage: {mean_3:.4f} (95% CI: [{ci_3_lower:.4f}, {ci_3_upper:.4f}])")
            print(f"      Improvement: {improvement:+.2f}%")
            print(f"      Paired t-test: t={t_stat:.3f}, p={p_value:.4f} {'✅' if p_value < 0.05 else '❌'}")
            print(f"      Effect size (Cohen's d): {effect_size:.3f}")
            print(f"      95% CI for difference: [{ci_lower:.4f}, {ci_upper:.4f}]")

            # Store for CSV output
            results_list.append({
                'dataset': dataset,
                'metric': metric,
                'mean_1stage': mean_1,
                'mean_3stage': mean_3,
                'improvement_pct': improvement,
                'ci_1stage_lower': ci_1_lower,
                'ci_1stage_upper': ci_1_upper,
                'ci_3stage_lower': ci_3_lower,
                'ci_3stage_upper': ci_3_upper,
                'paired_n': len(vals_1stage),
                't_statistic': t_stat,
                'p_value': p_value,
                'cohens_d': effect_size,
                'ci_diff_lower': ci_lower,
                'ci_diff_upper': ci_upper,
                'significant': p_value < 0.05 if not np.isnan(p_value) else False
            })

    # Token cost analysis
    single_tokens = single['total_tokens'].mean()
    multi_tokens = multi['total_tokens'].mean()
    cost_ratio = multi_tokens / single_tokens if single_tokens > 0 else 0

    print(f"\n💰 COST ANALYSIS")
    print(f"   Single-agent tokens: {single_tokens:.0f}")
    print(f"   Multi-agent tokens:  {multi_tokens:.0f}")
    print(f"   Cost ratio: {cost_ratio:.2f}x")

    # Save statistical tests to CSV
    if results_list:
        stats_df = pd.DataFrame(results_list)
        output_path = f'{OUTPUT_DIR}/statistical_tests.csv'
        stats_df.to_csv(output_path, index=False)
        print(f"\n✅ Statistical tests saved to: {output_path}")

    return results_list

def analyze_prompt_versions(df):
    """Compare different prompt versions"""
    print("\n" + "="*60)
    print("ANALYSIS 2: Prompt Version Comparison")
    print("="*60)

    # Focus on maybe_recall for PubMedQA
    pubmed = df[df['dataset'] == 'pubmedqa']

    if len(pubmed) == 0:
        print("⚠️ No PubMedQA experiments found")
        return

    prompt_summary = pubmed.groupby('prompt_version').agg({
        'maybe_recall': ['mean', 'std', 'count'],
        'accuracy': 'mean',
        'total_tokens': 'mean'
    }).round(4)

    print("\n📋 Maybe Recall by Prompt Version (PubMedQA):")
    print(prompt_summary)

    # Best prompt
    best_prompt = pubmed.loc[pubmed['maybe_recall'].idxmax()]
    print(f"\n🏆 Best performing prompt:")
    print(f"   {best_prompt['prompt_version']}")
    print(f"   Maybe Recall: {best_prompt['maybe_recall']:.4f}")
    print(f"   Accuracy: {best_prompt['accuracy']:.4f}")

def analyze_by_model(df):
    """Compare different models"""
    print("\n" + "="*60)
    print("ANALYSIS 3: Model Comparison")
    print("="*60)

    model_summary = df.groupby('model').agg({
        'accuracy': 'mean',
        'f1_macro': 'mean',
        'maybe_recall': 'mean',
        'total_tokens': 'mean'
    }).round(4)

    print("\n📋 Performance by Model:")
    print(model_summary)

def analyze_confusion_matrices(results_df):
    """Generate confusion matrices for all datasets"""
    print("\n" + "="*60)
    print("ANALYSIS 4: Confusion Matrices")
    print("="*60)

    if results_df is None or len(results_df) == 0:
        print("⚠️ No question-level results available")
        return

    # Analyze by dataset and stage
    for dataset in results_df['dataset'].unique():
        print(f"\n📊 DATASET: {dataset.upper()}")

        dataset_results = results_df[results_df['dataset'] == dataset]

        # Determine label set
        if dataset == 'pubmedqa':
            labels = ['yes', 'no', 'maybe']
        else:
            labels = ['A', 'B', 'C', 'D']

        for n_stages in sorted(dataset_results['n_stages'].unique()):
            stage_results = dataset_results[dataset_results['n_stages'] == n_stages]

            y_true = stage_results['gold'].tolist()
            y_pred = stage_results['predicted'].tolist()

            # Filter to valid labels only
            valid_indices = [i for i, (t, p) in enumerate(zip(y_true, y_pred))
                           if t in labels and p in labels]

            if len(valid_indices) == 0:
                continue

            y_true_filtered = [y_true[i] for i in valid_indices]
            y_pred_filtered = [y_pred[i] for i in valid_indices]

            # Compute confusion matrix
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_true_filtered, y_pred_filtered, labels=labels)

            print(f"\n   {n_stages}-stage (n={len(y_true_filtered)}):")
            print(f"   Predicted →")
            print(f"   True ↓")

            # Print as formatted table
            header = "      " + "  ".join(f"{l:>6}" for l in labels)
            print(header)

            for i, true_label in enumerate(labels):
                row = f"   {true_label:>3}  " + "  ".join(f"{cm[i, j]:>6}" for j in range(len(labels)))
                print(row)

            # Calculate per-class metrics
            print(f"\n   Per-class metrics:")
            for i, label in enumerate(labels):
                tp = cm[i, i]
                fp = cm[:, i].sum() - tp
                fn = cm[i, :].sum() - tp

                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

                print(f"      {label}: Precision={precision:.3f}, Recall={recall:.3f}, F1={f1:.3f}")

            # Save confusion matrix visualization
            plt.figure(figsize=(8, 6))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                       xticklabels=labels, yticklabels=labels,
                       cbar_kws={'label': 'Count'})
            plt.xlabel('Predicted', fontsize=12)
            plt.ylabel('True', fontsize=12)
            plt.title(f'Confusion Matrix: {dataset.upper()} ({n_stages}-stage)',
                     fontsize=14, fontweight='bold')
            plt.tight_layout()

            filename = f'{OUTPUT_DIR}/confusion_matrix_{dataset}_{n_stages}stage.png'
            plt.savefig(filename, dpi=300, bbox_inches='tight')
            print(f"   ✅ Saved: {filename}")
            plt.close()

def analyze_maybe_recall_deep(df, results_df):
    """Deep dive into Maybe Recall performance (Section 6.2)"""
    print("\n" + "="*60)
    print("ANALYSIS 5: Maybe Recall Deep Dive (PubMedQA)")
    print("="*60)

    pubmed = df[df['dataset'] == 'pubmedqa']

    if len(pubmed) == 0:
        print("⚠️ No PubMedQA experiments found")
        return

    # Analysis by prompt version and stage
    maybe_results = []

    for prompt in pubmed['prompt_version'].unique():
        for n_stages in sorted(pubmed['n_stages'].unique()):
            subset = pubmed[(pubmed['prompt_version'] == prompt) &
                           (pubmed['n_stages'] == n_stages)]

            if len(subset) == 0:
                continue

            maybe_vals = subset['maybe_recall'].dropna().values

            if len(maybe_vals) == 0:
                continue

            mean_recall = maybe_vals.mean()
            ci_lower, ci_upper = compute_confidence_interval(maybe_vals)

            maybe_results.append({
                'prompt_version': prompt,
                'n_stages': n_stages,
                'maybe_recall_mean': mean_recall,
                'maybe_recall_std': maybe_vals.std(),
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'n_experiments': len(maybe_vals)
            })

            print(f"\n   {prompt} ({n_stages}-stage):")
            print(f"      Mean: {mean_recall:.4f}")
            print(f"      Std:  {maybe_vals.std():.4f}")
            print(f"      95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
            print(f"      n={len(maybe_vals)}")

    # Save to CSV
    if maybe_results:
        maybe_df = pd.DataFrame(maybe_results)
        output_path = f'{OUTPUT_DIR}/maybe_recall_analysis.csv'
        maybe_df.to_csv(output_path, index=False)
        print(f"\n✅ Maybe Recall analysis saved to: {output_path}")

    # Error analysis: Find examples where maybe was misclassified
    if results_df is not None:
        pubmed_results = results_df[results_df['dataset'] == 'pubmedqa']
        maybe_errors = pubmed_results[
            (pubmed_results['gold'] == 'maybe') &
            (pubmed_results['predicted'] != 'maybe')
        ]

        print(f"\n📊 Maybe Misclassifications:")
        print(f"   Total 'maybe' gold labels: {len(pubmed_results[pubmed_results['gold'] == 'maybe'])}")
        print(f"   Misclassified: {len(maybe_errors)}")

        if len(maybe_errors) > 0:
            error_breakdown = maybe_errors['predicted'].value_counts()
            print(f"\n   Misclassified as:")
            for pred, count in error_breakdown.items():
                print(f"      {pred}: {count}")

def create_visualizations(df):
    """Create publication-quality plots (Section 6.4)"""
    print("\n" + "="*60)
    print("Creating Visualizations")
    print("="*60)

    # Set style
    sns.set_style("whitegrid")
    plt.rcParams['figure.dpi'] = 300

    # Plot 1: Maybe Recall Comparison (1-stage vs 3-stage)
    fig, ax = plt.subplots(figsize=(10, 6))

    pubmed = df[df['dataset'] == 'pubmedqa']
    if len(pubmed) > 0:
        data_to_plot = pubmed.groupby(['n_stages', 'prompt_version'])['maybe_recall'].mean().reset_index()

        sns.barplot(data=data_to_plot, x='prompt_version', y='maybe_recall',
                   hue='n_stages', ax=ax, palette=['#e74c3c', '#2ecc71'])

        ax.set_xlabel('Prompt Version', fontsize=12)
        ax.set_ylabel('Maybe Recall', fontsize=12)
        ax.set_title('Maybe Recall: Single-Agent vs Multi-Agent Debate (PubMedQA)',
                    fontsize=14, fontweight='bold')
        ax.legend(title='Stages', labels=['1-stage (single)', '3-stage (debate)'])
        ax.set_ylim(0, 1)

        plt.tight_layout()
        plt.savefig(f'{OUTPUT_DIR}/maybe_recall_comparison.png', dpi=300, bbox_inches='tight')
        print(f"✅ Saved: {OUTPUT_DIR}/maybe_recall_comparison.png")
        plt.close()

    # Plot 2: Accuracy by Dataset
    fig, ax = plt.subplots(figsize=(10, 6))

    data_to_plot = df.groupby(['dataset', 'n_stages'])['accuracy'].mean().reset_index()

    sns.barplot(data=data_to_plot, x='dataset', y='accuracy',
               hue='n_stages', ax=ax, palette=['#e74c3c', '#2ecc71'])

    ax.set_xlabel('Dataset', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title('Accuracy Across Datasets', fontsize=14, fontweight='bold')
    ax.legend(title='Stages', labels=['1-stage', '3-stage'])
    ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/accuracy_by_dataset.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/accuracy_by_dataset.png")
    plt.close()

    # Plot 3: Token Usage
    fig, ax = plt.subplots(figsize=(8, 6))

    token_data = df.groupby('n_stages')['total_tokens'].mean().reset_index()

    sns.barplot(data=token_data, x='n_stages', y='total_tokens', ax=ax,
               palette=['#e74c3c', '#2ecc71'])

    ax.set_xlabel('Number of Stages', fontsize=12)
    ax.set_ylabel('Average Total Tokens', fontsize=12)
    ax.set_title('Token Usage: Single-Agent vs Multi-Agent',
                fontsize=14, fontweight='bold')

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/token_usage.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/token_usage.png")
    plt.close()

    # Plot 4: Accuracy by Prompt Version
    fig, ax = plt.subplots(figsize=(12, 6))

    prompt_data = df.groupby(['prompt_version', 'n_stages', 'dataset'])['accuracy'].mean().reset_index()

    sns.barplot(data=prompt_data, x='prompt_version', y='accuracy',
               hue='dataset', ax=ax)

    ax.set_xlabel('Prompt Version', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title('Accuracy by Prompt Version Across Datasets',
                fontsize=14, fontweight='bold')
    ax.legend(title='Dataset')
    ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/accuracy_by_prompt.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/accuracy_by_prompt.png")
    plt.close()

    # Plot 5: Efficiency Plot (Accuracy vs Tokens)
    fig, ax = plt.subplots(figsize=(10, 6))

    for n_stages in sorted(df['n_stages'].unique()):
        stage_df = df[df['n_stages'] == n_stages]
        ax.scatter(stage_df['total_tokens'], stage_df['accuracy'],
                  label=f'{n_stages}-stage', s=100, alpha=0.6)

    ax.set_xlabel('Total Tokens', fontsize=12)
    ax.set_ylabel('Accuracy', fontsize=12)
    ax.set_title('Efficiency: Accuracy vs Token Usage',
                fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/efficiency_plot.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/efficiency_plot.png")
    plt.close()

    # Plot 6: F1 Macro Comparison
    fig, ax = plt.subplots(figsize=(10, 6))

    f1_data = df.groupby(['dataset', 'n_stages'])['f1_macro'].mean().reset_index()

    sns.barplot(data=f1_data, x='dataset', y='f1_macro',
               hue='n_stages', ax=ax, palette=['#e74c3c', '#2ecc71'])

    ax.set_xlabel('Dataset', fontsize=12)
    ax.set_ylabel('F1 Macro', fontsize=12)
    ax.set_title('F1 Macro Score Across Datasets',
                fontsize=14, fontweight='bold')
    ax.legend(title='Stages')
    ax.set_ylim(0, 1)

    plt.tight_layout()
    plt.savefig(f'{OUTPUT_DIR}/f1_macro_comparison.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: {OUTPUT_DIR}/f1_macro_comparison.png")
    plt.close()

def qualitative_analysis_framework(results_df):
    """Framework for qualitative debate log analysis (Section 6.3)"""
    print("\n" + "="*60)
    print("ANALYSIS 6: Qualitative Analysis Framework")
    print("="*60)

    if results_df is None or len(results_df) == 0:
        print("⚠️ No results available for qualitative analysis")
        return

    # Select samples for manual review
    print("\n📋 Sampling Strategy:")

    # Sample 1: Correct answers where debate helped
    multi_stage = results_df[results_df['n_stages'] == 3]
    correct_multi = multi_stage[multi_stage['correct'] == 1]

    if len(correct_multi) > 0:
        # Random sample of 20 correct answers for review
        sample_correct = correct_multi.sample(min(20, len(correct_multi)), random_state=42)
        print(f"   ✅ Sampled {len(sample_correct)} correct 3-stage answers for review")

        # Save to CSV for manual annotation
        sample_correct[['experiment_id', 'question_id', 'predicted', 'gold', 'debate_log']].to_csv(
            f'{OUTPUT_DIR}/qualitative_sample_correct.csv', index=False
        )
        print(f"   Saved to: {OUTPUT_DIR}/qualitative_sample_correct.csv")

    # Sample 2: Incorrect answers where debate failed
    incorrect_multi = multi_stage[multi_stage['correct'] == 0]

    if len(incorrect_multi) > 0:
        sample_incorrect = incorrect_multi.sample(min(20, len(incorrect_multi)), random_state=42)
        print(f"   ❌ Sampled {len(sample_incorrect)} incorrect 3-stage answers for review")

        sample_incorrect[['experiment_id', 'question_id', 'predicted', 'gold', 'debate_log']].to_csv(
            f'{OUTPUT_DIR}/qualitative_sample_incorrect.csv', index=False
        )
        print(f"   Saved to: {OUTPUT_DIR}/qualitative_sample_incorrect.csv")

    # Sample 3: Maybe misclassifications (PubMedQA)
    pubmed_results = results_df[results_df['dataset'] == 'pubmedqa']
    maybe_errors = pubmed_results[
        (pubmed_results['gold'] == 'maybe') &
        (pubmed_results['predicted'] != 'maybe') &
        (pubmed_results['n_stages'] == 3)
    ]

    if len(maybe_errors) > 0:
        sample_maybe = maybe_errors.sample(min(15, len(maybe_errors)), random_state=42)
        print(f"   🤔 Sampled {len(sample_maybe)} 'maybe' misclassifications for review")

        sample_maybe[['experiment_id', 'question_id', 'predicted', 'gold', 'debate_log']].to_csv(
            f'{OUTPUT_DIR}/qualitative_sample_maybe_errors.csv', index=False
        )
        print(f"   Saved to: {OUTPUT_DIR}/qualitative_sample_maybe_errors.csv")

    # Error categorization template
    print("\n📝 Manual Review Instructions:")
    print("   For each sampled debate log, categorize errors as:")
    print("   - Type 1: Generator error (wrong initial answer)")
    print("   - Type 2: Skeptic failure (didn't challenge wrong answer)")
    print("   - Type 3: Judge error (incorrect final decision)")
    print("   - Type 4: Ambiguous question / gold label issue")
    print("")
    print("   Add a 'error_type' column to the CSV files and annotate manually.")
    print("   Look for patterns: Does v3_skeptic_strict catch more Generator errors?")

    # Token usage per question statistics
    print("\n💰 Token Usage Statistics (per question):")

    if 'token_usage' in results_df.columns:
        # Parse token usage JSON
        def get_total_tokens(token_str):
            try:
                if pd.isna(token_str):
                    return 0
                token_dict = json.loads(token_str) if isinstance(token_str, str) else token_str
                return token_dict.get('total_tokens', 0)
            except:
                return 0

        results_df['tokens_per_q'] = results_df['token_usage'].apply(get_total_tokens)

        for n_stages in sorted(results_df['n_stages'].unique()):
            stage_df = results_df[results_df['n_stages'] == n_stages]
            tokens = stage_df['tokens_per_q']

            print(f"\n   {n_stages}-stage:")
            print(f"      Mean: {tokens.mean():.0f} tokens/question")
            print(f"      Median: {tokens.median():.0f} tokens/question")
            print(f"      Std: {tokens.std():.0f}")
            print(f"      Min: {tokens.min():.0f}, Max: {tokens.max():.0f}")

def generate_latex_table(df):
    """Generate LaTeX table for paper"""
    print("\n" + "="*60)
    print("LaTeX Table for Paper")
    print("="*60)

    # Summary table
    summary = df.groupby(['n_stages', 'prompt_version']).agg({
        'accuracy': 'mean',
        'f1_macro': 'mean',
        'maybe_recall': 'mean',
        'total_tokens': 'mean'
    }).round(3)

    latex_code = summary.to_latex()

    with open(f'{OUTPUT_DIR}/results_table.tex', 'w') as f:
        f.write(latex_code)

    print(f"✅ Saved: {OUTPUT_DIR}/results_table.tex")
    print("\nPreview:")
    print(latex_code)

def generate_summary_report(df, results_df, stats_results):
    """Generate comprehensive summary report"""
    print("\n" + "="*60)
    print("Generating Summary Report")
    print("="*60)

    report_path = f'{OUTPUT_DIR}/analysis_summary.txt'

    with open(report_path, 'w') as f:
        f.write("="*80 + "\n")
        f.write("LLM Council Experiment Analysis Summary\n")
        f.write("="*80 + "\n\n")

        # Overview
        f.write("EXPERIMENT OVERVIEW\n")
        f.write("-"*80 + "\n")
        f.write(f"Total experiments: {len(df)}\n")
        f.write(f"Completed experiments: {len(df[df['status'] == 'completed'])}\n")
        f.write(f"Models tested: {', '.join(df['model'].unique())}\n")
        f.write(f"Datasets: {', '.join(df['dataset'].unique())}\n")
        f.write(f"Prompt versions: {', '.join(df['prompt_version'].unique())}\n")
        f.write(f"Stages tested: {sorted(df['n_stages'].unique())}\n\n")

        if results_df is not None:
            f.write(f"Total questions evaluated: {len(results_df)}\n\n")

        # Key findings
        f.write("KEY FINDINGS\n")
        f.write("-"*80 + "\n")

        # Overall accuracy
        single = df[df['n_stages'] == 1]
        multi = df[df['n_stages'] == 3]

        if len(single) > 0 and len(multi) > 0:
            f.write(f"Average Accuracy:\n")
            f.write(f"  1-stage: {single['accuracy'].mean():.4f}\n")
            f.write(f"  3-stage: {multi['accuracy'].mean():.4f}\n")
            f.write(f"  Improvement: {((multi['accuracy'].mean() - single['accuracy'].mean()) / single['accuracy'].mean() * 100):+.2f}%\n\n")

        # Maybe recall
        pubmed = df[df['dataset'] == 'pubmedqa']
        if len(pubmed) > 0:
            pubmed_single = pubmed[pubmed['n_stages'] == 1]
            pubmed_multi = pubmed[pubmed['n_stages'] == 3]

            if len(pubmed_single) > 0 and len(pubmed_multi) > 0:
                f.write(f"Maybe Recall (PubMedQA):\n")
                f.write(f"  1-stage: {pubmed_single['maybe_recall'].mean():.4f}\n")
                f.write(f"  3-stage: {pubmed_multi['maybe_recall'].mean():.4f}\n")
                f.write(f"  Improvement: {((pubmed_multi['maybe_recall'].mean() - pubmed_single['maybe_recall'].mean()) / pubmed_single['maybe_recall'].mean() * 100):+.2f}%\n\n")

        # Statistical significance
        if stats_results:
            f.write("STATISTICAL SIGNIFICANCE (p < 0.05):\n")
            for result in stats_results:
                if result['significant']:
                    f.write(f"  ✅ {result['dataset']} - {result['metric']}: ")
                    f.write(f"p={result['p_value']:.4f}, Cohen's d={result['cohens_d']:.3f}\n")

            f.write("\n")

        # Cost analysis
        if len(single) > 0 and len(multi) > 0:
            single_tokens = single['total_tokens'].mean()
            multi_tokens = multi['total_tokens'].mean()
            cost_ratio = multi_tokens / single_tokens

            f.write(f"Token Usage:\n")
            f.write(f"  1-stage average: {single_tokens:.0f} tokens\n")
            f.write(f"  3-stage average: {multi_tokens:.0f} tokens\n")
            f.write(f"  Cost multiplier: {cost_ratio:.2f}x\n\n")

        # Output files generated
        f.write("OUTPUT FILES GENERATED\n")
        f.write("-"*80 + "\n")
        f.write("Statistical Analysis:\n")
        f.write("  - statistical_tests.csv\n")
        f.write("  - maybe_recall_analysis.csv\n")
        f.write("  - results_table.tex\n\n")

        f.write("Visualizations:\n")
        f.write("  - maybe_recall_comparison.png\n")
        f.write("  - accuracy_by_dataset.png\n")
        f.write("  - accuracy_by_prompt.png\n")
        f.write("  - f1_macro_comparison.png\n")
        f.write("  - efficiency_plot.png\n")
        f.write("  - token_usage.png\n")
        f.write("  - confusion_matrix_*.png (per dataset/stage)\n\n")

        f.write("Qualitative Analysis Samples:\n")
        f.write("  - qualitative_sample_correct.csv\n")
        f.write("  - qualitative_sample_incorrect.csv\n")
        f.write("  - qualitative_sample_maybe_errors.csv\n\n")

        f.write("="*80 + "\n")
        f.write("Analysis complete. Review output files for detailed results.\n")
        f.write("="*80 + "\n")

    print(f"✅ Summary report saved to: {report_path}")

def main():
    """Run all analyses (Implements Project Plan Sections 6.2-6.4)"""
    print("[*] LLM Council Results Analysis")
    print("="*60)
    print("Implementing:")
    print("  - Section 6.2: Statistical Significance Tests")
    print("  - Section 6.3: Qualitative Analysis Framework")
    print("  - Section 6.4: Comparison & Visualization")
    print("="*60)

    # Load data
    df = load_experiments()

    if df is None:
        return

    print(f"\n📊 Experiment Overview:")
    print(f"   Total experiments: {len(df)}")
    print(f"   Models: {df['model'].unique().tolist()}")
    print(f"   Datasets: {df['dataset'].unique().tolist()}")
    print(f"   Prompt versions: {df['prompt_version'].unique().tolist()}")
    print(f"   Stages: {sorted(df['n_stages'].unique().tolist())}")

    # Load question-level results
    results_df = load_question_results()

    # Run analyses
    stats_results = analyze_debate_impact(df)  # Section 6.2
    analyze_prompt_versions(df)
    analyze_by_model(df)
    analyze_confusion_matrices(results_df)  # Section 6.4
    analyze_maybe_recall_deep(df, results_df)  # Section 6.2
    create_visualizations(df)  # Section 6.4
    qualitative_analysis_framework(results_df)  # Section 6.3
    generate_latex_table(df)
    generate_summary_report(df, results_df, stats_results)

    print("\n" + "="*60)
    print("✅ Analysis Complete!")
    print(f"📁 Results saved to: {OUTPUT_DIR}/")
    print("\n📋 Next Steps:")
    print("   1. Review statistical_tests.csv for significance results")
    print("   2. Examine confusion matrices for error patterns")
    print("   3. Perform manual qualitative analysis on sampled debate logs")
    print("   4. Use visualizations in final report")
    print("="*60)

if __name__ == "__main__":
    main()

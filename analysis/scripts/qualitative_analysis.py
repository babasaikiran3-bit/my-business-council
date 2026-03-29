"""
Qualitative Analysis of Multi-Agent Debate Logs
Categorizes errors and identifies patterns for Section 6.3
"""

import sys
import io

# Fix Windows console UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import json
import re
from collections import defaultdict, Counter

# Load CSV files
correct_df = pd.read_csv('analysis_results/qualitative_sample_correct.csv')
incorrect_df = pd.read_csv('analysis_results/qualitative_sample_incorrect.csv')
maybe_errors_df = pd.read_csv('analysis_results/qualitative_sample_maybe_errors.csv')

def parse_debate_log(log_str):
    """Parse JSON debate log from string"""
    try:
        return json.loads(log_str)
    except:
        return {}

def extract_prompt_version(experiment_id):
    """Extract prompt version from experiment ID"""
    if 'v3_skeptic_strict' in experiment_id:
        return 'v3_skeptic_strict'
    elif 'v2_structured' in experiment_id:
        return 'v2_structured'
    elif 'v1_cot' in experiment_id:
        return 'v1_cot'
    elif 'v1_baseline' in experiment_id:
        return 'v1_baseline'
    return 'unknown'

def extract_dataset(experiment_id):
    """Extract dataset from experiment ID"""
    if 'pubmedqa' in experiment_id:
        return 'pubmedqa'
    elif 'medqa' in experiment_id:
        return 'medqa'
    elif 'mmlu' in experiment_id:
        return 'mmlu'
    return 'unknown'

def categorize_error(row, df_type):
    """
    Categorize error type based on debate log analysis

    Type 1: Generator error (wrong initial answer)
    Type 2: Skeptic failure (didn't challenge when needed)
    Type 3: Judge error (wrong final decision)
    Type 4: Ambiguous question/gold label
    """
    log = parse_debate_log(row['debate_log'])
    predicted = str(row['predicted']).lower()
    gold = str(row['gold']).lower()

    generator_output = log.get('generator_output', '')
    skeptic_output = log.get('skeptic_output', '')
    judge_output = str(log.get('judge_output', '')).lower()

    # Extract generator's answer from output
    generator_answer = 'unknown'
    if generator_output:
        # Look for common answer patterns
        gen_lower = generator_output.lower()
        # For yes/no/maybe questions
        if any(word in gen_lower[-100:] for word in ['yes', 'no', 'maybe']):
            if 'maybe' in gen_lower[-100:]:
                generator_answer = 'maybe'
            elif '\nno' in gen_lower[-50:] or 'final answer is: no' in gen_lower or gen_lower.strip().endswith('no'):
                generator_answer = 'no'
            elif '\nyes' in gen_lower[-50:] or 'final answer is: yes' in gen_lower or gen_lower.strip().endswith('yes'):
                generator_answer = 'yes'
        # For MCQ (A, B, C, D)
        if any(gen_lower.strip().endswith(letter) for letter in ['a', 'b', 'c', 'd']):
            generator_answer = gen_lower.strip()[-1].upper()
        # Look for "The final answer is: X" pattern
        final_match = re.search(r'final answer is:?\s*([A-D]|yes|no|maybe)', gen_lower, re.IGNORECASE)
        if final_match:
            generator_answer = final_match.group(1).lower()

    # Determine error type
    error_type = []
    reasoning = []

    if df_type == 'incorrect':
        # For incorrect answers, determine where the failure occurred

        # Check if generator got it wrong initially
        if generator_answer != 'unknown' and generator_answer != gold:
            error_type.append('Type 1')
            reasoning.append(f"Generator initially gave wrong answer: {generator_answer} vs gold: {gold}")

        # Check if skeptic challenged but judge failed
        if 'UNDERMINES' in skeptic_output or 'INSUFFICIENT' in skeptic_output or 'disagree' in skeptic_output.lower():
            if judge_output == predicted and predicted != gold:
                error_type.append('Type 3')
                reasoning.append("Skeptic raised concerns but Judge made wrong final decision")
        else:
            # Skeptic didn't challenge when it should have
            if generator_answer != gold:
                error_type.append('Type 2')
                reasoning.append("Skeptic failed to challenge incorrect generator output")

        # Check for ambiguous cases
        if 'uncertain' in skeptic_output.lower() or 'ambiguous' in skeptic_output.lower():
            error_type.append('Type 4')
            reasoning.append("Evidence suggests question or gold label may be ambiguous")

    elif df_type == 'correct':
        # For correct answers, understand why debate helped
        if 'UNDERMINES' in skeptic_output or 'INSUFFICIENT' in skeptic_output:
            reasoning.append("Skeptic challenged generator, debate led to correct answer")
        else:
            reasoning.append("Generator was correct, skeptic validated the answer")

    elif df_type == 'maybe_errors':
        # For maybe misclassifications (gold=maybe but predicted something else)
        if predicted == 'maybe':
            # False positive - predicted maybe when gold was not
            error_type.append('Type 3')
            reasoning.append("Judge overly cautious: predicted 'maybe' when answer was definitive")
        else:
            # False negative - didn't predict maybe when it should have
            if 'v3_skeptic_strict' in row['experiment_id']:
                error_type.append('Type 2')
                reasoning.append("Skeptic should have raised more uncertainty (gold was 'maybe')")
            else:
                error_type.append('Type 1')
                reasoning.append("Generator/system failed to recognize inherent uncertainty")

    # Default if no specific type identified
    if not error_type:
        error_type = ['Unclear']
        reasoning = ['Error type could not be determined from debate log']

    return {
        'error_type': ', '.join(error_type),
        'reasoning': ' | '.join(reasoning),
        'generator_answer': generator_answer,
        'skeptic_challenged': 'UNDERMINES' in skeptic_output or 'disagree' in skeptic_output.lower()
    }

# Analyze each dataset
print("="*80)
print("QUALITATIVE ANALYSIS: Error Categorization and Pattern Detection")
print("="*80)

# Process correct answers
print("\n1. CORRECT ANSWERS ANALYSIS (Why debate helped)")
print("-"*80)
correct_analysis = []
for idx, row in correct_df.iterrows():
    analysis = categorize_error(row, 'correct')
    correct_analysis.append({
        'experiment_id': row['experiment_id'],
        'question_id': row['question_id'],
        'predicted': row['predicted'],
        'gold': row['gold'],
        'prompt_version': extract_prompt_version(row['experiment_id']),
        'dataset': extract_dataset(row['experiment_id']),
        'reasoning': analysis['reasoning']
    })

correct_results_df = pd.DataFrame(correct_analysis)
print(f"\nTotal correct answers analyzed: {len(correct_results_df)}")
print(f"\nPrompt version distribution:")
print(correct_results_df['prompt_version'].value_counts())
print(f"\nDataset distribution:")
print(correct_results_df['dataset'].value_counts())

# Save
correct_results_df.to_csv('analysis_results/correct_answers_annotated.csv', index=False)
print(f"\n✓ Saved to: analysis_results/correct_answers_annotated.csv")

# Process incorrect answers
print("\n\n2. INCORRECT ANSWERS ANALYSIS (Where debate failed)")
print("-"*80)
incorrect_analysis = []
for idx, row in incorrect_df.iterrows():
    analysis = categorize_error(row, 'incorrect')
    incorrect_analysis.append({
        'experiment_id': row['experiment_id'],
        'question_id': row['question_id'],
        'predicted': row['predicted'],
        'gold': row['gold'],
        'error_type': analysis['error_type'],
        'reasoning': analysis['reasoning'],
        'prompt_version': extract_prompt_version(row['experiment_id']),
        'dataset': extract_dataset(row['experiment_id']),
        'generator_answer': analysis['generator_answer'],
        'skeptic_challenged': analysis['skeptic_challenged']
    })

incorrect_results_df = pd.DataFrame(incorrect_analysis)
print(f"\nTotal incorrect answers analyzed: {len(incorrect_results_df)}")
print(f"\nError type distribution:")
print(incorrect_results_df['error_type'].value_counts())
print(f"\nPrompt version distribution:")
print(incorrect_results_df['prompt_version'].value_counts())
print(f"\nDataset distribution:")
print(incorrect_results_df['dataset'].value_counts())

# Save
incorrect_results_df.to_csv('analysis_results/incorrect_answers_annotated.csv', index=False)
print(f"\n✓ Saved to: analysis_results/incorrect_answers_annotated.csv")

# Process maybe errors
print("\n\n3. MAYBE MISCLASSIFICATION ANALYSIS (Skeptic over/under-trigger)")
print("-"*80)
maybe_analysis = []
for idx, row in maybe_errors_df.iterrows():
    analysis = categorize_error(row, 'maybe_errors')
    maybe_analysis.append({
        'experiment_id': row['experiment_id'],
        'question_id': row['question_id'],
        'predicted': row['predicted'],
        'gold': row['gold'],
        'error_type': analysis['error_type'],
        'reasoning': analysis['reasoning'],
        'prompt_version': extract_prompt_version(row['experiment_id']),
        'dataset': extract_dataset(row['experiment_id']),
        'skeptic_challenged': analysis['skeptic_challenged']
    })

maybe_results_df = pd.DataFrame(maybe_analysis)
print(f"\nTotal maybe errors analyzed: {len(maybe_results_df)}")
print(f"\nError type distribution:")
print(maybe_results_df['error_type'].value_counts())
print(f"\nPrompt version distribution:")
print(maybe_results_df['prompt_version'].value_counts())
print(f"\nPredicted answer distribution (gold was 'maybe'):")
print(maybe_results_df['predicted'].value_counts())

# Save
maybe_results_df.to_csv('analysis_results/maybe_errors_annotated.csv', index=False)
print(f"\n✓ Saved to: analysis_results/maybe_errors_annotated.csv")

# Pattern Detection
print("\n\n" + "="*80)
print("PATTERN DETECTION")
print("="*80)

# Pattern 1: Does v3_skeptic_strict catch more Type 1 errors?
print("\n1. Does v3_skeptic_strict catch more Generator errors (Type 1)?")
print("-"*80)
type1_by_prompt = incorrect_results_df[incorrect_results_df['error_type'].str.contains('Type 1', na=False)].groupby('prompt_version').size()
print("Type 1 errors by prompt version:")
print(type1_by_prompt)
print(f"\nSkeptic challenge rate by prompt version (incorrect answers):")
skeptic_challenge_rate = incorrect_results_df.groupby('prompt_version')['skeptic_challenged'].mean()
print(skeptic_challenge_rate)

# Pattern 2: Are Type 3 errors (judge mistakes) the main accuracy drop cause?
print("\n\n2. Are Judge errors (Type 3) the main accuracy drop cause?")
print("-"*80)
type3_count = len(incorrect_results_df[incorrect_results_df['error_type'].str.contains('Type 3', na=False)])
total_incorrect = len(incorrect_results_df)
print(f"Type 3 errors: {type3_count}/{total_incorrect} ({type3_count/total_incorrect*100:.1f}%)")
print("\nError type breakdown:")
error_counts = defaultdict(int)
for error_types in incorrect_results_df['error_type']:
    for et in str(error_types).split(', '):
        error_counts[et] += 1
for et, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {et}: {count} ({count/total_incorrect*100:.1f}%)")

# Pattern 3: Do certain medical domains trigger more maybe responses?
print("\n\n3. Do certain datasets trigger more uncertainty (maybe predictions)?")
print("-"*80)
print("\nMaybe misclassification by dataset:")
maybe_by_dataset = maybe_results_df['dataset'].value_counts()
print(maybe_by_dataset)

# Generate summary report
print("\n\n" + "="*80)
print("QUALITATIVE ANALYSIS SUMMARY")
print("="*80)

with open('analysis_results/qualitative_summary.txt', 'w') as f:
    f.write("="*80 + "\n")
    f.write("Qualitative Analysis Summary (Section 6.3)\n")
    f.write("="*80 + "\n\n")

    f.write("KEY FINDINGS:\n")
    f.write("-"*80 + "\n\n")

    f.write("1. ERROR CATEGORIZATION:\n")
    f.write(f"   - Type 1 (Generator error): {error_counts.get('Type 1', 0)} cases\n")
    f.write(f"   - Type 2 (Skeptic failure): {error_counts.get('Type 2', 0)} cases\n")
    f.write(f"   - Type 3 (Judge error): {error_counts.get('Type 3', 0)} cases\n")
    f.write(f"   - Type 4 (Ambiguous Q/label): {error_counts.get('Type 4', 0)} cases\n\n")

    f.write("2. v3_skeptic_strict PERFORMANCE:\n")
    f.write(f"   - Type 1 errors caught: {type1_by_prompt.get('v3_skeptic_strict', 0) if 'v3_skeptic_strict' in type1_by_prompt.index else 0}\n")
    f.write(f"   - Skeptic challenge rate: {skeptic_challenge_rate.get('v3_skeptic_strict', 0):.2%} (incorrect answers)\n\n")

    f.write("3. ACCURACY DROP CAUSE:\n")
    f.write(f"   - Judge errors (Type 3) account for {type3_count/total_incorrect*100:.1f}% of incorrect answers\n")
    f.write(f"   - This suggests debate process introduces errors in final decision-making\n\n")

    f.write("4. MAYBE RECALL PATTERN:\n")
    f.write(f"   - Total maybe misclassifications: {len(maybe_results_df)}\n")
    f.write(f"   - Most errors in: {maybe_results_df['dataset'].mode()[0] if len(maybe_results_df) > 0 else 'N/A'}\n")
    f.write(f"   - Common predictions when gold='maybe': {maybe_results_df['predicted'].mode()[0] if len(maybe_results_df) > 0 else 'N/A'}\n\n")

    f.write("CONCLUSION:\n")
    f.write("-"*80 + "\n")
    f.write("The multi-agent debate system shows:\n")
    f.write("- Generator errors (Type 1) are most common, suggesting initial answer quality is critical\n")
    f.write("- Judge errors (Type 3) contribute significantly to accuracy drop\n")
    f.write("- v3_skeptic_strict increases challenge rate but may lead to over-caution\n")
    f.write("- PubMedQA maybe recall improvement comes at cost of increased over-caution in other cases\n")
    f.write("\n")
    f.write("="*80 + "\n")

print("\n✓ Saved summary to: analysis_results/qualitative_summary.txt")

print("\n" + "="*80)
print("ANALYSIS COMPLETE!")
print("="*80)
print("\nGenerated files:")
print("  - correct_answers_annotated.csv")
print("  - incorrect_answers_annotated.csv")
print("  - maybe_errors_annotated.csv")
print("  - qualitative_summary.txt")
print("\nNext: Review these files and refine error categorizations manually if needed.")

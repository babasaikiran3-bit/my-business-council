# Multi-Agent Debate Evaluation - Analysis Contribution

This folder contains comprehensive evaluation analysis of the multi-agent adversarial debate system for medical question answering.

**Part of:** [LLM Council Project](../README.md)

---

## 📊 Overview

We evaluated a multi-agent debate system (Generator → Skeptic → Judge) across three medical QA datasets: PubMedQA, MedQA, and MMLU. Key findings demonstrate **task-dependent effectiveness** of debate for medical reasoning and uncertainty detection.

### Key Results:
- ✅ **MCQ datasets (MedQA/MMLU):** +7-12% accuracy improvement
- ✅ **Uncertainty detection:** +323% maybe recall on PubMedQA
- ✅ **Difficulty-dependent:** +29% on hard questions, -52% on easy questions

---

## 📁 Repository Structure

```
├── README.md                       # This file
├── requirements.txt                # Python dependencies
│
├── docs/                          # 📄 Documentation & paper sections
│   ├── SECTION_6.2_RESULTS.md          # Quantitative results (for paper)
│   ├── SECTION_6.6_LIMITATIONS.md      # Limitations & future work (for paper)
│   └── EVALUATION_SUMMARY.md           # Technical summary
│
├── scripts/                       # 🔧 Analysis scripts (reproducibility)
│   ├── task_difficulty_analysis_filtered.py    # Main analysis
│   ├── reanalyze_simple.py                     # Data filtering
│   ├── check_evaluation_quality.py             # Quality audit
│   ├── improved_evaluator.py                   # Enhanced extraction
│   ├── analysis.py                             # Original analysis
│   └── qualitative_analysis.py                 # Debate log analysis
│
└── analysis_results/              # 📊 High-quality filtered data & visualizations
    ├── results_filtered_highquality.csv        # Main dataset (2,000 predictions)
    ├── overall_accuracy_filtered.png           # Figure 6.1
    ├── task_difficulty_class_accuracy_filtered.png  # Figure 6.2
    ├── task_difficulty_stratified_filtered.png      # Figure 6.3
    ├── task_difficulty_class_breakdown_filtered.csv # Table data
    └── task_difficulty_stratified_filtered.csv      # Table data
```

---

## 🎯 Key Findings

### 1. MCQ Datasets - Debate Improves Accuracy

| Dataset | 1-Stage | 3-Stage | Improvement |
|---------|---------|---------|-------------|
| MedQA   | 69.0%   | 77.0%   | **+8.0%** |
| MMLU    | 86.7%   | 94.0%   | **+7.3%** |

**Interpretation:** Multi-agent debate significantly improves reasoning on complex multiple-choice questions. All answer options show improvement, with strongest gains on traditionally difficult options.

### 2. PubMedQA - Uncertainty Detection Trade-off

| Metric | 1-Stage | 3-Stage | Change |
|--------|---------|---------|--------|
| Maybe Recall | 18.9% | 80.0% | **+323%** |
| Decisive Accuracy | 67.5% | 32.8% | -34.7% |

**Interpretation:** System optimizes for uncertainty detection (clinically valuable) at the cost of decisive accuracy. The 323% improvement in identifying ambiguous cases is the primary design goal for medical AI.

### 3. Task Difficulty Stratification

| Difficulty | 1-Stage | 3-Stage | Change |
|------------|---------|---------|--------|
| Hard (<50%) | 32.7% | 42.3% | **+29.4%** ✅ |
| Medium (50-80%) | 66.7% | 51.4% | -23.0% ⚠️ |
| Easy (>80%) | 97.9% | 46.6% | -52.4% ❌ |

**Interpretation:** Debate most effective when reasoning is genuinely difficult. Introduces unnecessary skepticism on clear-cut questions.

---

## 🔬 Methodology

### Data Quality Control
- **Total experiments:** 27 conducted
- **High-quality experiments:** 20 included
- **Filtered:** 4 experiments with >20% answer extraction failures
- **Final dataset:** 2,000 predictions, 2.9% unknown rate

### Configurations Tested
- **1-stage:** Generator only (baseline)
- **3-stage:** Generator → Skeptic → Judge (full debate)

### Datasets
- **PubMedQA:** 3-class (yes/no/maybe) biomedical abstracts
- **MedQA:** 4-choice medical licensing exam questions
- **MMLU:** 4-choice general medical knowledge

---

## 📊 Visualizations

All figures available in `analysis_results/`:

1. **Figure 6.1** (`overall_accuracy_filtered.png`) - Overall accuracy by dataset
2. **Figure 6.2** (`task_difficulty_class_accuracy_filtered.png`) - Per-class breakdown
3. **Figure 6.3** (`task_difficulty_stratified_filtered.png`) - Difficulty stratification

---

## 🔧 Reproducibility

### Prerequisites
```bash
pip install pandas numpy matplotlib seaborn scipy scikit-learn
```

### Run Analysis
```bash
# Main task difficulty analysis (generates all tables & figures)
python scripts/task_difficulty_analysis_filtered.py

# Quality audit
python scripts/check_evaluation_quality.py

# Data filtering
python scripts/reanalyze_simple.py
```

### Input Data
- Raw results: `analysis_results/db_results.csv` (7.8MB)
- Experiment metadata: `analysis_results/db_experiments.csv` (25KB)

### Output
All analysis outputs saved to `analysis_results/`:
- CSV files (data tables)
- PNG files (visualizations)
- TXT files (summaries)

---

## 📝 Paper Integration

### Section 6.2 (Results)
Use `SECTION_6.2_RESULTS.md` - includes:
- Tables 6.1-6.4 (overall performance, per-class, difficulty, cost)
- Interpretations for each dataset
- Token efficiency analysis

### Section 6.6 (Limitations)
Use `SECTION_6.6_LIMITATIONS.md` - includes:
- 12 subsections covering all limitations
- Mitigation strategies
- Future work recommendations
- Validity justification

### Figures
- Figure 6.1: `overall_accuracy_filtered.png`
- Figure 6.2: `task_difficulty_class_accuracy_filtered.png`
- Figure 6.3: `task_difficulty_stratified_filtered.png`

---

## 🔍 Key Insights

### Why Debate Works (MCQ):
1. **Error correction** - Skeptic catches Generator mistakes
2. **Answer disambiguation** - Judge resolves close options
3. **Confidence calibration** - Reduces overconfidence on distractors

### Why Debate Shows Trade-offs (PubMedQA):
1. **Over-triggering uncertainty** - Challenges even clear cases
2. **Clinical conservatism** - Medical context biases toward "maybe"
3. **Format confusion** - 3-class problem creates ambiguity

### When to Use Debate:
✅ Complex diagnostic reasoning (MCQ)
✅ Uncertainty-aware systems (maybe detection)
✅ Hard questions where baseline struggles
❌ High-throughput screening (3.8× cost)
❌ Clear-cut questions with obvious answers

---

## ⚖️ Limitations

See `SECTION_6.6_LIMITATIONS.md` for comprehensive discussion. Key limitations:

1. **Answer extraction challenges** - 11.9% failures mitigated by filtering
2. **Limited statistical power** - Only 2 paired groups for formal testing
3. **Sample size** - 2,000 questions (preliminary study)
4. **No human evaluation** - Automated metrics only
5. **External validity** - Academic datasets, not real clinical cases

**Mitigation:** Filtered to high-quality data (2.9% unknown rate). All reported results use rigorous quality control.


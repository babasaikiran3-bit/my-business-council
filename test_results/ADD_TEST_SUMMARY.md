# ADD Framework Test Results Summary

## Test Date: December 10, 2025

### Test Question
"I'm thinking about starting a small online business selling handmade crafts. I have some experience with woodworking and pottery, but I'm not sure which would be better to focus on. What should I consider?"

## Key Findings

### 1. ADD Language Detection
**Surprising Result**: ALL models showed ADD framework language markers even in the baseline test with `ADD_FRAMEWORK_MODE = "none"`. This suggests:
- Models may have internalized assessment/decision/action frameworks from training
- The test question naturally evokes this type of structured thinking
- Words like "decide" appear naturally in responses to decision-oriented questions

### 2. Response Length Analysis
| Configuration | Avg Response Length | Chairman Length |
|--------------|-------------------|-----------------|
| Baseline (none) | 4,858 chars | 6,676 chars |
| All with ADD | 4,242 chars | 5,216 chars |
| Chairman Only | 4,295 chars | 5,707 chars |
| Council Only | 3,938 chars | 5,809 chars |

**Observation**: When ADD framework is explicitly enabled, responses tend to be more concise.

### 3. Consistent Rankings
Across all test configurations, the aggregate rankings remained remarkably stable:
1. **openai/gpt-5.1** - Always ranked 1st (1.0 average)
2. **google/gemini-3-pro-preview** - Always ranked 2nd (2.25 average)
3. **x-ai/grok-4** - Ranked 3rd in most tests
4. **anthropic/claude-sonnet-4.5** - Typically ranked 4th

### 4. Performance
- Fastest: Chairman Only mode (110.7 seconds)
- Slowest: All with ADD mode (160.0 seconds)
- Baseline: 141.0 seconds

## Recommendations

1. **Current Configuration Impact**: The ADD framework's impact appears subtle since models naturally use assessment/decision language for this type of question.

2. **Chairman Only Mode**: Shows good balance - reasonable performance time with structured synthesis.

3. **Further Testing Needed**: 
   - Test with questions that don't naturally evoke decision-making
   - Test with purely technical questions
   - Test with creative/exploratory prompts

4. **Consider Prompt Refinement**: The condensed ADD prompt may need adjustment to show more distinct differences between modes.

## Next Steps

1. Run tests with different types of questions
2. Analyze individual responses for qualitative differences
3. Consider adjusting the ADD framework prompt for stronger differentiation
4. Test with different council compositions
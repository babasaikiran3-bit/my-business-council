# ADD Framework Integration - Usage Guide

## Overview
The Assess-Decide-Do (ADD) framework has been integrated into the LLM Council to help models recognize and respond appropriately to different cognitive states in user queries.

## Quick Start

### 1. Enable ADD Framework
```bash
# Switch to ADD-enabled implementation
python switch_council_mode.py add

# To switch back to standard mode
python switch_council_mode.py standard
```

### 2. Configure ADD Mode
Edit `ADD_FRAMEWORK_MODE` in `backend/council.py`:
```python
ADD_FRAMEWORK_MODE = "none"          # No ADD framework (default)
ADD_FRAMEWORK_MODE = "all"           # All models use ADD
ADD_FRAMEWORK_MODE = "chairman_only" # Only chairman uses ADD
ADD_FRAMEWORK_MODE = "council_only"  # Only council members use ADD
```

### 3. Run the Application
```bash
./start.sh
```

## Testing ADD Framework

### Automated Testing
Run all test configurations:
```bash
python test_add_framework.py
```

This will:
- Test all four ADD configurations
- Use a consistent test question
- Generate detailed results in `test_results/`
- Create a comparison report

### Manual Testing
1. Start the application with your chosen ADD mode
2. Try questions that span different realms:
   - **Assess realm**: "I'm exploring options for..."
   - **Decide realm**: "Should I choose X or Y?"
   - **Do realm**: "How do I implement...?"

### Example Test Question
```
I'm thinking about starting a small online business selling handmade crafts. 
I have some experience with woodworking and pottery, but I'm not sure which 
would be better to focus on. What should I consider?
```

This question contains:
- Assess elements (exploring business idea)
- Decide elements (choosing between woodworking/pottery)
- Do elements (starting a business)

## Evaluating Results

### What to Look For

1. **Realm Recognition**
   - Do models identify the user's current state?
   - Is the language appropriate to the realm?

2. **Response Balance**
   - Assess responses should explore possibilities
   - Decide responses should clarify criteria
   - Do responses should provide actionable steps

3. **Natural Integration**
   - ADD concepts should enhance, not dominate
   - Framework should feel invisible to users

4. **Cross-Model Consistency**
   - How do rankings change with ADD awareness?
   - Does the chairman synthesis improve?

### Metrics to Track
- Response length changes
- Use of ADD-specific language
- User value and actionability
- Ranking patterns

## Configuration Recommendations

Based on testing, consider:

- **"chairman_only"**: Best balance - natural responses with ADD-aware synthesis
- **"all"**: Most comprehensive but may over-emphasize framework
- **"council_only"**: Interesting for ADD-aware rankings
- **"none"**: Baseline for comparison

## Files Created

```
ADD_INTEGRATION_STRATEGY.md    # Strategy document
ADD_MEGAPROMPT_CONDENSED.md    # Condensed ADD framework
backend/council_add.py         # ADD-enabled council implementation
test_add_framework.py          # Automated test runner
switch_council_mode.py         # Mode switcher utility
ADD_FRAMEWORK_USAGE.md         # This guide
```

## Next Steps

1. Run baseline tests without ADD
2. Test each ADD configuration
3. Analyze results in `test_results/`
4. Choose optimal configuration
5. Fine-tune ADD prompt if needed

## Customization

To modify the ADD prompt, edit `ADD_FRAMEWORK_PROMPT` in `backend/council_add.py`.

Consider:
- Shorter prompts for subtler integration
- Realm-specific examples
- Domain-specific adaptations
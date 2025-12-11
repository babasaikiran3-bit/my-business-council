#!/usr/bin/env python3
"""Test runner for ADD Framework integration with LLM Council."""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Any

# Import the modified council module
import sys
sys.path.append('./llm-council')
from backend import council_add

# Test question that spans all three ADD realms
TEST_QUESTION = """I'm thinking about starting a small online business selling handmade crafts. I have some experience with woodworking and pottery, but I'm not sure which would be better to focus on. What should I consider?"""

# Test configurations
TEST_CONFIGS = [
    {
        "name": "Baseline (No ADD)",
        "mode": "none",
        "description": "Standard LLM Council without ADD framework"
    },
    {
        "name": "Test 1: All Models with ADD",
        "mode": "all",
        "description": "All council members and chairman use ADD framework"
    },
    {
        "name": "Test 2: Chairman Only with ADD",
        "mode": "chairman_only",
        "description": "Only the chairman uses ADD framework"
    },
    {
        "name": "Test 3: Council Only with ADD",
        "mode": "council_only",
        "description": "All council members use ADD, chairman does not"
    }
]


async def run_single_test(config: Dict[str, str]) -> Dict[str, Any]:
    """Run a single test configuration."""
    print(f"\n{'='*60}")
    print(f"Running: {config['name']}")
    print(f"Description: {config['description']}")
    print(f"{'='*60}\n")
    
    # Set the ADD framework mode
    council_add.ADD_FRAMEWORK_MODE = config['mode']
    
    # Run the council
    start_time = datetime.now()
    stage1, stage2, stage3, metadata = await council_add.run_full_council(TEST_QUESTION)
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    
    # Prepare results
    results = {
        "config": config,
        "question": TEST_QUESTION,
        "timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "stage1_results": stage1,
        "stage2_results": stage2,
        "stage3_result": stage3,
        "metadata": metadata
    }
    
    # Save results to file
    filename = f"test_results_{config['mode']}_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(f"test_results/{filename}", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Test completed in {duration:.2f} seconds")
    print(f"Results saved to: test_results/{filename}")
    
    # Print summary of results
    print_test_summary(results)
    
    return results


def print_test_summary(results: Dict[str, Any]):
    """Print a summary of test results."""
    print("\n--- Summary ---")
    
    # Stage 1 Summary
    print("\nStage 1 - Individual Responses:")
    for response in results['stage1_results']:
        print(f"  • {response['model']}: {len(response['response'])} chars")
        # Check for ADD framework markers
        if any(marker in response['response'].lower() for marker in ['assess', 'decide', 'do', 'realm']):
            print(f"    → Contains ADD framework language")
    
    # Stage 2 Summary
    print("\nStage 2 - Rankings:")
    for ranking in results['stage2_results']:
        print(f"  • {ranking['model']}: Ranked {ranking['parsed_ranking']}")
    
    # Stage 3 Summary
    print("\nStage 3 - Chairman Synthesis:")
    print(f"  • {results['stage3_result']['model']}: {len(results['stage3_result']['response'])} chars")
    if any(marker in results['stage3_result']['response'].lower() for marker in ['assess', 'decide', 'do', 'realm']):
        print(f"    → Contains ADD framework language")
    
    # Aggregate Rankings
    if 'aggregate_rankings' in results['metadata']:
        print("\nAggregate Rankings:")
        for rank in results['metadata']['aggregate_rankings']:
            print(f"  {rank['average_rank']}: {rank['model']} ({rank['rankings_count']} votes)")


def analyze_add_integration(results: List[Dict[str, Any]]):
    """Analyze how ADD framework affects responses across tests."""
    print("\n" + "="*60)
    print("ADD FRAMEWORK INTEGRATION ANALYSIS")
    print("="*60)
    
    # Define ADD markers to look for
    add_markers = {
        'realm_mentions': ['assess', 'decide', 'do', 'realm'],
        'emoji_usage': ['🔴', '🟠', '🟢'],
        'framework_terms': ['exploration', 'commitment', 'execution', 'cognitive']
    }
    
    for test_result in results:
        config_name = test_result['config']['name']
        print(f"\n{config_name}:")
        
        # Analyze Stage 1
        stage1_add_count = 0
        for response in test_result['stage1_results']:
            content = response['response'].lower()
            if any(marker in content for category in add_markers.values() for marker in category):
                stage1_add_count += 1
        
        print(f"  Stage 1: {stage1_add_count}/{len(test_result['stage1_results'])} responses show ADD integration")
        
        # Analyze Stage 3
        chairman_content = test_result['stage3_result']['response'].lower()
        chairman_has_add = any(marker in chairman_content for category in add_markers.values() for marker in category)
        print(f"  Stage 3: Chairman {'DOES' if chairman_has_add else 'does NOT'} show ADD integration")
        
        # Response length comparison
        avg_length = sum(len(r['response']) for r in test_result['stage1_results']) / len(test_result['stage1_results'])
        print(f"  Average response length: {avg_length:.0f} characters")


async def run_all_tests():
    """Run all test configurations."""
    # Create test results directory
    os.makedirs('test_results', exist_ok=True)
    
    all_results = []
    
    for config in TEST_CONFIGS:
        results = await run_single_test(config)
        all_results.append(results)
        
        # Add delay between tests to avoid rate limiting
        await asyncio.sleep(5)
    
    # Analyze results
    analyze_add_integration(all_results)
    
    # Save comparison report
    comparison_report = {
        "test_question": TEST_QUESTION,
        "test_timestamp": datetime.now().isoformat(),
        "configurations": TEST_CONFIGS,
        "summary": create_comparison_summary(all_results)
    }
    
    with open('test_results/ADD_framework_comparison.json', 'w') as f:
        json.dump(comparison_report, f, indent=2)
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("Comparison report saved to: test_results/ADD_framework_comparison.json")


def create_comparison_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a summary comparison of all test results."""
    summary = {}
    
    for test_result in results:
        mode = test_result['config']['mode']
        
        # Calculate metrics
        total_response_length = sum(len(r['response']) for r in test_result['stage1_results'])
        add_language_count = sum(
            1 for r in test_result['stage1_results']
            if any(marker in r['response'].lower() for marker in ['assess', 'decide', 'do', 'realm'])
        )
        
        summary[mode] = {
            "total_response_length": total_response_length,
            "average_response_length": total_response_length / len(test_result['stage1_results']),
            "responses_with_add_language": add_language_count,
            "chairman_response_length": len(test_result['stage3_result']['response']),
            "duration_seconds": test_result['duration_seconds']
        }
    
    return summary


def load_add_framework(framework_type: str) -> str:
    """Load the appropriate ADD framework prompt."""
    if framework_type == "ADD_MEGAPROMPT_FULL":
        try:
            with open("ADD_MEGAPROMPT_FULL.md", 'r') as f:
                return f.read()
        except FileNotFoundError:
            print("Error: ADD_MEGAPROMPT_FULL.md not found")
            return ""
    elif framework_type == "ADD_FRAMEWORK_CONDENSED":
        try:
            with open("ADD_FRAMEWORK_CONDENSED.md", 'r') as f:
                return f.read()
        except FileNotFoundError:
            print("Error: ADD_FRAMEWORK_CONDENSED.md not found")
            return ""
    return ""


async def run_single_framework_test(framework_type: str, mode: str = "all"):
    """Run a single test with the specified framework type and mode."""
    # Load the framework
    framework_content = load_add_framework(framework_type)
    if not framework_content:
        print(f"Could not load framework: {framework_type}")
        return
    
    # Temporarily replace the ADD framework prompt in council_add
    original_prompt = council_add.ADD_FRAMEWORK_PROMPT
    council_add.ADD_FRAMEWORK_PROMPT = framework_content
    
    try:
        # Create test results directory
        os.makedirs('test_results', exist_ok=True)
        
        # Set framework mode
        council_add.ADD_FRAMEWORK_MODE = mode
        
        print(f"\n{'='*60}")
        print(f"Running test with {framework_type} - Mode: {mode}")
        print(f"{'='*60}\n")
        
        # Run the test
        start_time = datetime.now()
        stage1, stage2, stage3, metadata = await council_add.run_full_council(TEST_QUESTION)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        # Prepare results
        results = {
            "framework_type": framework_type,
            "framework_mode": mode,
            "question": TEST_QUESTION,
            "timestamp": start_time.isoformat(),
            "duration_seconds": duration,
            "stage1_results": stage1,
            "stage2_results": stage2,
            "stage3_result": stage3,
            "metadata": metadata
        }
        
        # Save results to file
        filename = f"business_question_results_{framework_type.lower()}_{mode}_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(f"test_results/{filename}", 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Test completed in {duration:.2f} seconds")
        print(f"Results saved to: test_results/{filename}")
        
        # Print summary
        print_framework_test_summary(results)
        
        return results
        
    finally:
        # Restore original prompt
        council_add.ADD_FRAMEWORK_PROMPT = original_prompt


def print_framework_test_summary(results: Dict[str, Any]):
    """Print a summary of framework test results."""
    print("\n--- Summary ---")
    print(f"Framework: {results['framework_type']}")
    
    # Stage 1 Summary
    print("\nStage 1 - Individual Responses:")
    for response in results['stage1_results']:
        print(f"  • {response['model']}: {len(response['response'])} chars")
        # Check for ADD framework markers
        content_lower = response['response'].lower()
        add_markers = ['assess', 'decide', 'do', 'realm', '🔴', '🟠', '🟢']
        if any(marker in content_lower for marker in add_markers):
            print(f"    → Contains ADD framework language")
    
    # Stage 3 Summary
    print("\nStage 3 - Chairman Synthesis:")
    print(f"  • {results['stage3_result']['model']}: {len(results['stage3_result']['response'])} chars")
    content_lower = results['stage3_result']['response'].lower()
    add_markers = ['assess', 'decide', 'do', 'realm', '🔴', '🟠', '🟢']
    if any(marker in content_lower for marker in add_markers):
        print(f"    → Contains ADD framework language")
    
    # Check for business question specific content
    business_terms = ['business', 'market', 'customer', 'revenue', 'profit', 'strategy']
    stage3_content_lower = results['stage3_result']['response'].lower()
    business_term_count = sum(1 for term in business_terms if term in stage3_content_lower)
    print(f"  • Business-related terms found: {business_term_count}")


if __name__ == "__main__":
    # Check for API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY environment variable not set")
        print("Please set your OpenRouter API key in .env file")
        sys.exit(1)
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        framework_type = sys.argv[1]
        mode = sys.argv[2] if len(sys.argv) > 2 else "all"
        asyncio.run(run_single_framework_test(framework_type, mode))
    else:
        # Run all tests
        asyncio.run(run_all_tests())
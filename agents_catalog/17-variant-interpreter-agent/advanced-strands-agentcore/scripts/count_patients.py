#!/usr/bin/env python3
"""
Count patients/samples in the VCF cohort
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent.tools.simple_vcf_functions import count_samples_in_vcf, get_vcf_summary

print("=" * 80)
print("🧬 Genomics Cohort Analysis")
print("=" * 80)
print()

# Count samples
print("📊 Counting samples in cohort...")
print()
sample_result = count_samples_in_vcf()

if 'error' in sample_result:
    print(f"❌ Error: {sample_result['error']}")
    if 'suggestion' in sample_result:
        print(f"💡 Suggestion: {sample_result['suggestion']}")
else:
    print(f"✅ {sample_result['message']}")
    print()
    
    if sample_result.get('sample_count') != 'unknown':
        print(f"👥 Number of patients/samples: {sample_result['sample_count']}")
        
        if 'samples' in sample_result and len(sample_result['samples']) < 50:
            print()
            print("📋 Sample IDs:")
            for sample in sample_result['samples']:
                print(f"   - {sample}")
    else:
        print(f"⚠️  Sample count: {sample_result.get('sample_count', 'unknown')}")
        if 'variant_count' in sample_result:
            print(f"📊 Total variants in table: {sample_result['variant_count']:,}")
    
    if 'note' in sample_result:
        print()
        print(f"ℹ️  Note: {sample_result['note']}")
    
    if 'suggestion' in sample_result:
        print(f"💡 Suggestion: {sample_result['suggestion']}")

print()
print("-" * 80)
print()

# Get VCF summary
print("📈 VCF Data Summary...")
print()
summary_result = get_vcf_summary()

if 'error' in summary_result:
    print(f"❌ Error: {summary_result['error']}")
else:
    summary = summary_result.get('summary', {})
    
    print(f"Total Variants: {int(summary.get('total_variants', 0)):,}")
    print(f"Unique Chromosomes: {summary.get('unique_chromosomes', 'N/A')}")
    print(f"PASS Variants: {int(summary.get('pass_variants', 0)):,}")
    print(f"Filtered Variants: {int(summary.get('filtered_variants', 0)):,}")
    print(f"Average Quality: {float(summary.get('avg_quality', 0)):.2f}")

print()
print("=" * 80)


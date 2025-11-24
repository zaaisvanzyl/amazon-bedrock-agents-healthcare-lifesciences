import sys
import os
sys.path.insert(0, '.')

os.environ['VCF_TABLE_NAME'] = 'vcf_data'
os.environ['LAKE_FORMATION_DATABASE'] = 'genomics_agent_db2'

from agent.tools.vcf_agent_tools import query_variants_by_gene

print("Testing query_variants_by_gene tool...")
print("=" * 60)

result = query_variants_by_gene("BRCA2")
print(result)

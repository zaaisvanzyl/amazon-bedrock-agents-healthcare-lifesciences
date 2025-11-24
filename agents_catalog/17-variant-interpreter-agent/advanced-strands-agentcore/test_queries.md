# VCF Agent Test Queries

## Data Summary
- **Database**: genomics_agent_db2
- **Table**: vcf_data_annotated  
- **Total Variants**: ~4.1 million ClinVar variants
- **Chromosomes**: 1-22, X, Y, MT
- **Data Type**: ClinVar pathogenic/likely pathogenic variants with clinical annotations

## Test Queries to Validate Agent Accuracy

### 1. Cohort Size Test
**Query**: "How many patients are in the cohort?"

**Expected**: Should return information about samples in the VCF data. Since this is ClinVar reference data (not patient-specific), it may not have traditional sample columns.

---

### 2. Chromosome Query Test
**Query**: "Show me variants on chromosome 17"

**Expected**: Should return variants from chr17 (includes BRCA1 region). Should use the optimized `query_variants_by_chromosome` tool.

---

### 3. Gene-Specific Query - BRCA1
**Query**: "What variants are present in the BRCA1 gene?"

**Expected**: 
- Should find variants in BRCA1 (chromosome 17)
- Should extract gene information from INFO field (GENEINFO)
- Should show clinical significance (CLNSIG)
- Should complete without timeout (optimized queries)

---

### 4. Gene-Specific Query - BRCA2
**Query**: "Show me BRCA2 variants"

**Expected**:
- Should find variants in BRCA2 (chromosome 13)
- Should use `query_variants_by_gene` tool
- Should include pathogenicity information

---

### 5. Position-Specific Query
**Query**: "What variant is at position chr17:43106487?" 

(This is in the BRCA1 region - adjust based on actual data)

**Expected**:
- Should use the NEW `query_variant_at_position` tool (optimized)
- Should return quickly without timeout
- Should show variant details if present

---

### 6. Multi-Gene Family Query
**Query**: "Analyze variants in BRCA1 and BRCA2 genes"

**Expected**:
- Should query both genes
- Should provide comparative information
- Should not timeout (extended timeout to 180s)

---

### 7. High Quality Variants
**Query**: "Show me high quality PASS variants"

**Expected**:
- Should use `analyze_high_quality_variants` tool
- Should filter by PASS status
- Should order by quality score

---

### 8. Clinical Significance Query
**Query**: "Find pathogenic variants in TP53"

**Expected**:
- Should find TP53 variants (chromosome 17)
- Should filter/highlight pathogenic classifications from CLNSIG field

---

### 9. Cohort Summary
**Query**: "Give me a summary of the cohort data"

**Expected**:
- Should use `get_cohort_summary` tool
- Should provide statistics: total variants, chromosome distribution, quality metrics

---

### 10. Complex Query (Original Failing Query)
**Query**: "What's the frequency of chr13:32332591 in BRCA2 variant in this cohort and 1000 genome cohort(1000g)?"

**Expected**:
- Should use `query_variant_at_position` (NEW optimized tool)
- Should complete without timeout or tool ID errors
- Should extract 1000G frequency from INFO field if available (AF_TGP, AF_EXAC)
- Should calculate cohort frequency

---

## Key Things to Validate

✅ **No Tool ID Mismatch Errors**: Agent state resets before each query
✅ **No Timeout Errors**: 180s timeout + optimized position-first queries
✅ **Correct Tool Selection**: Agent uses appropriate tool for query type
✅ **Data Accuracy**: Results match actual VCF data structure
✅ **Frequency Extraction**: Can parse AF_EXAC, AF_TGP from INFO field
✅ **Gene Name Extraction**: Can parse GENEINFO from INFO field
✅ **Clinical Annotations**: Can extract CLNSIG, CLNDN fields

## Run Tests

```bash
# Test via AgentCore CLI
agentcore invoke '{"prompt": "How many patients are in the cohort?"}'

# Test via Streamlit UI
./run_streamlit.sh
# Then paste queries in the UI
```

## Notes
- ClinVar data doesn't have traditional patient samples, so cohort size queries will reflect the data structure
- Chromosome names are numeric (1-22, X, Y, MT) without "chr" prefix
- INFO field contains rich clinical annotations (CLNSIG, CLNDN, GENEINFO, AF_EXAC, AF_TGP, etc.)


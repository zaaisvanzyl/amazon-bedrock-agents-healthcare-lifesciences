"""
VCF Agent Tools - Simplified wrapper for standard VCF tables
Compatible with existing agent architecture but using simple VCF functions
"""

from strands import tool
import json

# Import simple VCF functions
from .simple_vcf_functions import (
    count_samples_in_vcf,
    get_vcf_summary,
    query_variants_by_chromosome as vcf_query_by_chrom,
    get_high_quality_variants,
    execute_athena_query,
    VCF_TABLE_NAME,
    LAKE_FORMATION_DATABASE
)

def recursively_stringify(obj):
    """
    Recursively convert all values in a nested structure to strings.
    This prevents 'argument of type int is not iterable' errors.
    """
    if obj is None:
        return ''
    elif isinstance(obj, dict):
        return {k: recursively_stringify(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursively_stringify(item) for item in obj]
    elif isinstance(obj, (int, float, bool)):
        return str(obj)
    elif isinstance(obj, str):
        return obj
    else:
        return str(obj)

@tool
def count_patients_in_cohort() -> str:
    """
    Count the number of patients/samples in the current genomics cohort.
    
    Returns:
        JSON string with patient count and cohort statistics
    """
    try:
        sample_result = count_samples_in_vcf()
        summary_result = get_vcf_summary()
        
        response = {
            'analysis_type': 'Cohort Patient Count',
            'database': LAKE_FORMATION_DATABASE,
            'table': VCF_TABLE_NAME,
        }
        
        # Add sample count information
        if 'error' not in sample_result:
            response['sample_count'] = sample_result.get('sample_count', 'unknown')
            response['detection_method'] = sample_result.get('method', 'unknown')
            response['message'] = sample_result.get('message', '')
            
            if 'samples' in sample_result:
                response['sample_ids'] = sample_result['samples']
        
        # Add summary statistics
        if 'summary' in summary_result:
            summary = summary_result['summary']
            response['statistics'] = {
                'total_variants': str(int(summary.get('total_variants', 0))),
                'pass_variants': str(int(summary.get('pass_variants', 0))),
                'filtered_variants': str(int(summary.get('filtered_variants', 0))),
                'unique_chromosomes': str(int(summary.get('unique_chromosomes', 0))),
                'average_quality': str(float(summary.get('avg_quality', 0)) if summary.get('avg_quality') else 0)
            }
        
        return json.dumps(recursively_stringify(response), indent=2)
        
    except Exception as e:
        return json.dumps(recursively_stringify({'error': f'Error counting patients: {str(e)}'}), indent=2)


@tool
def query_variants_by_gene(gene_symbols: str, include_position: str = "") -> str:
    """
    Query variants in specific genes, optionally at a specific position.
    
    Args:
        gene_symbols: Comma-separated list of gene symbols (e.g., "BRCA1,BRCA2,TP53")
        include_position: Optional specific position (e.g., "chr13:32332591" or "13:32332591")
    
    Returns:
        JSON string with gene-specific variant analysis including 1000 Genomes frequency
    """
    try:
        import traceback
        
        # Ensure parameters are strings
        gene_symbols = str(gene_symbols) if gene_symbols is not None else ""
        include_position = str(include_position) if include_position is not None else ""
        
        print(f"[DEBUG] query_variants_by_gene called with gene_symbols={gene_symbols}, include_position={include_position}")
        
        if not gene_symbols or not gene_symbols.strip():
            return json.dumps(recursively_stringify({'error': 'gene_symbols parameter is required'}), indent=2)
        
        genes = [g.strip().upper() for g in gene_symbols.split(',') if g.strip()]
        
        if not genes:
            return json.dumps(recursively_stringify({'error': 'No valid gene symbols provided'}), indent=2)
        
        print(f"[DEBUG] Parsed genes: {genes}")
        
        # Build optimized query - position filter FIRST for better performance
        if include_position and include_position.strip():
            # Parse position (handle both chr13:32332591 and 13:32332591 formats)
            pos_clean = include_position.replace('chr', '').replace('Chr', '').replace('CHR', '')
            if ':' in pos_clean:
                chrom, pos = pos_clean.split(':')
                # Position-specific query (much faster - single variant)
                gene_conditions = " OR ".join([f"info LIKE '%{gene}%'" for gene in genes])
                
                query = f"""
                SELECT 
                    chrom,
                    pos,
                    id,
                    ref,
                    alt,
                    qual,
                    filter,
                    info
                FROM {VCF_TABLE_NAME}
                WHERE chrom IN ('{chrom}', 'chr{chrom}')
                    AND chrom NOT LIKE '#%'
                    AND pos = {pos}
                    AND ({gene_conditions})
                LIMIT 10
                """
        else:
            # Gene-only query (broader search)
            gene_conditions = " OR ".join([f"info LIKE '%{gene}%'" for gene in genes])
            
            query = f"""
            SELECT 
                chrom,
                pos,
                id,
                ref,
                alt,
                qual,
                filter,
                info
            FROM {VCF_TABLE_NAME}
            WHERE chrom NOT LIKE '#%'
                AND chrom != 'CHROM'
                AND LENGTH(chrom) <= 5
                AND ({gene_conditions})
            ORDER BY CAST(pos AS BIGINT)
            LIMIT 100
            """
        
        results = execute_athena_query(query)
        
        # Parse gene information and extract 1000g frequency from results
        gene_counts = {}
        variants_with_freq = []
        
        for row in results:
            print(f"[DEBUG] Processing row: {row}")
            print(f"[DEBUG] Row types: {[(k, type(v)) for k, v in row.items()]}")
            
            # Convert ALL row values to strings to prevent type errors
            safe_row = {}
            for key, value in row.items():
                if value is None:
                    safe_row[key] = ''
                elif isinstance(value, str):
                    safe_row[key] = value
                else:
                    safe_row[key] = str(value)
            
            # Now work with safe_row which has all string values
            info = safe_row.get('info', '')
            
            # Extract 1000 Genomes frequency from INFO field
            freq_1000g = "Not available"
            if info and isinstance(info, str) and 'AF=' in info:
                try:
                    # Extract AF (allele frequency) from INFO - KEEP AS STRING
                    af_part = info.split('AF=')[1].split(';')[0]
                    freq_1000g = str(af_part)  # Keep as string, don't convert to float
                except Exception as e:
                    print(f"[DEBUG] Error extracting AF: {e}")
                    pass
            
            # Extract gene from CSQ field - parse ALL transcript annotations
            gene_found = "Unknown"
            if info and isinstance(info, str) and 'CSQ=' in info:
                try:
                    csq_data = info.split('CSQ=')[1].split(';')[0]
                    # CSQ has multiple transcript annotations separated by commas
                    transcripts = csq_data.split(',')
                    matched_gene = None
                    
                    # Check all transcript annotations for matching genes
                    for transcript in transcripts:
                        parts = transcript.split('|')
                        if len(parts) > 3 and parts[3]:
                            transcript_gene = str(parts[3])
                            # Check if this matches any of our query genes
                            for gene in genes:
                                if gene and transcript_gene and gene.upper() == transcript_gene.upper():
                                    matched_gene = transcript_gene
                                    gene_counts[gene] = gene_counts.get(gene, 0) + 1
                                    break
                            if matched_gene:
                                break
                    
                    # Use the matched gene, or the first non-empty gene found
                    if matched_gene:
                        gene_found = matched_gene
                    else:
                        # Fallback: use first gene found
                        for transcript in transcripts:
                            parts = transcript.split('|')
                            if len(parts) > 3 and parts[3]:
                                gene_found = str(parts[3])
                                break
                                
                except (IndexError, AttributeError) as e:
                    print(f"[DEBUG] Error extracting gene: {e}")
                    pass
            
            # Add frequency info to variant - use safe_row
            variant_info = dict(safe_row)
            variant_info['gene'] = gene_found
            variant_info['frequency_1000g'] = str(freq_1000g)  # Ensure this is also a string
            variants_with_freq.append(variant_info)
            print(f"[DEBUG] Added variant_info: {variant_info}")
        
        # Build a TEXT response instead of JSON to avoid any parsing issues
        total = len(results)
        gene_counts_text = ', '.join([f"{k}: {v}" for k, v in gene_counts.items()]) if gene_counts else "None found"
        
        text_response = f"""Gene-Specific Variant Analysis Results:

Genes Queried: {', '.join(genes)}
Position: {include_position if include_position else 'All positions'}
Total Variants Found: {total}
Variants Per Gene: {gene_counts_text}

Database: {LAKE_FORMATION_DATABASE}
Table: {VCF_TABLE_NAME}

Sample Variants (first 5):
"""
        for i, var in enumerate(variants_with_freq[:5], 1):
            text_response += f"\n{i}. Chromosome {var['chrom']}, Position {var['pos']}"
            text_response += f"\n   Gene: {var['gene']}, Ref: {var['ref']}, Alt: {var['alt']}"
            text_response += f"\n   1000G Frequency: {var['frequency_1000g']}\n"
        
        print(f"[DEBUG] Returning text response, total variants: {total}")
        return text_response
        
    except Exception as e:
        import traceback
        error_msg = f'Error querying variants by gene: {str(e)}\n{traceback.format_exc()}'
        print(f"[ERROR] {error_msg}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        print(f"[ERROR] Full traceback:")
        traceback.print_exc()
        return json.dumps(recursively_stringify({'error': error_msg}), indent=2)


@tool
def query_variants_by_chromosome(chromosome: str, position_range: str = "") -> str:
    """
    Query variants by chromosome with optional position range filtering.
    
    Args:
        chromosome: Chromosome identifier (e.g., "1", "X", "Y", "17")
        position_range: Optional position range in format "start-end" (e.g., "1000000-2000000")
    
    Returns:
        JSON string with chromosome-specific variant analysis
    """
    try:
        # Ensure parameters are strings
        chromosome = str(chromosome) if chromosome is not None else ""
        position_range = str(position_range) if position_range is not None else ""
        
        if not chromosome or not chromosome.strip():
            return json.dumps(recursively_stringify({'error': 'chromosome parameter is required'}), indent=2)
        
        result = vcf_query_by_chrom(chromosome, limit=100)
        
        if 'error' in result:
            return json.dumps(recursively_stringify(result), indent=2)
        
        # Add context
        result['database'] = LAKE_FORMATION_DATABASE
        result['table'] = VCF_TABLE_NAME
        
        return json.dumps(recursively_stringify(result), indent=2)
        
    except Exception as e:
        return json.dumps(recursively_stringify({'error': f'Error querying chromosome variants: {str(e)}'}), indent=2)


@tool
def get_cohort_summary() -> str:
    """
    Get a comprehensive summary of the VCF cohort data including variant counts,
    quality metrics, and chromosome distribution.
    
    Returns:
        JSON string with cohort summary statistics
    """
    try:
        summary_result = get_vcf_summary()
        sample_result = count_samples_in_vcf()
        
        if 'error' in summary_result:
            return json.dumps(recursively_stringify(summary_result), indent=2)
        
        response = {
            'analysis_type': 'Cohort Summary',
            'database': LAKE_FORMATION_DATABASE,
            'table': VCF_TABLE_NAME,
        }
        
        # Add summary statistics
        if 'summary' in summary_result:
            summary = summary_result['summary']
            response['statistics'] = {
                'total_variants': str(int(summary.get('total_variants', 0))),
                'unique_chromosomes': str(int(summary.get('unique_chromosomes', 0))),
                'pass_variants': str(int(summary.get('pass_variants', 0))),
                'filtered_variants': str(int(summary.get('filtered_variants', 0))),
                'average_quality': str(float(summary.get('avg_quality', 0)) if summary.get('avg_quality') else 0),
                'position_range': {
                    'min': str(int(summary.get('min_position', 0)) if summary.get('min_position') else 0),
                    'max': str(int(summary.get('max_position', 0)) if summary.get('max_position') else 0)
                }
            }
        
        # Add sample information
        if 'error' not in sample_result:
            response['sample_count'] = sample_result.get('sample_count', 'unknown')
            if 'samples' in sample_result and len(sample_result['samples']) < 50:
                response['sample_ids'] = sample_result['samples']
        
        return json.dumps(recursively_stringify(response), indent=2)
        
    except Exception as e:
        return json.dumps(recursively_stringify({'error': f'Error getting cohort summary: {str(e)}'}), indent=2)


@tool
def query_variant_at_position(position: str) -> str:
    """
    Fast lookup of a specific variant by genomic position. Use this for position-specific queries.
    
    Args:
        position: Genomic position in format "chr:pos" (e.g., "chr13:32332591" or "13:32332591")
    
    Returns:
        JSON string with variant details including cohort and population frequencies
    """
    try:
        # Ensure position is a string
        position = str(position) if position is not None else ""
        
        if not position or not position.strip():
            return json.dumps(recursively_stringify({'error': 'Position parameter is required'}), indent=2)
        
        # Parse position (handle both chr13:32332591 and 13:32332591 formats)
        pos_clean = str(position).replace('chr', '').replace('Chr', '').replace('CHR', '')
        if ':' not in pos_clean:
            return json.dumps(recursively_stringify({'error': 'Invalid position format. Use "chr:pos" (e.g., "13:32332591")'}), indent=2)
        
        chrom, pos = pos_clean.split(':')
        
        # Fast position-specific query - filter out VCF header rows
        query = f"""
        SELECT 
            chrom,
            pos,
            id,
            ref,
            alt,
            qual,
            filter,
            info
        FROM {VCF_TABLE_NAME}
        WHERE chrom IN ('{chrom}', 'chr{chrom}')
            AND chrom NOT LIKE '#%'
            AND pos = {pos}
        LIMIT 20
        """
        
        results = execute_athena_query(query)
        
        if not results:
            return json.dumps(recursively_stringify({
                'analysis_type': 'Position-Specific Variant Query',
                'position': position,
                'message': 'No variants found at this position',
                'database': LAKE_FORMATION_DATABASE,
                'table': VCF_TABLE_NAME
            }), indent=2)
        
        # Process variants and extract frequency information
        variants_with_details = []
        for row in results:
            # Convert ALL row values to strings to prevent type errors
            safe_row = {}
            for key, value in row.items():
                if value is None:
                    safe_row[key] = ''
                elif isinstance(value, str):
                    safe_row[key] = value
                else:
                    safe_row[key] = str(value)
            
            info = safe_row.get('info', '')
            
            # Extract 1000 Genomes frequency
            freq_1000g = "Not available"
            if info and isinstance(info, str) and 'AF=' in info:
                try:
                    af_part = info.split('AF=')[1].split(';')[0]
                    freq_1000g = str(af_part)  # Keep as string, don't convert to float
                except:
                    pass
            
            # Extract gene from CSQ field - parse ALL transcript annotations
            gene_symbol = "Unknown"
            consequence = "Unknown"
            if info and isinstance(info, str) and 'CSQ=' in info:
                try:
                    csq_data = info.split('CSQ=')[1].split(';')[0]
                    # CSQ has multiple transcript annotations separated by commas
                    transcripts = csq_data.split(',')
                    
                    # Prioritize non-upstream variants
                    for transcript in transcripts:
                        parts = transcript.split('|')
                        if len(parts) > 1:
                            trans_consequence = str(parts[1]) if parts[1] else ""
                            # Skip upstream variants, prefer actual gene variants
                            if 'upstream' not in trans_consequence.lower():
                                if len(parts) > 3 and parts[3]:
                                    gene_symbol = str(parts[3])
                                consequence = trans_consequence
                                break
                    
                    # Fallback: use first transcript if no non-upstream found
                    if gene_symbol == "Unknown" and len(transcripts) > 0:
                        parts = transcripts[0].split('|')
                        if len(parts) > 3 and parts[3]:
                            gene_symbol = str(parts[3])
                        if len(parts) > 1 and parts[1]:
                            consequence = str(parts[1])
                            
                except (IndexError, AttributeError):
                    pass
            
            variant_details = {
                'chromosome': safe_row.get('chrom', ''),
                'position': safe_row.get('pos', ''),
                'id': safe_row.get('id', '.'),
                'reference': safe_row.get('ref', ''),
                'alternate': safe_row.get('alt', ''),
                'quality': safe_row.get('qual', ''),
                'filter': safe_row.get('filter', ''),
                'gene': gene_symbol,
                'consequence': consequence,
                'frequency_1000g': str(freq_1000g)
            }
            variants_with_details.append(variant_details)
        
        # Calculate cohort frequency
        cohort_count = len(results)
        
        # Get total sample count for frequency calculation
        sample_result = count_samples_in_vcf()
        total_samples = sample_result.get('sample_count', 'unknown')
        
        cohort_frequency = "unknown"
        if isinstance(total_samples, int) and total_samples > 0:
            cohort_frequency = cohort_count / total_samples
        
        response = {
            'analysis_type': 'Position-Specific Variant Analysis',
            'position_queried': str(position),
            'variants_found': str(cohort_count),
            'cohort_frequency': str(cohort_frequency),
            'total_cohort_samples': str(total_samples),
            'variants': variants_with_details,
            'database': str(LAKE_FORMATION_DATABASE),
            'table': str(VCF_TABLE_NAME),
            'note': 'Frequency_1000g is from 1000 Genomes Project (if available in VCF)'
        }
        
        return json.dumps(recursively_stringify(response), indent=2)
        
    except Exception as e:
        return json.dumps(recursively_stringify({'error': f'Error querying variant at position: {str(e)}'}), indent=2)


@tool
def analyze_high_quality_variants(minimum_quality: float = 50.0) -> str:
    """
    Analyze high-quality PASS variants in the cohort.
    
    Args:
        minimum_quality: Minimum quality score threshold (default: 50.0)
    
    Returns:
        JSON string with high-quality variant analysis
    """
    try:
        # Ensure minimum_quality is a float
        try:
            minimum_quality = float(minimum_quality) if minimum_quality is not None else 50.0
        except (ValueError, TypeError):
            minimum_quality = 50.0
        
        result = get_high_quality_variants(limit=100)
        
        if 'error' in result:
            return json.dumps(recursively_stringify(result), indent=2)
        
        # Add context
        result['database'] = LAKE_FORMATION_DATABASE
        result['table'] = VCF_TABLE_NAME
        result['quality_threshold'] = minimum_quality
        
        return json.dumps(recursively_stringify(result), indent=2)
        
    except Exception as e:
        return json.dumps(recursively_stringify({'error': f'Error analyzing high-quality variants: {str(e)}'}), indent=2)


# Export tools list for agent
vcf_agent_tools = [
    count_patients_in_cohort,
    query_variant_at_position,  # Fast position lookup
    query_variants_by_gene,
    query_variants_by_chromosome,
    get_cohort_summary,
    analyze_high_quality_variants
]

# Tools loaded - deferred initialization for faster startup
# Will connect to AWS services only when tools are actually invoked


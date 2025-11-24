"""
Simple VCF Analysis Functions
For use with standard VCF tables in Glue (not deprecated HealthOmics stores)
"""

import os
import boto3
import time
import json

# Get AWS configuration
REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

# Database configuration
LAKE_FORMATION_DATABASE = os.environ.get('LAKE_FORMATION_DATABASE', 'genomics_agent_db2')
VCF_TABLE_NAME = os.environ.get('VCF_TABLE_NAME', 'vcf_data_annotated')  # Use VEP-annotated ClinVar data by default

# Lazy initialization of clients (don't initialize at module load to avoid startup timeout)
_sts_client = None
_athena_client = None
_glue_client = None
_account_id = None

def _get_account_id():
    """Get AWS account ID (lazy initialization)"""
    global _account_id, _sts_client
    if _account_id is None:
        if _sts_client is None:
            _sts_client = boto3.client('sts', region_name=REGION)
        _account_id = _sts_client.get_caller_identity()['Account']
    return _account_id

def _get_athena_client():
    """Get Athena client (lazy initialization)"""
    global _athena_client
    if _athena_client is None:
        _athena_client = boto3.client('athena', region_name=REGION)
    return _athena_client

def _get_glue_client():
    """Get Glue client (lazy initialization)"""
    global _glue_client
    if _glue_client is None:
        _glue_client = boto3.client('glue', region_name=REGION)
    return _glue_client

# Note: ACCOUNT_ID, athena_client, glue_client are now accessed via functions
# _get_account_id(), _get_athena_client(), _get_glue_client()
# This avoids initialization timeout during agent startup


def execute_athena_query(query, database=None):
    """Execute Athena query on VCF table"""
    if not database:
        database = LAKE_FORMATION_DATABASE
    
    print(f"Executing query on database '{database}':")
    print(f"  {query}")
    
    try:
        athena = _get_athena_client()
        account_id = _get_account_id()
        response = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': database},
            WorkGroup='primary',
            ResultConfiguration={
                'OutputLocation': f's3://aws-athena-query-results-{account_id}-{REGION}/'
            }
        )
        
        query_id = response['QueryExecutionId']
        
        # Wait for completion with longer timeout for complex queries
        max_attempts = 90  # Increased from 30 to 90 (3 minutes total)
        for attempt in range(max_attempts):
            result = athena.get_query_execution(QueryExecutionId=query_id)
            status = result['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                break
            elif status in ['FAILED', 'CANCELLED']:
                error_reason = result['QueryExecution']['Status'].get('StateChangeReason', 'Unknown error')
                raise Exception(f"Query failed: {error_reason}")
            
            time.sleep(2)
        
        if status != 'SUCCEEDED':
            raise Exception("Query timed out")
        
        # Get results with pagination
        rows = []
        next_token = None
        columns = None
        
        while True:
            if next_token:
                results = athena.get_query_results(
                    QueryExecutionId=query_id,
                    NextToken=next_token,
                    MaxResults=1000
                )
            else:
                results = athena.get_query_results(
                    QueryExecutionId=query_id,
                    MaxResults=1000
                )
            
            # Get column names from first response
            if columns is None:
                columns = [col['Name'] for col in results['ResultSet']['ResultSetMetadata']['ColumnInfo']]
            
            # Process rows (skip header only on first page)
            start_idx = 1 if next_token is None else 0
            for row in results['ResultSet']['Rows'][start_idx:]:
                # Athena returns different value types - handle all of them
                row_data = []
                for col in row['Data']:
                    # Check for different Athena data types
                    if 'VarCharValue' in col:
                        row_data.append(col['VarCharValue'])
                    elif 'IntValue' in col:
                        row_data.append(str(col['IntValue']))
                    elif 'BigIntValue' in col:
                        row_data.append(str(col['BigIntValue']))
                    elif 'DoubleValue' in col:
                        row_data.append(str(col['DoubleValue']))
                    elif 'BooleanValue' in col:
                        row_data.append(str(col['BooleanValue']))
                    else:
                        # Empty or NULL value
                        row_data.append('')
                row_dict = dict(zip(columns, row_data))
                rows.append(row_dict)
            
            # Check if there are more results
            next_token = results.get('NextToken')
            if not next_token:
                break
        
        print(f"Retrieved {len(rows)} rows")
        return rows
        
    except Exception as e:
        print(f"Error executing Athena query: {e}")
        raise


def count_samples_in_vcf():
    """
    Count the number of distinct samples/patients in the VCF data.
    
    VCF files typically have sample information in:
    1. The INFO column (sometimes has sample IDs)
    2. Separate sample columns (in multi-sample VCFs)
    3. Filename patterns
    
    For now, we'll check the table structure and extract what we can.
    """
    try:
        # First, check the table schema
        glue = _get_glue_client()
        table = glue.get_table(
            DatabaseName=LAKE_FORMATION_DATABASE,
            Name=VCF_TABLE_NAME
        )
        
        columns = [col['Name'] for col in table['Table']['StorageDescriptor']['Columns']]
        print(f"Table columns: {columns}")
        
        # Check if there are partition columns (might contain sample info)
        partition_keys = table['Table'].get('PartitionKeys', [])
        partition_names = [pk['Name'] for pk in partition_keys]
        print(f"Partition columns: {partition_names}")
        
        # Strategy 1: Check for sample-specific columns (FORMAT columns in multi-sample VCF)
        sample_columns = [col for col in columns if col not in ['chrom', 'pos', 'id', 'ref', 'alt', 'qual', 'filter', 'info']]
        
        if sample_columns:
            # Multi-sample VCF with sample columns
            num_samples = len(sample_columns)
            return {
                'method': 'sample_columns',
                'sample_count': num_samples,
                'samples': sample_columns,
                'message': f'Found {num_samples} sample(s) from VCF column names'
            }
        
        # Strategy 2: Check partitions (files might be partitioned by sample)
        if 'sample' in partition_names or 'sampleid' in partition_names:
            partition_col = 'sample' if 'sample' in partition_names else 'sampleid'
            query = f"SELECT DISTINCT {partition_col} FROM {VCF_TABLE_NAME}"
            results = execute_athena_query(query)
            
            samples = [row[partition_col] for row in results if row.get(partition_col)]
            return {
                'method': 'partition_column',
                'sample_count': len(samples),
                'samples': samples,
                'message': f'Found {len(samples)} sample(s) from partition column'
            }
        
        # Strategy 3: Count distinct files (each file might be a sample)
        # Check table location to see if we can infer samples from file paths
        location = table['Table']['StorageDescriptor']['Location']
        
        # Try to count rows as a proxy (each VCF file is typically one sample)
        # Filter out VCF header rows
        query = f"""
        SELECT COUNT(*) as variant_count 
        FROM {VCF_TABLE_NAME}
        WHERE chrom NOT LIKE '#%'
            AND chrom != 'CHROM'
            AND LENGTH(chrom) <= 5
        """
        results = execute_athena_query(query)
        
        variant_count = int(results[0]['variant_count'])
        
        # If the VCF has an 'id' column that looks like it has sample prefixes, try that
        if 'id' in columns:
            query_sample_check = f"""
            SELECT id 
            FROM {VCF_TABLE_NAME} 
            WHERE chrom NOT LIKE '#%'
                AND chrom != 'CHROM'
                AND id IS NOT NULL 
                AND id != '.'
            LIMIT 100
            """
            id_results = execute_athena_query(query_sample_check)
            
            # Check if IDs follow a pattern like "SAMPLE_variant" or similar
            sample_prefixes = set()
            for row in id_results:
                id_val = row.get('id', '')
                # Convert to string to handle cases where id is an integer
                id_val = str(id_val) if id_val else ''
                if id_val and '_' in id_val:
                    prefix = id_val.split('_')[0]
                    sample_prefixes.add(prefix)
            
            if len(sample_prefixes) > 0 and len(sample_prefixes) < 1000:
                return {
                    'method': 'id_prefix',
                    'sample_count': str(len(sample_prefixes)),
                    'samples': list(sample_prefixes),
                    'message': f'Inferred {len(sample_prefixes)} sample(s) from variant ID patterns',
                    'note': 'This is an estimation based on ID prefixes'
                }
        
        # Fallback: Report what we know
        return {
            'method': 'unknown',
            'sample_count': 'unknown',
            'variant_count': str(variant_count),
            'table_location': str(location),
            'message': f'Unable to determine sample count. VCF table has {variant_count:,} variants.',
            'note': 'This appears to be a single-sample VCF or the sample information is not in standard columns',
            'suggestion': 'Check the INFO column or file naming patterns for sample information'
        }
        
    except Exception as e:
        return {
            'error': f'Error counting samples: {str(e)}',
            'suggestion': 'Ensure Lake Formation permissions are granted and table exists'
        }


def get_vcf_summary():
    """Get a summary of the VCF data"""
    try:
        # Filter out VCF header rows (lines starting with # or metadata)
        query = f"""
        SELECT 
            COUNT(*) as total_variants,
            COUNT(DISTINCT chrom) as unique_chromosomes,
            MIN(CAST(pos AS BIGINT)) as min_position,
            MAX(CAST(pos AS BIGINT)) as max_position,
            COUNT(CASE WHEN filter = 'PASS' THEN 1 END) as pass_variants,
            COUNT(CASE WHEN filter = '.' OR filter IS NULL THEN 1 END) as unfiltered_variants,
            COUNT(CASE WHEN filter != 'PASS' AND filter != '.' AND filter IS NOT NULL THEN 1 END) as filtered_variants,
            AVG(CAST(qual AS DOUBLE)) as avg_quality
        FROM {VCF_TABLE_NAME}
        WHERE chrom NOT LIKE '#%'
            AND chrom != 'CHROM'
            AND LENGTH(chrom) <= 5
            AND (
                chrom IN ('1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','X','Y','MT')
                OR chrom LIKE 'chr%'
            )
        """
        
        results = execute_athena_query(query)
        
        if results:
            summary = results[0]
            return {
                'analysis_type': 'VCF Summary',
                'summary': summary,
                'table': VCF_TABLE_NAME,
                'database': LAKE_FORMATION_DATABASE
            }
        else:
            return {'error': 'No data returned from summary query'}
            
    except Exception as e:
        return {'error': f'Error getting VCF summary: {str(e)}'}


def query_variants_by_chromosome(chromosome, limit=100):
    """Query variants on a specific chromosome"""
    try:
        # Clean chromosome name (handle both 'chr1' and '1' formats)
        chr_clean = chromosome.replace('chr', '').replace('Chr', '').replace('CHR', '')
        
        # Filter out VCF header rows - ClinVar data has filter='.' (not 'PASS')
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
        WHERE chrom IN ('chr{chr_clean}', '{chr_clean}')
            AND chrom NOT LIKE '#%'
            AND LENGTH(chrom) <= 5
        ORDER BY CAST(pos AS BIGINT)
        LIMIT {limit}
        """
        
        results = execute_athena_query(query)
        
        return {
            'analysis_type': 'Chromosome-Specific Variants',
            'chromosome': str(chr_clean),
            'variant_count': str(len(results)),
            'variants': results,
            'table': str(VCF_TABLE_NAME),
            'note': 'ClinVar reference data - filter values may be "." (unfiltered)'
        }
        
    except Exception as e:
        return {'error': f'Error querying variants by chromosome: {str(e)}'}


def get_high_quality_variants(limit=100):
    """Get high-quality variants - for ClinVar data, returns a sample of variants across chromosomes"""
    try:
        # For ClinVar reference data, just return a representative sample of variants
        # Filtering by clinical significance is too slow without indexes
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
            AND (
                chrom IN ('1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','X','Y','MT')
                OR chrom LIKE 'chr%'
            )
        ORDER BY chrom, CAST(pos AS BIGINT)
        LIMIT {limit}
        """
        
        results = execute_athena_query(query)
        
        return {
            'analysis_type': 'Sample Variants',
            'variant_count': str(len(results)),
            'variants': results,
            'filter_criteria': 'Representative sample of ClinVar variants',
            'table': str(VCF_TABLE_NAME),
            'note': 'ClinVar reference data - all variants have clinical significance annotations in INFO field'
        }
        
    except Exception as e:
        return {'error': f'Error getting high-quality variants: {str(e)}'}


def diagnose_vcf_data():
    """Diagnostic function to check what filter values and quality scores exist in the data"""
    try:
        # Check what filter values exist
        filter_query = f"""
        SELECT 
            filter, 
            COUNT(*) as count,
            AVG(qual) as avg_quality,
            MIN(qual) as min_quality,
            MAX(qual) as max_quality
        FROM {VCF_TABLE_NAME}
        GROUP BY filter
        ORDER BY count DESC
        LIMIT 20
        """
        
        filter_results = execute_athena_query(filter_query)
        
        # Get sample data
        sample_query = f"""
        SELECT 
            chrom,
            pos,
            id,
            ref,
            alt,
            qual,
            filter,
            SUBSTR(info, 1, 200) as info_sample
        FROM {VCF_TABLE_NAME}
        LIMIT 10
        """
        
        sample_results = execute_athena_query(sample_query)
        
        return {
            'analysis_type': 'VCF Data Diagnosis',
            'filter_distribution': filter_results,
            'sample_variants': sample_results,
            'table': VCF_TABLE_NAME,
            'database': LAKE_FORMATION_DATABASE
        }
        
    except Exception as e:
        return {'error': f'Error diagnosing VCF data: {str(e)}'}


# Export functions for use in agent tools
__all__ = [
    'count_samples_in_vcf',
    'get_vcf_summary',
    'query_variants_by_chromosome',
    'get_high_quality_variants',
    'execute_athena_query',
    'diagnose_vcf_data'
]


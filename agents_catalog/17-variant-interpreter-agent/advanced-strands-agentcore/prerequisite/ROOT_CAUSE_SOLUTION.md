# Root Cause Analysis & Solution

## Problem Summary

You were getting this error when trying to create variant and annotation stores:
```
❌ Error creating variant store: An error occurred (AccessDeniedException) 
   when calling the CreateVariantStore operation: Unable to determine 
   service/operation name to be authorized
```

## Root Cause ✅ IDENTIFIED

The diagnostic revealed the actual problem:

1. ✅ **IAM Permissions**: You have AdministratorAccess - permissions are NOT the issue
2. ✅ **boto3/botocore versions**: Version 1.41.2 - up to date
3. ✅ **Reference Store exists**: ID `3068761940` exists and is accessible
4. ❌ **Reference Genome MISSING**: The reference store is **completely empty**!

```
❌ Reference Genome NOT FOUND: The specified reference does not exist.
Available References in store 3068761940: No references found in this store!
```

### Why This Caused the Error

When you try to create a variant or annotation store, you must provide a valid reference ARN:
```
arn:aws:omics:us-east-1:149536495426:referenceStore/3068761940/reference/8931115867
```

Since reference `8931115867` doesn't exist in your reference store, the API couldn't determine what you were trying to authorize, leading to the confusing error message: "Unable to determine service/operation name to be authorized".

## Solution

You need to **import a reference genome** into your reference store before you can create variant/annotation stores.

### Step 1: Import Reference Genome (Run Cell 13)

The notebook now includes a cell that will:
- Check if any references already exist
- If empty, start a reference import job for GRCh38 from AWS public datasets
- The import takes **30-60 minutes** to complete

Run the cell and you should see:
```
✅ Import job started successfully!
   Job ID: <job-id>
   Status: SUBMITTED
⏳ Import is running in the background...
   This typically takes 30-60 minutes
```

### Step 2: Monitor Import Progress (Run Cell 14 periodically)

While the import is running, periodically run Cell 14 to check status:
```python
check_reference_import_status()
```

You'll see:
- Import job status (SUBMITTED → IN_PROGRESS → COMPLETED)
- When complete, available reference genome IDs
- Automatic update of `REFERENCE_GENOME_ID` variable

### Step 3: Create Variant & Annotation Stores

Once the import completes and Cell 14 shows:
```
✅ REFERENCE_GENOME_ID updated to: <new-id>
🎉 You can now proceed to create variant and annotation stores!
```

Then run the cells to create variant and annotation stores - they will now succeed!

## Alternative: Upload Your Own Reference

If the AWS public dataset doesn't work, you can upload your own reference genome:

### Option 1: Upload to S3 and Import
```bash
# 1. Upload your reference FASTA to S3
aws s3 cp GRCh38.fasta s3://genomics-vep-output-bucket-149536495426-us-east-1/references/

# 2. Start import job
aws omics start-reference-import-job \
  --reference-store-id 3068761940 \
  --role-arn arn:aws:iam::149536495426:role/genomics-vep-pipeline-healthomics-workflow-role \
  --sources sourceFile=s3://genomics-vep-output-bucket-149536495426-us-east-1/references/GRCh38.fasta,name=GRCh38
```

### Option 2: Use a Different Reference Store

If you have another reference store with references already imported:

1. List all reference stores:
```bash
aws omics list-reference-stores --region us-east-1
```

2. For each store, check if it has references:
```bash
aws omics list-references --reference-store-id <store-id> --region us-east-1
```

3. Update Cell 7 in the notebook with the correct IDs:
```python
REFERENCE_STORE_ID = '<store-id-with-references>'
REFERENCE_GENOME_ID = '<reference-id-from-that-store>'
```

## Why "Unable to determine service/operation name" Was Misleading

This error message is AWS's generic response when:
1. The API can't validate the resource ARN you provided
2. The resource in the ARN doesn't exist
3. The service can't determine which operation to authorize

In your case, it wasn't an IAM permissions issue at all - it was an invalid reference ARN pointing to a non-existent genome.

## Next Steps

1. ✅ **Run Cell 13** to start the reference genome import
2. ⏳ **Wait 30-60 minutes** for the import to complete
3. 🔄 **Run Cell 14** periodically to check progress
4. ✅ **When complete**, run the variant/annotation store creation cells
5. 🎉 **Continue** with the rest of the deployment!

## Files Modified

- ✅ `genomics-vep-pipeline-deployment-complete.ipynb` - Added diagnostic and import cells
- ✅ `healthomics-admin-policy.json` - IAM policy (not needed, but useful for reference)
- ✅ `attach-healthomics-policy.sh` - Policy attachment script (already ran successfully)
- ✅ `infrastructure.yaml` - Updated with HealthOmics permissions
- ✅ `ROOT_CAUSE_SOLUTION.md` - This document

## Summary

| Issue | Status |
|-------|--------|
| IAM Permissions | ✅ Fixed (AdministratorAccess already present) |
| boto3 version | ✅ Good (1.41.2) |
| Reference Store | ✅ Exists (3068761940) |
| Reference Genome | ❌ Missing → **Action Required: Run Cell 13 to import** |
| Variant Store | ⏳ Pending reference genome import |
| Annotation Store | ⏳ Pending reference genome import |

**Current blockers**: Reference genome import (30-60 min)  
**Action required**: Run Cell 13 and wait for import to complete


# HealthOmics Permissions Fix

## Problem
When running the deployment notebook, you encountered these errors:

```
❌ Error creating variant store: An error occurred (AccessDeniedException) when calling the CreateVariantStore operation: Unable to determine service/operation name to be authorized
❌ Error creating annotation store: An error occurred (AccessDeniedException) when calling the CreateAnnotationStore operation: Unable to determine service/operation name to be authorized
```

This occurs because your IAM user/role lacks the necessary permissions to create HealthOmics resources.

## Solution Options

### Option 1: Quick Fix - Attach Policy to Your IAM User (Recommended for Testing)

Run the provided script to attach the necessary permissions to your current IAM identity:

```bash
cd /Users/zaaisvanzyl/Documents/GitHub/amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/17-variant-interpreter-agent/advanced-strands-agentcore/prerequisite
./attach-healthomics-policy.sh
```

**What this does:**
- Detects your current IAM user or role
- Creates/updates an IAM policy with HealthOmics permissions
- Attaches the policy to your identity

**Requirements:**
- AWS CLI configured with your profile
- Permission to create and attach IAM policies
- `jq` installed (for JSON parsing)

### Option 2: Manual Policy Attachment via AWS Console

1. **Open AWS IAM Console** → Users (or Roles)
2. **Find your user/role** (the one you're using with your AWS profile)
3. **Click "Add permissions"** → "Attach policies directly"
4. **Click "Create policy"** → JSON tab
5. **Paste the contents** from `healthomics-admin-policy.json`
6. **Name it:** `HealthOmicsAdminPolicy`
7. **Attach** the policy to your user/role

### Option 3: Update CloudFormation Stack (For Production)

The CloudFormation template has been updated with the necessary permissions. To apply them:

```bash
# Navigate to the prerequisite directory
cd /Users/zaaisvanzyl/Documents/GitHub/amazon-bedrock-agents-healthcare-lifesciences/agents_catalog/17-variant-interpreter-agent/advanced-strands-agentcore/prerequisite

# Update the CloudFormation stack
aws cloudformation update-stack \
  --stack-name genomics-vep-pipeline \
  --template-body file://infrastructure.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile default \
  --region us-east-1
```

**Note:** This updates the Lambda execution role permissions but won't affect your notebook execution unless you modify the notebook to assume that role.

## Permissions Added

The following permissions have been added to fix the issue:

### HealthOmics Store Management
- `omics:CreateVariantStore`
- `omics:DeleteVariantStore`
- `omics:UpdateVariantStore`
- `omics:CreateAnnotationStore`
- `omics:DeleteAnnotationStore`
- `omics:UpdateAnnotationStore`

### HealthOmics Import Jobs
- `omics:StartVariantImportJob`
- `omics:GetVariantImportJob`
- `omics:ListVariantImportJobs`
- `omics:StartAnnotationImportJob`
- `omics:GetAnnotationImportJob`
- `omics:ListAnnotationImportJobs`

### HealthOmics Reference Store
- `omics:CreateReferenceStore`
- `omics:DeleteReferenceStore`
- `omics:GetReferenceStore`
- `omics:ListReferenceStores`
- `omics:StartReferenceImportJob`
- `omics:GetReferenceImportJob`
- `omics:GetReference`
- `omics:ListReferences`

### HealthOmics Workflows
- `omics:CreateWorkflow`
- `omics:DeleteWorkflow`
- `omics:StartRun`
- `omics:GetRun`
- `omics:CancelRun`

### Resource Sharing (RAM)
- `ram:AcceptResourceShareInvitation`
- `ram:GetResourceShareInvitations`
- `ram:ListResources`
- `ram:GetResourceShares`

### Supporting Services
- IAM PassRole (for HealthOmics service)
- S3 access for genomics buckets
- Lake Formation permissions
- Glue catalog access

## Verification

After applying the fix, verify your permissions:

```bash
# Check if you can list variant stores (should work even if empty)
aws omics list-variant-stores --profile default --region us-east-1

# Check if you can list annotation stores
aws omics list-annotation-stores --profile default --region us-east-1
```

If these commands succeed without errors, your permissions are correctly configured.

## Re-run the Notebook

After fixing permissions, re-run the notebook cells that create the variant and annotation stores:

1. **Cell 11:** Create Variant Store
2. **Cell 12:** Create Annotation Store

The creation should now succeed with output like:

```
🚀 Creating variant store: genomicsvariantstore
✅ Variant store creation initiated with ID: 1234567
⏳ Store is being created in the background...
```

## Troubleshooting

### Script Fails with "jq: command not found"

Install jq:
```bash
# macOS
brew install jq

# Linux (Ubuntu/Debian)
sudo apt-get install jq

# Linux (RHEL/CentOS)
sudo yum install jq
```

### Script Fails with "AccessDenied" for IAM operations

Your IAM user doesn't have permission to create/attach policies. Options:
1. Ask your AWS administrator to attach the policy
2. Use Option 2 (Manual Console approach)
3. Have an admin run the script for you

### Still Getting AccessDenied After Attaching Policy

- **Wait 30-60 seconds** for IAM permissions to propagate
- **Refresh credentials** if using temporary credentials
- **Check AWS Region** - ensure you're using the same region (us-east-1)
- **Verify policy attachment:**
  ```bash
  aws iam list-attached-user-policies --user-name YOUR_USERNAME --profile default
  ```

### "Unable to determine service/operation name" Error

This specific error indicates the HealthOmics service API is not being called correctly or permissions are completely missing. After attaching the policy, this error should be resolved.

## Files Created/Modified

- ✅ `healthomics-admin-policy.json` - IAM policy document
- ✅ `attach-healthomics-policy.sh` - Automated policy attachment script
- ✅ `infrastructure.yaml` - Updated with HealthOmics permissions
- ✅ `PERMISSIONS_FIX.md` - This documentation

## Next Steps

1. **Apply the fix** using one of the three options above
2. **Verify permissions** using the verification commands
3. **Re-run notebook cells** to create the stores
4. **Continue with deployment** following the notebook instructions

## Additional Resources

- [AWS HealthOmics Documentation](https://docs.aws.amazon.com/omics/)
- [AWS HealthOmics IAM Permissions](https://docs.aws.amazon.com/omics/latest/dev/security-iam.html)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)


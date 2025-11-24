#!/bin/bash

# Script to attach HealthOmics permissions to your IAM user/role
# This script creates an IAM policy and attaches it to your current IAM identity

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}HealthOmics Policy Attachment${NC}"
echo -e "${GREEN}================================${NC}"
echo

# Get AWS profile and region from environment or use defaults
AWS_PROFILE=${AWS_PROFILE:-default}
AWS_REGION=${AWS_REGION:-us-east-1}

echo -e "${YELLOW}Using AWS Profile:${NC} $AWS_PROFILE"
echo -e "${YELLOW}Using AWS Region:${NC} $AWS_REGION"
echo

# Get current IAM identity
echo -e "${YELLOW}Checking current IAM identity...${NC}"
IDENTITY=$(aws sts get-caller-identity --profile $AWS_PROFILE --region $AWS_REGION)
ACCOUNT_ID=$(echo $IDENTITY | jq -r '.Account')
USER_ARN=$(echo $IDENTITY | jq -r '.Arn')
USER_ID=$(echo $IDENTITY | jq -r '.UserId')

echo -e "${GREEN}Account ID:${NC} $ACCOUNT_ID"
echo -e "${GREEN}User ARN:${NC} $USER_ARN"
echo

# Determine if this is a user or a role
if [[ $USER_ARN == *":user/"* ]]; then
    IDENTITY_TYPE="user"
    IDENTITY_NAME=$(echo $USER_ARN | awk -F'/' '{print $NF}')
elif [[ $USER_ARN == *":assumed-role/"* ]]; then
    IDENTITY_TYPE="role"
    IDENTITY_NAME=$(echo $USER_ARN | awk -F'/' '{print $(NF-1)}')
else
    echo -e "${RED}❌ Unable to determine identity type${NC}"
    exit 1
fi

echo -e "${YELLOW}Identity Type:${NC} $IDENTITY_TYPE"
echo -e "${YELLOW}Identity Name:${NC} $IDENTITY_NAME"
echo

# Policy details
POLICY_NAME="HealthOmicsAdminPolicy"
POLICY_FILE="healthomics-admin-policy.json"

# Check if policy file exists
if [ ! -f "$POLICY_FILE" ]; then
    echo -e "${RED}❌ Policy file not found: $POLICY_FILE${NC}"
    echo -e "${YELLOW}Please ensure you're running this script from the prerequisite directory${NC}"
    exit 1
fi

echo -e "${YELLOW}Creating/updating IAM policy...${NC}"

# Check if policy already exists
EXISTING_POLICY_ARN=$(aws iam list-policies --profile $AWS_PROFILE --region $AWS_REGION --scope Local --query "Policies[?PolicyName=='$POLICY_NAME'].Arn" --output text)

if [ -z "$EXISTING_POLICY_ARN" ]; then
    # Create new policy
    echo -e "${YELLOW}Creating new IAM policy: $POLICY_NAME${NC}"
    POLICY_ARN=$(aws iam create-policy \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --policy-name $POLICY_NAME \
        --policy-document file://$POLICY_FILE \
        --description "Administrative permissions for AWS HealthOmics service" \
        --query 'Policy.Arn' \
        --output text)
    echo -e "${GREEN}✅ Policy created: $POLICY_ARN${NC}"
else
    POLICY_ARN=$EXISTING_POLICY_ARN
    echo -e "${GREEN}✅ Policy already exists: $POLICY_ARN${NC}"
    
    # Create a new version of the policy
    echo -e "${YELLOW}Updating policy with new version...${NC}"
    
    # Get the default version
    DEFAULT_VERSION=$(aws iam get-policy \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --policy-arn $POLICY_ARN \
        --query 'Policy.DefaultVersionId' \
        --output text)
    
    # List all versions
    VERSIONS=$(aws iam list-policy-versions \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --policy-arn $POLICY_ARN \
        --query 'Versions[?IsDefaultVersion==`false`].VersionId' \
        --output text)
    
    # Delete old versions if there are 5 (AWS limit)
    VERSION_COUNT=$(aws iam list-policy-versions \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --policy-arn $POLICY_ARN \
        --query 'length(Versions)' \
        --output text)
    
    if [ "$VERSION_COUNT" -ge 5 ]; then
        OLDEST_VERSION=$(aws iam list-policy-versions \
            --profile $AWS_PROFILE \
            --region $AWS_REGION \
            --policy-arn $POLICY_ARN \
            --query 'Versions[-1].VersionId' \
            --output text)
        echo -e "${YELLOW}Deleting oldest policy version: $OLDEST_VERSION${NC}"
        aws iam delete-policy-version \
            --profile $AWS_PROFILE \
            --region $AWS_REGION \
            --policy-arn $POLICY_ARN \
            --version-id $OLDEST_VERSION
    fi
    
    # Create new version
    aws iam create-policy-version \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --policy-arn $POLICY_ARN \
        --policy-document file://$POLICY_FILE \
        --set-as-default > /dev/null
    
    echo -e "${GREEN}✅ Policy updated${NC}"
fi

echo

# Attach policy to user or role
echo -e "${YELLOW}Attaching policy to $IDENTITY_TYPE: $IDENTITY_NAME${NC}"

if [ "$IDENTITY_TYPE" = "user" ]; then
    # Check if already attached
    ATTACHED=$(aws iam list-attached-user-policies \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --user-name $IDENTITY_NAME \
        --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN'].PolicyArn" \
        --output text)
    
    if [ -z "$ATTACHED" ]; then
        aws iam attach-user-policy \
            --profile $AWS_PROFILE \
            --region $AWS_REGION \
            --user-name $IDENTITY_NAME \
            --policy-arn $POLICY_ARN
        echo -e "${GREEN}✅ Policy attached to user: $IDENTITY_NAME${NC}"
    else
        echo -e "${GREEN}✅ Policy already attached to user: $IDENTITY_NAME${NC}"
    fi
elif [ "$IDENTITY_TYPE" = "role" ]; then
    # Check if already attached
    ATTACHED=$(aws iam list-attached-role-policies \
        --profile $AWS_PROFILE \
        --region $AWS_REGION \
        --role-name $IDENTITY_NAME \
        --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN'].PolicyArn" \
        --output text)
    
    if [ -z "$ATTACHED" ]; then
        aws iam attach-role-policy \
            --profile $AWS_PROFILE \
            --region $AWS_REGION \
            --role-name $IDENTITY_NAME \
            --policy-arn $POLICY_ARN
        echo -e "${GREEN}✅ Policy attached to role: $IDENTITY_NAME${NC}"
    else
        echo -e "${GREEN}✅ Policy already attached to role: $IDENTITY_NAME${NC}"
    fi
fi

echo
echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Policy attachment complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. The policy has been attached to your IAM identity"
echo "2. You can now create variant stores and annotation stores"
echo "3. Re-run the notebook cell that creates the stores"
echo
echo -e "${YELLOW}Note:${NC} If you're using temporary credentials, you may need to refresh them"
echo


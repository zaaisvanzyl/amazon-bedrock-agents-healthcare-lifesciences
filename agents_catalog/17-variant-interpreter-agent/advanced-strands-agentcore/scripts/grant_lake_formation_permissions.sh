#!/bin/bash
# Quick script to grant Lake Formation permissions for genomics agent

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "🔐 Lake Formation Permissions Setup"
echo "=========================================="

# Default values
DATABASE_NAME="${LAKE_FORMATION_DATABASE:-genomics_agent_db2}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")

if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Error: Unable to get AWS account ID${NC}"
    echo "Please ensure AWS CLI is configured correctly"
    exit 1
fi

echo "📊 Database: $DATABASE_NAME"
echo "📍 Region: $REGION"
echo "🆔 Account ID: $ACCOUNT_ID"
echo ""

# Get current identity
echo "🔍 Detecting current IAM identity..."
IDENTITY_ARN=$(aws sts get-caller-identity --query Arn --output text)

if [[ $IDENTITY_ARN == *":assumed-role/"* ]]; then
    # Extract role name from assumed role ARN
    ROLE_NAME=$(echo $IDENTITY_ARN | cut -d'/' -f2)
    PRINCIPAL_ARN="arn:aws:iam::$ACCOUNT_ID:role/$ROLE_NAME"
elif [[ $IDENTITY_ARN == *":user/"* ]]; then
    # It's an IAM user
    PRINCIPAL_ARN=$IDENTITY_ARN
else
    PRINCIPAL_ARN=$IDENTITY_ARN
fi

echo -e "${GREEN}✅ Principal: $PRINCIPAL_ARN${NC}"
echo ""

# Check if Lake Formation permissions are needed
echo "🔍 Checking current Lake Formation permissions..."
CURRENT_PERMS=$(aws lakeformation list-permissions \
    --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \
    --region $REGION 2>/dev/null || echo "[]")

echo ""
echo "=========================================="
echo "📋 Granting Lake Formation Permissions"
echo "=========================================="
echo ""

# Grant database permissions
echo "1️⃣  Granting DESCRIBE permission on database '$DATABASE_NAME'..."
aws lakeformation grant-permissions \
    --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \
    --resource "{\"Database\":{\"Name\":\"$DATABASE_NAME\"}}" \
    --permissions "DESCRIBE" \
    --region $REGION 2>&1 | grep -v "AlreadyExistsException" || true

echo -e "${GREEN}   ✅ Database permissions granted${NC}"
echo ""

# Get list of tables in the database
echo "2️⃣  Discovering tables in database..."
TABLES=$(aws glue get-tables \
    --database-name $DATABASE_NAME \
    --region $REGION \
    --query 'TableList[].Name' \
    --output text 2>/dev/null || echo "")

if [ -z "$TABLES" ]; then
    echo -e "${YELLOW}   ⚠️  No tables found in database '$DATABASE_NAME'${NC}"
    echo ""
    echo "Possible reasons:"
    echo "   - Database is empty"
    echo "   - Glue Crawler hasn't run yet"
    echo "   - Tables haven't been created"
    echo ""
    echo "You can manually grant permissions for a table:"
    echo "   ./grant_lake_formation_permissions.sh <table_name>"
    echo ""
else
    TABLE_COUNT=$(echo $TABLES | wc -w)
    echo -e "${GREEN}   ✅ Found $TABLE_COUNT table(s): $TABLES${NC}"
    echo ""
    
    # Grant permissions for each table
    for TABLE_NAME in $TABLES; do
        echo "3️⃣  Granting permissions for table: $TABLE_NAME"
        
        # Grant table-level permissions
        echo "   📋 Granting SELECT and DESCRIBE on table..."
        aws lakeformation grant-permissions \
            --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \
            --resource "{\"Table\":{\"DatabaseName\":\"$DATABASE_NAME\",\"Name\":\"$TABLE_NAME\"}}" \
            --permissions "SELECT" "DESCRIBE" \
            --region $REGION 2>&1 | grep -v "AlreadyExistsException" || true
        
        # Grant column-level permissions
        echo "   📋 Granting SELECT on all columns..."
        aws lakeformation grant-permissions \
            --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \
            --resource "{\"TableWithColumns\":{\"DatabaseName\":\"$DATABASE_NAME\",\"Name\":\"$TABLE_NAME\",\"ColumnWildcard\":{}}}" \
            --permissions "SELECT" \
            --region $REGION 2>&1 | grep -v "AlreadyExistsException" || true
        
        echo -e "${GREEN}   ✅ Permissions granted for table '$TABLE_NAME'${NC}"
        echo ""
    done
fi

echo "=========================================="
echo "📊 SUMMARY"
echo "=========================================="
echo -e "${GREEN}✅ Lake Formation permissions configured!${NC}"
echo ""
echo "Database: $DATABASE_NAME"
echo "Principal: $PRINCIPAL_ARN"
echo "Region: $REGION"
echo ""

# If specific table was provided as argument
if [ ! -z "$1" ]; then
    TABLE_NAME=$1
    echo "🔧 Also granting permissions for specified table: $TABLE_NAME"
    
    aws lakeformation grant-permissions \
        --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \
        --resource "{\"Table\":{\"DatabaseName\":\"$DATABASE_NAME\",\"Name\":\"$TABLE_NAME\"}}" \
        --permissions "SELECT" "DESCRIBE" \
        --region $REGION 2>&1 | grep -v "AlreadyExistsException" || true
    
    aws lakeformation grant-permissions \
        --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \
        --resource "{\"TableWithColumns\":{\"DatabaseName\":\"$DATABASE_NAME\",\"Name\":\"$TABLE_NAME\",\"ColumnWildcard\":{}}}" \
        --permissions "SELECT" \
        --region $REGION 2>&1 | grep -v "AlreadyExistsException" || true
    
    echo -e "${GREEN}✅ Permissions granted for '$TABLE_NAME'${NC}"
fi

echo ""
echo "✨ You can now:"
echo "   1. Query the database using Athena"
echo "   2. Run the genomics agent"
echo "   3. Execute SQL queries on the tables"
echo ""
echo "To verify permissions:"
echo "   aws lakeformation list-permissions \\"
echo "     --principal DataLakePrincipalIdentifier=$PRINCIPAL_ARN \\"
echo "     --region $REGION"
echo ""


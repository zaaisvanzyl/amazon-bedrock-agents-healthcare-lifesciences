#!/bin/bash
# Check VEP workflow status and provide commands to retry

REGION=us-east-1
ACCOUNT_ID=149536495426

echo "🔍 Checking VEP Workflow Status..."
echo "=" | tr = "=" | head -c 70 && echo

# Get the latest run
echo "📊 Latest Run:"
LATEST_RUN=$(aws omics list-runs \
  --region $REGION \
  --max-items 1 \
  --query 'items[0]' \
  --output json 2>/dev/null)

if [ -z "$LATEST_RUN" ] || [ "$LATEST_RUN" == "null" ]; then
  echo "❌ No runs found. You may need to start your first run."
  echo ""
  echo "💡 To start a run, use your deployment notebook/script or:"
  echo "   aws omics start-run --workflow-id <WORKFLOW_ID> --role-arn <ROLE_ARN> ..."
  exit 0
fi

RUN_ID=$(echo "$LATEST_RUN" | jq -r '.id')
RUN_STATUS=$(echo "$LATEST_RUN" | jq -r '.status')
RUN_NAME=$(echo "$LATEST_RUN" | jq -r '.name // "unnamed"')
RUN_START=$(echo "$LATEST_RUN" | jq -r '.startTime')

echo "   Run ID: $RUN_ID"
echo "   Name: $RUN_NAME"
echo "   Status: $RUN_STATUS"
echo "   Started: $RUN_START"
echo ""

# Get detailed run info
echo "🔍 Detailed Run Info:"
RUN_DETAILS=$(aws omics get-run --id $RUN_ID --region $REGION --output json 2>/dev/null)

WORKFLOW_ID=$(echo "$RUN_DETAILS" | jq -r '.workflowId')
ROLE_ARN=$(echo "$RUN_DETAILS" | jq -r '.roleArn')
OUTPUT_URI=$(echo "$RUN_DETAILS" | jq -r '.outputUri // "N/A"')

echo "   Workflow ID: $WORKFLOW_ID"
echo "   Role: $ROLE_ARN"
echo "   Output: $OUTPUT_URI"
echo ""

# Check ECR permissions
echo "🔐 ECR Repository Permissions:"
ECR_POLICY=$(aws ecr get-repository-policy \
  --repository-name ensembl-vep \
  --region $REGION \
  --query 'policyText' \
  --output text 2>/dev/null | jq -r '.Statement[] | select(.Principal.Service == "omics.amazonaws.com")')

if [ ! -z "$ECR_POLICY" ]; then
  echo "   ✅ HealthOmics has pull permissions"
else
  echo "   ❌ HealthOmics does NOT have pull permissions"
  echo "   Run: ./fix_ecr_permissions.sh"
fi
echo ""

# Check recent logs
echo "📝 Recent Logs:"
LOG_ENTRIES=$(aws omics get-run --id $RUN_ID --region $REGION \
  --query 'logEvents[-5:]' \
  --output json 2>/dev/null)

if [ ! -z "$LOG_ENTRIES" ] && [ "$LOG_ENTRIES" != "null" ]; then
  echo "$LOG_ENTRIES" | jq -r '.[] | "\(.timestamp) [\(.logLevel)] \(.message)"'
else
  echo "   No log events available"
fi
echo ""

# Provide next steps based on status
echo "=" | tr = "=" | head -c 70 && echo
echo "🎯 Next Steps:"
echo ""

case $RUN_STATUS in
  RUNNING)
    echo "✅ Workflow is currently RUNNING"
    echo ""
    echo "To monitor logs:"
    echo "   aws logs tail /aws/omics/WorkflowLog --follow \\"
    echo "     --log-stream-name run/$RUN_ID/engine \\"
    echo "     --region $REGION"
    ;;
  COMPLETED)
    echo "🎉 Workflow COMPLETED successfully!"
    echo ""
    echo "Check outputs at: $OUTPUT_URI"
    ;;
  FAILED)
    echo "❌ Workflow FAILED"
    echo ""
    echo "To view full logs:"
    echo "   aws logs tail /aws/omics/WorkflowLog \\"
    echo "     --log-stream-name run/$RUN_ID/engine \\"
    echo "     --region $REGION"
    echo ""
    echo "To retry with fixed ECR permissions:"
    echo "   aws omics start-run \\"
    echo "     --workflow-id $WORKFLOW_ID \\"
    echo "     --role-arn $ROLE_ARN \\"
    echo "     --name \"vep-run-\$(date +%Y%m%d-%H%M%S)\" \\"
    echo "     --output-uri $OUTPUT_URI \\"
    echo "     --parameters file://path/to/parameters.json \\"
    echo "     --region $REGION"
    echo ""
    echo "💡 ECR permissions have been fixed, so retry should work!"
    ;;
  STOPPING|CANCELLED)
    echo "⚠️  Workflow is $RUN_STATUS"
    echo ""
    echo "To retry once stopped:"
    echo "   aws omics start-run \\"
    echo "     --workflow-id $WORKFLOW_ID \\"
    echo "     --role-arn $ROLE_ARN \\"
    echo "     --name \"vep-run-\$(date +%Y%m%d-%H%M%S)\" \\"
    echo "     --output-uri $OUTPUT_URI \\"
    echo "     --parameters file://path/to/parameters.json \\"
    echo "     --region $REGION"
    ;;
  *)
    echo "ℹ️  Status: $RUN_STATUS"
    ;;
esac

echo ""
echo "=" | tr = "=" | head -c 70 && echo


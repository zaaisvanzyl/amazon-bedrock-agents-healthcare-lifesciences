"""
AWS Lambda Function: Workflow Monitor with Glue Crawler Integration
Monitors HealthOmics workflow completion and triggers Glue Crawler to catalog VEP outputs
"""

import json
import boto3
import os
from datetime import datetime
from botocore.exceptions import ClientError

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb')
glue_client = boto3.client('glue')
omics_client = boto3.client('omics')
s3_client = boto3.client('s3')

# Environment variables
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
CRAWLER_NAME = os.environ.get('CRAWLER_NAME')
DATABASE_NAME = os.environ.get('DATABASE_NAME')
VEP_OUTPUT_BUCKET = os.environ.get('VEP_OUTPUT_BUCKET')

print(f"Initialized with:")
print(f"  DynamoDB Table: {DYNAMODB_TABLE}")
print(f"  Crawler Name: {CRAWLER_NAME}")
print(f"  Database: {DATABASE_NAME}")
print(f"  VEP Output Bucket: {VEP_OUTPUT_BUCKET}")


def lambda_handler(event, context):
    """
    Handle HealthOmics workflow completion events and trigger Glue Crawler
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Check if this is a HealthOmics workflow status change event
        if 'detail-type' in event and event['detail-type'] == 'HealthOmics Run Status Change':
            return handle_workflow_status_change(event)
        
        # Check if this is an S3 event (VEP output files)
        elif 'Records' in event:
            return handle_s3_event(event)
        
        else:
            print(f"Unknown event type: {event.get('detail-type', 'No detail-type')}")
            return {
                'statusCode': 200,
                'body': json.dumps('Event type not handled')
            }
    
    except Exception as e:
        print(f"Error processing event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }


def handle_workflow_status_change(event):
    """
    Handle HealthOmics workflow completion and trigger Glue Crawler
    """
    detail = event.get('detail', {})
    run_id = detail.get('id')
    status = detail.get('status')
    workflow_id = detail.get('workflowId')
    
    print(f"Workflow Status Change:")
    print(f"  Run ID: {run_id}")
    print(f"  Workflow ID: {workflow_id}")
    print(f"  Status: {status}")
    
    # Update DynamoDB with workflow status
    if DYNAMODB_TABLE:
        try:
            table = dynamodb.Table(DYNAMODB_TABLE)
            table.update_item(
                Key={'SampleID': run_id},
                UpdateExpression='SET WorkflowStatus = :status, LastUpdated = :timestamp',
                ExpressionAttributeValues={
                    ':status': status,
                    ':timestamp': datetime.utcnow().isoformat()
                }
            )
            print(f"✅ Updated DynamoDB tracking for run {run_id}")
        except Exception as e:
            print(f"⚠️ Error updating DynamoDB: {e}")
    
    # If workflow completed successfully, trigger Glue Crawler
    if status == 'COMPLETED':
        print(f"🎉 Workflow {run_id} completed successfully!")
        
        # Get run details to find output location
        try:
            run_details = omics_client.get_run(id=run_id)
            output_uri = run_details.get('outputUri', '')
            print(f"  Output URI: {output_uri}")
            
            # Update DynamoDB with output location
            if DYNAMODB_TABLE:
                table = dynamodb.Table(DYNAMODB_TABLE)
                table.update_item(
                    Key={'SampleID': run_id},
                    UpdateExpression='SET OutputLocation = :uri, ProcessingStage = :stage',
                    ExpressionAttributeValues={
                        ':uri': output_uri,
                        ':stage': 'CATALOGING'
                    }
                )
        except Exception as e:
            print(f"⚠️ Could not get run details: {e}")
        
        # Trigger Glue Crawler to catalog the new VEP outputs
        trigger_result = trigger_glue_crawler()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Workflow {run_id} completed',
                'crawler_triggered': trigger_result
            })
        }
    
    elif status in ['FAILED', 'CANCELLED']:
        print(f"❌ Workflow {run_id} {status}")
        return {
            'statusCode': 200,
            'body': json.dumps(f'Workflow {status}')
        }
    
    else:
        print(f"ℹ️  Workflow status: {status}")
        return {
            'statusCode': 200,
            'body': json.dumps(f'Workflow status: {status}')
        }


def handle_s3_event(event):
    """
    Handle S3 events for new VEP output files and trigger Glue Crawler
    """
    print("Processing S3 event...")
    
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"New file detected:")
        print(f"  Bucket: {bucket}")
        print(f"  Key: {key}")
        
        # Check if this is a VEP output file
        if 'vep-outputs' in key or 'vep_annotated' in key:
            print(f"✅ VEP output file detected, triggering crawler")
            trigger_result = trigger_glue_crawler()
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'VEP output detected',
                    'file': key,
                    'crawler_triggered': trigger_result
                })
            }
    
    return {
        'statusCode': 200,
        'body': json.dumps('No VEP outputs detected')
    }


def trigger_glue_crawler():
    """
    Trigger the Glue Crawler to catalog VEP outputs
    Returns: dict with status and message
    """
    if not CRAWLER_NAME:
        print("⚠️ No crawler name configured")
        return {'status': 'skipped', 'message': 'No crawler configured'}
    
    try:
        # Check crawler status first
        crawler_status = glue_client.get_crawler(Name=CRAWLER_NAME)
        current_state = crawler_status['Crawler']['State']
        
        print(f"Crawler '{CRAWLER_NAME}' current state: {current_state}")
        
        if current_state == 'RUNNING':
            print("ℹ️  Crawler already running, skipping trigger")
            return {
                'status': 'already_running',
                'message': f'Crawler {CRAWLER_NAME} is already running'
            }
        
        # Start the crawler
        response = glue_client.start_crawler(Name=CRAWLER_NAME)
        print(f"✅ Successfully triggered Glue Crawler: {CRAWLER_NAME}")
        
        return {
            'status': 'triggered',
            'message': f'Crawler {CRAWLER_NAME} started successfully',
            'crawler_name': CRAWLER_NAME
        }
    
    except glue_client.exceptions.CrawlerRunningException:
        print("ℹ️  Crawler is already running")
        return {
            'status': 'already_running',
            'message': f'Crawler {CRAWLER_NAME} is already running'
        }
    
    except glue_client.exceptions.EntityNotFoundException:
        error_msg = f'Crawler {CRAWLER_NAME} not found'
        print(f"❌ {error_msg}")
        return {
            'status': 'error',
            'message': error_msg
        }
    
    except Exception as e:
        error_msg = f'Error starting crawler: {str(e)}'
        print(f"❌ {error_msg}")
        return {
            'status': 'error',
            'message': error_msg
        }


def get_crawler_status():
    """
    Get the current status of the Glue Crawler
    """
    if not CRAWLER_NAME:
        return {'error': 'No crawler name configured'}
    
    try:
        response = glue_client.get_crawler(Name=CRAWLER_NAME)
        crawler = response['Crawler']
        
        return {
            'name': crawler['Name'],
            'state': crawler['State'],
            'creation_time': str(crawler.get('CreationTime', '')),
            'last_updated': str(crawler.get('LastUpdated', '')),
            'database': crawler.get('DatabaseName', ''),
            'last_crawl': crawler.get('LastCrawl', {})
        }
    except Exception as e:
        return {'error': f'Error getting crawler status: {str(e)}'}


# For testing
if __name__ == '__main__':
    # Test workflow completion event
    test_event = {
        'detail-type': 'HealthOmics Run Status Change',
        'detail': {
            'id': 'test-run-123',
            'workflowId': 'test-workflow-456',
            'status': 'COMPLETED'
        }
    }
    
    print("Testing workflow completion event:")
    result = lambda_handler(test_event, None)
    print(f"Result: {json.dumps(result, indent=2)}")


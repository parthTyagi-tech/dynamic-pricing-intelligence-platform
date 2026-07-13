import os
import json
from google.cloud import tasks_v2

def create_pricing_recommendation_task(recommendation_id: str, product_id: str):
    """
    Dispatches a task to Google Cloud Tasks to process a pricing recommendation asynchronously.
    Falls back to synchronous or log warning if GCP environment variables are not set.
    """
    project = os.environ.get("GCP_PROJECT_ID")
    location = os.environ.get("GCP_LOCATION", "us-central1")
    queue = os.environ.get("GCP_QUEUE_NAME", "pricing-queue")
    backend_url = os.environ.get("BACKEND_PUBLIC_URL")

    if not project or not backend_url:
        print("[GCP Cloud Tasks Warning] GCP_PROJECT_ID or BACKEND_PUBLIC_URL not set. Skipping task queue dispatch.")
        return None

    try:
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project, location, queue)

        url = f"{backend_url.rstrip('/')}/api/recommendations/process-task"
        payload = {
            "recommendation_id": recommendation_id,
            "product_id": product_id
        }

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode("utf-8")
            }
        }

        # Enable Google OIDC authentication if service account email is set
        service_account_email = os.environ.get("GCP_SERVICE_ACCOUNT_EMAIL")
        if service_account_email:
            task["http_request"]["oidc_token"] = {
                "service_account_email": service_account_email,
                "audience": url
            }

        response = client.create_task(request={"parent": parent, "task": task})
        print(f"[GCP Cloud Tasks] Created task: {response.name}")
        return response.name
    except Exception as e:
        print(f"[GCP Cloud Tasks Error] Failed to create Cloud Task: {e}")
        return None

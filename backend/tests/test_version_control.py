"""
Test script cho Version Control API

Usage:
    cd backend
    python tests/test_version_control.py
"""
import requests
import json
import os

BASE_URL = "http://localhost:8000/api/v1"


def login(email: str, password: str) -> str:
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.text}")
        return None


def test_version_control():
    """Test full version control workflow"""
    print("=" * 60)
    print("Testing Version Control API")
    print("=" * 60)

    # 1. Login
    print("\n[1] Logging in...")
    token = login("test@example.com", "Test123456")
    if not token:
        # Try creating admin user first
        print("Trying to register admin user...")
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": "admin@example.com",
                "password": "Admin123456",
                "name": "Admin User"
            }
        )
        if response.status_code in [200, 201]:
            token = response.json().get("access_token")
        else:
            print(f"Failed to register: {response.text}")
            return

    if not token:
        print("Failed to get access token")
        return

    headers = {"Authorization": f"Bearer {token}"}
    print(f"Got access token: {token[:20]}...")

    # 2. Upload a test document
    print("\n[2] Uploading test document...")

    # Create a test file
    test_content = b"# Test Document V1\n\nThis is version 1 of the test document.\n\n## Content\nSome initial content here."

    files = {
        "file": ("test_version_control.md", test_content, "text/markdown")
    }
    data = {
        "title": "Test Version Control Document",
        "tags": "test,version"
    }

    response = requests.post(
        f"{BASE_URL}/documents",
        headers=headers,
        files=files,
        data=data
    )

    if response.status_code not in [200, 201]:
        print(f"Failed to upload document: {response.text}")
        return

    document = response.json()
    document_id = document["id"]
    print(f"Created document: {document_id}")
    print(f"Initial version: {document['version']}")

    # 3. Get version history (should have 1 version)
    print("\n[3] Getting version history...")
    response = requests.get(
        f"{BASE_URL}/documents/{document_id}/versions",
        headers=headers
    )

    if response.status_code == 200:
        versions = response.json()
        print(f"Found {len(versions)} version(s):")
        for v in versions:
            print(f"  - v{v['version']} ({v['change_type']}): {v.get('change_summary', 'N/A')}")
    else:
        print(f"Failed to get versions: {response.text}")

    # 4. Update document metadata
    print("\n[4] Updating document metadata (should create new version)...")
    response = requests.put(
        f"{BASE_URL}/documents/{document_id}",
        headers=headers,
        json={
            "title": "Test Version Control Document - Updated",
            "tags": ["test", "version", "updated"]
        }
    )

    if response.status_code == 200:
        updated = response.json()
        print(f"Updated document, new version: {updated['version']}")
    else:
        print(f"Failed to update: {response.text}")

    # 5. Upload new version with new file
    print("\n[5] Uploading new version with new file...")
    test_content_v2 = b"# Test Document V2\n\nThis is version 2 of the test document.\n\n## Updated Content\nThis content has been completely rewritten.\n\n## New Section\nAdded a new section."

    files = {
        "file": ("test_version_control_v2.md", test_content_v2, "text/markdown")
    }
    data = {
        "change_summary": "Major rewrite with new content structure",
        "is_major_version": "true"
    }

    response = requests.post(
        f"{BASE_URL}/documents/{document_id}/versions",
        headers=headers,
        files=files,
        data=data
    )

    if response.status_code == 200:
        new_version = response.json()
        print(f"Created new version: {new_version['version']}")
        print(f"Change type: {new_version['change_type']}")
        print(f"Summary: {new_version.get('change_summary', 'N/A')}")
    else:
        print(f"Failed to create new version: {response.text}")

    # 6. Get full version history
    print("\n[6] Getting full version history...")
    response = requests.get(
        f"{BASE_URL}/documents/{document_id}/versions",
        headers=headers
    )

    if response.status_code == 200:
        versions = response.json()
        print(f"Total {len(versions)} versions:")
        for v in versions:
            print(f"  - v{v['version']} (#{v['version_number']}) [{v['change_type']}]")
            print(f"    Summary: {v.get('change_summary', 'N/A')}")
            print(f"    Changed by: {v.get('changed_by_name', v['changed_by'])}")
            print(f"    At: {v['created_at']}")
    else:
        print(f"Failed to get versions: {response.text}")

    # 7. Get specific version detail
    if versions:
        first_version_id = versions[-1]["id"]  # First version (oldest)
        print(f"\n[7] Getting detail of first version ({first_version_id})...")
        response = requests.get(
            f"{BASE_URL}/documents/{document_id}/versions/{first_version_id}",
            headers=headers
        )

        if response.status_code == 200:
            detail = response.json()
            print(f"Version: {detail['version']}")
            print(f"Content snapshot preview: {detail.get('content_snapshot', 'N/A')[:100]}...")
        else:
            print(f"Failed to get version detail: {response.text}")

        # 8. Test restore
        print(f"\n[8] Testing restore to first version...")
        response = requests.post(
            f"{BASE_URL}/documents/{document_id}/versions/restore",
            headers=headers,
            json={
                "version_id": first_version_id,
                "change_summary": "Restoring to original version for testing"
            }
        )

        if response.status_code == 200:
            restored = response.json()
            print(f"Restored! New version: {restored['version']}")
            print(f"Change type: {restored['change_type']}")
        else:
            print(f"Failed to restore: {response.text}")

    # 9. Final version history
    print("\n[9] Final version history:")
    response = requests.get(
        f"{BASE_URL}/documents/{document_id}/versions",
        headers=headers
    )

    if response.status_code == 200:
        versions = response.json()
        print(f"Total {len(versions)} versions:")
        for v in versions:
            print(f"  - v{v['version']} (#{v['version_number']}) [{v['change_type']}]: {v.get('change_summary', 'N/A')}")

    # Cleanup
    print("\n[10] Cleaning up - deleting test document...")
    response = requests.delete(
        f"{BASE_URL}/documents/{document_id}",
        headers=headers
    )
    if response.status_code == 204:
        print("Document deleted successfully")
    else:
        print(f"Failed to delete: {response.text}")

    print("\n" + "=" * 60)
    print("Version Control Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_version_control()

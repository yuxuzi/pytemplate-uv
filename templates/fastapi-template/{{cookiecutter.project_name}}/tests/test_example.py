import pytest
from httpx import AsyncClient
from {{cookiecutter.package_name}}.models import ExampleModel

pytestmark = pytest.mark.asyncio

async def test_health_check(client: AsyncClient):
    """Test the health check endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data

async def test_create_example(client: AsyncClient):
    """Test creating a new example."""
    example_data = {
        "name": "Test Example",
        "description": "This is a test example"
    }
    response = await client.post("/api/v1/examples/", json=example_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == example_data["name"]
    assert data["description"] == example_data["description"]
    assert "id" in data

async def test_get_example(client: AsyncClient):
    """Test getting an example by ID."""
    # First create an example
    example_data = {
        "name": "Test Get Example",
        "description": "This is a test get example"
    }
    create_response = await client.post("/api/v1/examples/", json=example_data)
    created_example = create_response.json()
    
    # Then get it by ID
    response = await client.get(f"/api/v1/examples/{created_example['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == example_data["name"]
    assert data["description"] == example_data["description"]

async def test_get_nonexistent_example(client: AsyncClient):
    """Test getting a nonexistent example."""
    response = await client.get("/api/v1/examples/999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "NOT_FOUND"

async def test_list_examples(client: AsyncClient):
    """Test listing examples with pagination."""
    # Create multiple examples
    examples = [
        {"name": f"Example {i}", "description": f"Description {i}"}
        for i in range(3)
    ]
    for example in examples:
        await client.post("/api/v1/examples/", json=example)
    
    # Test pagination
    response = await client.get("/api/v1/examples/?skip=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Test skip
    response = await client.get("/api/v1/examples/?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0

async def test_delete_example(client: AsyncClient):
    """Test deleting an example."""
    # First create an example
    example_data = {
        "name": "Test Delete Example",
        "description": "This is a test delete example"
    }
    create_response = await client.post("/api/v1/examples/", json=example_data)
    created_example = create_response.json()
    
    # Then delete it
    response = await client.delete(f"/api/v1/examples/{created_example['id']}")
    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"]
    
    # Verify it's gone
    get_response = await client.get(f"/api/v1/examples/{created_example['id']}")
    assert get_response.status_code == 404

def test_example_model():
    """Test ExampleModel creation and validation."""
    example = ExampleModel(
        name="Test Model",
        description="Test Description"
    )
    assert example.name == "Test Model"
    assert example.description == "Test Description"
    assert example.id is None

    # Test model validation
    with pytest.raises(ValueError):
        ExampleModel(name="", description="Invalid example with empty name")

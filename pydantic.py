from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# =============================================================================
# EXAMPLE 1: Basic Model & Type Validation
# =============================================================================
class User(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool = True

def example_basic_validation():
    print("--- Example 1: Basic Validation ---")
    try:
        # Correct data
        user = User(id=1, username="jdoe", email="jdoe@example.com")
        print(f"Success: {user}")

        # Incorrect type (will be coerced if possible)
        user_coerced = User(id="2", username="asmith", email="asmith@example.com")
        print(f"Coerced Success: {user_coerced}")

        # Invalid data (missing field or wrong type that cannot be coerced)
        User(id=3, username="error", email=123)  # email should be str
    except Exception as e:
        print(f"Caught expected error: {e}\n")


# =============================================================================
# EXAMPLE 2: Using Field for Constraints & Metadata
# =============================================================================
class Product(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    price: float = Field(..., gt=0, description="Price must be greater than zero")
    stock: int = Field(default=0, ge=0)

def example_field_constraints():
    print("--- Example 2: Field Constraints ---")
    try:
        product = Product(name="Laptop", price=999.99, stock=10)
        print(f"Success: {product}")

        # Invalid name (too short)
        Product(name="L", price=50.0)
    except Exception as e:
        print(f"Caught expected error: {e}\n")


# =============================================================================
# EXAMPLE 3: Nested Models & Complex Types
# =============================================================================
class Address(BaseModel):
    street: str
    city: str
    zip_code: str

class DetailedUser(BaseModel):
    user: User
    address: Address
    tags: List[str] = []

def example_nested_models():
    print("--- Example 3: Nested Models ---")
    data = {
        "user": {"id": 10, "username": "complex_user", "email": "complex@example.com"},
        "address": {"street": "123 Python Lane", "city": "Codeville", "zip_code": "12345"},
        "tags": ["developer", "pythonist"]
    }
    detailed = DetailedUser(**data)
    print(f"Success: {detailed.user.username} lives in {detailed.address.city}")
    print(f"Tags: {detailed.tags}\n")


# =================================================================
# EXAMPLE 4: Field & Model Validators
# =============================================================================
class Registration(BaseModel):
    password: str = Field(..., min_length=8)
    confirm_password: str

    @field_validator('password')
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        return v

    @model_validator(mode='after')
    def check_passwords_match(self) -> 'Registration':
        if self.password != self.confirm_password:
            raise ValueError('Passwords do not match')
        return self

def example_validators():
    print("--- Example 4: Validators ---")
    try:
        # Passwords don't match
        Registration(password="StrongPass123", confirm_password="DifferentPass123")
    except Exception as e:
        print(f"Caught expected error (mismatch): {e}")

    try:
        # Password too simple (no digit)
        Registration(password="NoDigitsHere", confirm_password="NoDigitsHere")
    except Exception as e:
        print(f"Caught expected error (complexity): {e}\n")

    # Success
    reg = Registration(password="StrongPass123", confirm_password="StrongPass123")
    print(f"Success: Password validated!\n")


# =============================================================================
# EXAMPLE 5: Serialization & Configuration
# =============================================================================
class ConfiguredModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    internal_id: int = Field(..., alias="ID")
    display_name: str

def example_serialization():
    print("--- Example 5: Serialization & Config ---")
    # Using alias and stripping whitespace
    model = ConfiguredModel(ID=101, display_name="  Pydantic Pro  ")
    print(
        f"Object: {model}\n"
        f"Dict: {model.model_dump()}\n"
        f"JSON: {model.model_dump_json()}"
    )
    print("")


if __name__ == "__main__":
    example_basic_validation()
    example_field_constraints()
    example_nested_models()
    example_validators()
    example_serialization()

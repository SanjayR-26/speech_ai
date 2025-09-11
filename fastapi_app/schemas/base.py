"""
Base schemas with common functionality
"""
from pydantic import BaseModel, model_serializer
from typing import Any, Dict
from uuid import UUID


class BaseSchema(BaseModel):
    """Base schema class with UUID serialization"""
    
    @model_serializer(mode='wrap')
    def serialize_model(self, serializer, info) -> Dict[str, Any]:
        """Custom model serializer to handle UUID conversion"""
        data = serializer(self)
        
        # Convert UUID objects to strings
        def convert_uuids(obj):
            if isinstance(obj, dict):
                return {k: convert_uuids(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_uuids(item) for item in obj]
            elif isinstance(obj, UUID):
                return str(obj)
            else:
                return obj
        
        return convert_uuids(data)
    
    model_config = {"from_attributes": True}
